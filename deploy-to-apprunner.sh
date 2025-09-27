#!/bin/bash
# AWS App Runner Deployment Script for MCP Evaluation Server

set -euo pipefail

# Configuration
APP_NAME="mcp-eval-server"
REGION="us-east-1"
REPOSITORY_URL=""
SERVICE_ROLE_ARN=""
INSTANCE_ROLE_ARN="${INSTANCE_ROLE_ARN:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Build and push Docker image to ECR
build_and_push_image() {
    print_status "Building and pushing Docker image to ECR..."
    
    # Get AWS account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
    IMAGE_NAME="${APP_NAME}"
    IMAGE_TAG="latest"
    FULL_IMAGE_URI="${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    print_status "ECR Registry: ${ECR_REGISTRY}"
    print_status "Image URI: ${FULL_IMAGE_URI}"
    
    # Create ECR repository if it doesn't exist
    if ! aws ecr describe-repositories --repository-names "${IMAGE_NAME}" --region "${REGION}" &> /dev/null; then
        print_status "Creating ECR repository: ${IMAGE_NAME}"
        aws ecr create-repository --repository-name "${IMAGE_NAME}" --region "${REGION}"
    fi
    
    # Login to ECR
    print_status "Logging in to ECR..."
    aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
    
    # Build Docker image
    print_status "Building Docker image..."
    docker build -t "${IMAGE_NAME}" .
    
    # Tag image for ECR
    docker tag "${IMAGE_NAME}:latest" "${FULL_IMAGE_URI}"
    
    # Push image to ECR
    print_status "Pushing image to ECR..."
    docker push "${FULL_IMAGE_URI}"
    
    print_success "Image pushed successfully: ${FULL_IMAGE_URI}"
    echo "${FULL_IMAGE_URI}"
}

# Create App Runner service
create_app_runner_service() {
    local image_uri="$1"
    
    print_status "Creating App Runner service..."
    
    # Create service configuration
    cat > apprunner-service-config.json << EOF
{
    "ServiceName": "${APP_NAME}",
    "SourceConfiguration": {
        "ImageRepository": {
            "ImageIdentifier": "${image_uri}",
            "ImageConfiguration": {
                "Port": "8080",
                "RuntimeEnvironmentVariables": {
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "MCP_EVAL_CACHE_DIR": "/tmp/cache",
                    "MCP_EVAL_RESULTS_DB": "/tmp/results/evaluation_results.db",
                    "DEFAULT_JUDGE_MODEL": "gpt-4o-mini",
                    "PORT": "8080",
                    "MCP_PORT": "9001"
                }
            },
            "ImageRepositoryType": "ECR"
        },
        "AutoDeploymentsEnabled": true
    },
    "InstanceConfiguration": {
        "Cpu": "0.25 vCPU",
        "Memory": "0.5 GB",
        "InstanceRoleArn": "${INSTANCE_ROLE_ARN}"
    },
    "HealthCheckConfiguration": {
        "Protocol": "HTTP",
        "Path": "/health",
        "Interval": 30,
        "Timeout": 10,
        "HealthyThreshold": 1,
        "UnhealthyThreshold": 5
    }
}
EOF
    
    # Create the service
    SERVICE_ARN=$(aws apprunner create-service \
        --cli-input-json file://apprunner-service-config.json \
        --region "${REGION}" \
        --query 'Service.ServiceArn' \
        --output text)
    
    print_success "App Runner service created: ${SERVICE_ARN}"
    echo "${SERVICE_ARN}"
}

# Get service URL
get_service_url() {
    local service_arn="$1"
    
    print_status "Getting service URL..."
    
    # Wait for service to be ready
    print_status "Waiting for service to be ready..."
    aws apprunner wait service-created --service-arn "${service_arn}" --region "${REGION}"
    
    # Get service details
    SERVICE_URL=$(aws apprunner describe-service \
        --service-arn "${service_arn}" \
        --region "${REGION}" \
        --query 'Service.ServiceUrl' \
        --output text)
    
    print_success "Service URL: ${SERVICE_URL}"
    echo "${SERVICE_URL}"
}

# Test the deployed service
test_service() {
    local service_url="$1"
    
    print_status "Testing deployed service..."
    
    # Wait a bit for the service to fully start
    sleep 30
    
    # Test health endpoint
    if curl -f "${service_url}/health" > /dev/null 2>&1; then
        print_success "Health check passed"
    else
        print_warning "Health check failed - service might still be starting"
    fi
    
    # Test tools endpoint
    if curl -f "${service_url}/tools/categories" > /dev/null 2>&1; then
        print_success "Tools endpoint accessible"
    else
        print_warning "Tools endpoint not accessible yet"
    fi
    
    print_status "Service testing completed"
}

# Main deployment function
main() {
    print_status "Starting AWS App Runner deployment for MCP Evaluation Server"
    
    # Check prerequisites
    check_prerequisites
    
    # Check if required parameters are provided
    if [[ -z "${INSTANCE_ROLE_ARN:-}" ]]; then
        print_error "INSTANCE_ROLE_ARN is required. Please set it as an environment variable or modify this script."
        print_status "You can create an instance role with the following policy:"
        cat << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
EOF
        exit 1
    fi
    
    # Build and push image
    IMAGE_URI=$(build_and_push_image)
    
    # Create App Runner service
    SERVICE_ARN=$(create_app_runner_service "${IMAGE_URI}")
    
    # Get service URL
    SERVICE_URL=$(get_service_url "${SERVICE_ARN}")
    
    # Test service
    test_service "${SERVICE_URL}"
    
    print_success "Deployment completed successfully!"
    print_status "Service ARN: ${SERVICE_ARN}"
    print_status "Service URL: ${SERVICE_URL}"
    print_status "API Documentation: ${SERVICE_URL}/docs"
    print_status "Health Check: ${SERVICE_URL}/health"
    
    print_warning "Don't forget to set your API keys in the App Runner console:"
    print_status "- OPENAI_API_KEY"
    print_status "- AZURE_OPENAI_ENDPOINT"
    print_status "- AZURE_OPENAI_API_KEY"
    print_status "- ANTHROPIC_API_KEY"
    print_status "- OLLAMA_BASE_URL"
}

# Run main function
main "$@"
