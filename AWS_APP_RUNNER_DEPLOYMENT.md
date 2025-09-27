# 🚀 AWS App Runner Deployment Guide

## MCP Evaluation Server on AWS App Runner

This guide will help you deploy the MCP Evaluation Server to AWS App Runner, making it accessible as both a REST API service and MCP wrapper in the cloud.

## 📋 Prerequisites

### Required Tools
- **AWS CLI** - [Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Docker** - [Install Guide](https://docs.docker.com/get-docker/)
- **AWS Account** with appropriate permissions

### Required AWS Permissions
Your AWS user/role needs the following permissions:
- `apprunner:*`
- `ecr:*`
- `iam:PassRole`
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `logs:*`

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Internet      │    │  AWS App Runner  │    │   ECR Registry  │
│                 │◄──►│                  │◄──►│                 │
│ • REST API      │    │ • Container      │    │ • Docker Image  │
│ • /docs         │    │ • Auto-scaling   │    │ • Versioned     │
│ • /health       │    │ • Load Balancing │    │ • Secure        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Deployment

### Option 1: Automated Deployment Script

1. **Set up AWS credentials:**
   ```bash
   aws configure
   ```

2. **Create IAM role for App Runner:**
   ```bash
   # Create trust policy
   cat > trust-policy.json << 'EOF'
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Service": "tasks.apprunner.amazonaws.com"
         },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   EOF
   
   # Create role
   aws iam create-role \
     --role-name AppRunnerInstanceRole \
     --assume-role-policy-document file://trust-policy.json
   
   # Attach policy
   aws iam attach-role-policy \
     --role-name AppRunnerInstanceRole \
     --policy-arn arn:aws:iam::aws:policy/service-role/AppRunnerServicePolicyForECRAccess
   ```

3. **Set environment variables:**
   ```bash
   export INSTANCE_ROLE_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/AppRunnerInstanceRole"
   export REGION="us-east-1"  # or your preferred region
   ```

4. **Run deployment script:**
   ```bash
   ./deploy-to-apprunner.sh
   ```

## 🌐 **Deployed Endpoints**

Once deployed, your MCP Evaluation Server will be accessible via multiple endpoints:

### **REST API Endpoints**
- **Base URL**: `https://your-app.runner-url.com`
- **API Documentation**: `https://your-app.runner-url.com/docs`
- **Health Check**: `https://your-app.runner-url.com/health`
- **OpenAPI Schema**: `https://your-app.runner-url.com/openapi.json`

### **MCP Wrapper Endpoints**
- **MCP Endpoint**: `https://your-app.runner-url.com/mcp/`
- **Protocol**: Streamable HTTP (SSE)
- **Headers**: `Accept: application/json, text/event-stream`
- **Session Management**: Automatic via `mcp-session-id` header

### **Example Usage**

**REST API Example:**
```bash
curl -X POST https://your-app.runner-url.com/judge/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "response": "Paris is the capital of France.",
    "criteria": [{"name": "accuracy", "description": "Factual accuracy", "scale": "1-5", "weight": 1.0}],
    "rubric": {"criteria": [], "scale_description": {"1": "Wrong", "5": "Correct"}},
    "judge_model": "rule-based"
  }'
```

**MCP Wrapper Example:**
```bash
# Initialize MCP session
curl -X POST https://your-app.runner-url.com/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'

# Call MCP tool
curl -X POST https://your-app.runner-url.com/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: YOUR_SESSION_ID" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "judge_evaluate", "arguments": {...}}}'
```

### Option 2: Manual Deployment via AWS Console

1. **Build and push Docker image to ECR:**
   ```bash
   # Get AWS account ID
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   REGION="us-east-1"
   ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
   
   # Create ECR repository
   aws ecr create-repository --repository-name mcp-eval-server --region ${REGION}
   
   # Login to ECR
   aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
   
   # Build and push image
   docker build -t mcp-eval-server .
   docker tag mcp-eval-server:latest ${ECR_REGISTRY}/mcp-eval-server:latest
   docker push ${ECR_REGISTRY}/mcp-eval-server:latest
   ```

2. **Create App Runner service in AWS Console:**
   - Go to AWS App Runner console
   - Click "Create service"
   - Choose "Container registry" as source
   - Select your ECR repository
   - Configure service settings (see configuration section below)

## ⚙️ Configuration

### Environment Variables

Set these in the App Runner console under "Environment variables":

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for GPT models | `sk-...` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://your-resource.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `your-azure-key` |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models | `sk-ant-...` |
| `OLLAMA_BASE_URL` | Ollama base URL for local models | `http://your-ollama-server:11434` |
| `DEFAULT_JUDGE_MODEL` | Default judge model to use | `gpt-4o-mini` |

### Service Configuration

```yaml
# apprunner.yaml
version: 1.0
runtime: docker
run:
  runtime-version: latest
  command: python3 -m mcp_eval_server.rest_server --port 8080 --host 0.0.0.0
  network:
    port: 8080
    env: PORT
  env:
    - name: PORT
      value: "8080"
    - name: PYTHONUNBUFFERED
      value: "1"
    - name: DEFAULT_JUDGE_MODEL
      value: "gpt-4o-mini"
```

### Health Check Configuration

- **Protocol**: HTTP
- **Path**: `/health`
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Healthy Threshold**: 1
- **Unhealthy Threshold**: 5

## 🔧 Customization

### Scaling Configuration

```json
{
  "AutoScalingConfigurationArn": "arn:aws:apprunner:region:account:autoscalingconfiguration/name/version",
  "MinSize": 1,
  "MaxSize": 10,
  "MaxConcurrency": 100
}
```

### VPC Configuration (Optional)

For private network access:

```json
{
  "VpcConnectorArn": "arn:aws:apprunner:region:account:vpcconnector/name/version",
  "VpcConnectorConfiguration": {
    "VpcConnectorArn": "arn:aws:apprunner:region:account:vpcconnector/name/version"
  }
}
```

## 📊 Monitoring and Logs

### CloudWatch Logs

App Runner automatically sends logs to CloudWatch. View them at:
- **Log Group**: `/aws/apprunner/{service-name}/{service-id}/application`

### Health Monitoring

Monitor your service health:
```bash
# Check service status
aws apprunner describe-service --service-arn <SERVICE_ARN>

# View logs
aws logs describe-log-groups --log-group-name-prefix "/aws/apprunner"
```

## 🧪 Testing Your Deployment

### 1. Health Check
```bash
curl https://your-app-runner-url.awsapprunner.com/health
```

### 2. API Documentation
Visit: `https://your-app-runner-url.awsapprunner.com/docs`

### 3. List Available Tools
```bash
curl https://your-app-runner-url.awsapprunner.com/tools/categories
```

### 4. Test Evaluation
```bash
curl -X POST https://your-app-runner-url.awsapprunner.com/judge/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "response": "Paris is the capital of France.",
    "criteria": [
      {
        "name": "accuracy",
        "description": "Factual accuracy",
        "scale": "1-5",
        "weight": 1.0
      }
    ],
    "rubric": {
      "criteria": [],
      "scale_description": {
        "1": "Wrong",
        "5": "Correct"
      }
    },
    "judge_model": "rule-based"
  }'
```

## 🔒 Security Considerations

### 1. API Keys
- Store API keys as environment variables in App Runner
- Never commit API keys to version control
- Rotate keys regularly

### 2. Network Security
- App Runner provides HTTPS by default
- Consider VPC connector for private network access
- Use IAM roles for service permissions

### 3. Resource Limits
- Set appropriate CPU and memory limits
- Monitor usage and costs
- Implement auto-scaling policies

## 💰 Cost Optimization

### 1. Resource Sizing
- Start with minimal resources (0.25 vCPU, 0.5 GB RAM)
- Monitor usage and scale as needed
- Use auto-scaling to handle traffic spikes

### 2. API Usage
- Use rule-based judge for testing (no API costs)
- Monitor LLM API usage and costs
- Implement caching for repeated evaluations

### 3. Monitoring
- Set up CloudWatch alarms for cost monitoring
- Use AWS Cost Explorer to track spending
- Implement budget alerts

## 🚨 Troubleshooting

### Common Issues

1. **Service fails to start:**
   - Check CloudWatch logs
   - Verify environment variables
   - Ensure Docker image builds correctly

2. **Health check failures:**
   - Verify `/health` endpoint is accessible
   - Check port configuration (should be 8080)
   - Review health check timeout settings

3. **API key issues:**
   - Verify environment variables are set correctly
   - Check API key validity and permissions
   - Review judge model configuration

### Debug Commands

```bash
# Check service status
aws apprunner describe-service --service-arn <SERVICE_ARN>

# View recent logs
aws logs tail /aws/apprunner/{service-name}/{service-id}/application --follow

# Test health endpoint
curl -v https://your-app-runner-url.awsapprunner.com/health
```

## 🔄 Updates and Maintenance

### Updating the Service

1. **Build new image:**
   ```bash
   docker build -t mcp-eval-server .
   docker tag mcp-eval-server:latest ${ECR_REGISTRY}/mcp-eval-server:latest
   docker push ${ECR_REGISTRY}/mcp-eval-server:latest
   ```

2. **App Runner will auto-deploy** if auto-deployments are enabled

### Manual Updates

```bash
# Update service configuration
aws apprunner update-service \
  --service-arn <SERVICE_ARN> \
  --source-configuration file://apprunner-service-config.json
```

## 📚 Additional Resources

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [App Runner Pricing](https://aws.amazon.com/apprunner/pricing/)
- [ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [MCP Evaluation Server README](./README.md)

## 🆘 Support

If you encounter issues:

1. Check the [troubleshooting section](#-troubleshooting)
2. Review CloudWatch logs
3. Verify your AWS permissions
4. Check the [MCP Evaluation Server documentation](./README.md)

---

**🎉 Congratulations!** Your MCP Evaluation Server is now running on AWS App Runner and accessible via REST API!
