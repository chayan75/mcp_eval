#!/bin/bash
# Simple script to update ECR image for MCP Evaluation Server

set -euo pipefail

# Configuration
APP_NAME="mcp-eval-server"
REGION="us-east-1"
IMAGE_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Get AWS account ID
print_status "Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_NAME="${APP_NAME}"
FULL_IMAGE_URI="${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

print_status "ECR Registry: ${ECR_REGISTRY}"
print_status "Image URI: ${FULL_IMAGE_URI}"

# Create ECR repository if it doesn't exist
if ! aws ecr describe-repositories --repository-names "${IMAGE_NAME}" --region "${REGION}" &> /dev/null; then
    print_status "Creating ECR repository: ${IMAGE_NAME}"
    aws ecr create-repository --repository-name "${IMAGE_NAME}" --region "${REGION}" >&2
fi

# Login to ECR
print_status "Logging in to ECR..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}" >&2

# Build Docker image
print_status "Building Docker image..."
docker build -f Dockerfile -t "${IMAGE_NAME}" . >&2

# Tag image for ECR
docker tag "${IMAGE_NAME}:latest" "${FULL_IMAGE_URI}"

# Push image to ECR
print_status "Pushing image to ECR..."
docker push "${FULL_IMAGE_URI}" >&2

print_success "Image pushed successfully: ${FULL_IMAGE_URI}"
print_status "Image is now available in ECR and ready for App Runner deployment"
