#!/bin/bash
# =============================================================================
# Clio AI - AWS AgentCore Deployment Script (Fixed)
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="clio-agentcore"
IMAGE_TAG="latest"
AGENT_NAME="product-matching-agent"
EXECUTION_ROLE_NAME="ClioAgentCoreExecutionRole"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🚀 Clio AI AgentCore Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# =============================================================================
# Step 1: Create IAM Execution Role with proper checking
# =============================================================================
echo -e "${YELLOW}📋 Step 1: Creating IAM execution role...${NC}"

# Check if role exists
ROLE_EXISTS=$(aws iam get-role --role-name $EXECUTION_ROLE_NAME 2>/dev/null || echo "NOT_FOUND")

if [ "$ROLE_EXISTS" = "NOT_FOUND" ]; then
    echo "Creating new IAM role..."
    
    # Create trust policy
    cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    aws iam create-role \
        --role-name $EXECUTION_ROLE_NAME \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --description "Execution role for Clio AI AgentCore Runtime" \
        --region $AWS_REGION
    
    echo -e "${GREEN}✓ Role created${NC}"
    
    # Wait for role to be available
    echo "⏳ Waiting for IAM role to be available..."
    sleep 10
else
    echo -e "${YELLOW}✓ Role already exists${NC}"
fi

# Attach policies (with retry logic)
echo "Attaching IAM policies..."

for i in {1..5}; do
    if aws iam attach-role-policy \
        --role-name $EXECUTION_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess 2>/dev/null; then
        echo -e "${GREEN}✓ Attached AmazonBedrockFullAccess${NC}"
        break
    else
        if [ $i -eq 5 ]; then
            echo -e "${RED}❌ Failed to attach AmazonBedrockFullAccess after 5 attempts${NC}"
            exit 1
        fi
        echo "Retry $i/5 - waiting 5 seconds..."
        sleep 5
    fi
done

for i in {1..5}; do
    if aws iam attach-role-policy \
        --role-name $EXECUTION_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess 2>/dev/null; then
        echo -e "${GREEN}✓ Attached CloudWatchLogsFullAccess${NC}"
        break
    else
        if [ $i -eq 5 ]; then
            echo -e "${RED}❌ Failed to attach CloudWatchLogsFullAccess after 5 attempts${NC}"
            exit 1
        fi
        echo "Retry $i/5 - waiting 5 seconds..."
        sleep 5
    fi
done

for i in {1..5}; do
    if aws iam attach-role-policy \
        --role-name $EXECUTION_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly 2>/dev/null; then
        echo -e "${GREEN}✓ Attached AmazonEC2ContainerRegistryReadOnly${NC}"
        break
    else
        if [ $i -eq 5 ]; then
            echo -e "${RED}❌ Failed to attach AmazonEC2ContainerRegistryReadOnly after 5 attempts${NC}"
            exit 1
        fi
        echo "Retry $i/5 - waiting 5 seconds..."
        sleep 5
    fi
done

EXECUTION_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EXECUTION_ROLE_NAME}"
echo -e "${GREEN}✓ IAM role configured: $EXECUTION_ROLE_ARN${NC}"

# Wait for IAM propagation
echo "⏳ Waiting 15 seconds for IAM propagation..."
sleep 15
echo ""

# =============================================================================
# Step 2: Create ECR Repository
# =============================================================================
echo -e "${YELLOW}📦 Step 2: Creating ECR repository...${NC}"

aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &>/dev/null
if [ $? -ne 0 ]; then
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true
    echo -e "${GREEN}✓ Repository created${NC}"
else
    echo -e "${YELLOW}✓ Repository already exists${NC}"
fi
echo ""

# =============================================================================
# Step 3: Build and Push Docker Image
# =============================================================================
echo -e "${YELLOW}🏗️  Step 3: Building and pushing Docker image...${NC}"

# Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to login to ECR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Logged into ECR${NC}"

# Build ARM64 image
echo "Building ARM64 Docker image (this may take a few minutes)..."
docker buildx build --platform linux/arm64 -t ${ECR_REPO_NAME}:${IMAGE_TAG} .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker image built${NC}"

# Tag image
ECR_IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}"
docker tag ${ECR_REPO_NAME}:${IMAGE_TAG} $ECR_IMAGE_URI
echo -e "${GREEN}✓ Image tagged${NC}"

# Push to ECR
echo "Pushing image to ECR..."
docker push $ECR_IMAGE_URI

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to push image to ECR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Image pushed to ECR: $ECR_IMAGE_URI${NC}"
echo ""

# =============================================================================
# Step 4: Create AgentCore Runtime
# =============================================================================
echo -e "${YELLOW}🤖 Step 4: Creating AgentCore Runtime...${NC}"

# Check if runtime exists
echo "Checking for existing runtime..."
EXISTING_RUNTIME=$(aws bedrock-agentcore-control list-agent-runtimes \
    --region $AWS_REGION \
    --query "agentRuntimeSummaries[?agentRuntimeName=='$AGENT_NAME']" \
    --output json 2>/dev/null || echo "[]")

if [ "$EXISTING_RUNTIME" != "[]" ] && [ -n "$EXISTING_RUNTIME" ]; then
    AGENT_ARN=$(echo $EXISTING_RUNTIME | jq -r '.[0].agentRuntimeArn')
    echo "Runtime exists, updating..."
    echo "ARN: $AGENT_ARN"
    
    # Update existing runtime
    aws bedrock-agentcore-control update-agent-runtime \
        --agent-runtime-arn "$AGENT_ARN" \
        --agent-runtime-artifact containerConfiguration={containerUri=$ECR_IMAGE_URI} \
        --region $AWS_REGION
    
    echo -e "${GREEN}✓ Runtime updated${NC}"
else
    echo "Creating new AgentCore Runtime..."
    
    # Create new runtime
    CREATE_RESPONSE=$(aws bedrock-agentcore-control create-agent-runtime \
        --agent-runtime-name $AGENT_NAME \
        --agent-runtime-artifact containerConfiguration={containerUri=$ECR_IMAGE_URI} \
        --network-configuration networkMode=PUBLIC \
        --role-arn $EXECUTION_ROLE_ARN \
        --region $AWS_REGION \
        --output json)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to create AgentCore Runtime${NC}"
        echo "Response: $CREATE_RESPONSE"
        exit 1
    fi
    
    AGENT_ARN=$(echo $CREATE_RESPONSE | jq -r '.agentRuntimeArn')
    echo -e "${GREEN}✓ AgentCore Runtime created${NC}"
    echo "ARN: $AGENT_ARN"
fi
echo ""

# Wait for runtime to be ready
echo "⏳ Waiting for runtime to be ready..."
sleep 20

# =============================================================================
# Success!
# =============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📋 Agent Information:"
echo "  Name: $AGENT_NAME"
echo "  ARN: $AGENT_ARN"
echo "  Region: $AWS_REGION"
echo "  Image: $ECR_IMAGE_URI"
echo "  Role: $EXECUTION_ROLE_ARN"
echo ""
echo "🧪 Test Your Agent:"
echo ""
echo "# Method 1: Using AWS CLI"
echo 'aws bedrock-agentcore invoke-agent-runtime \'
echo "  --agent-runtime-arn \"$AGENT_ARN\" \\"
echo '  --runtime-session-id "test-session-$(date +%s)000000000000000000000" \'
echo '  --payload '"'"'{"input_csv":"vendor_name,vendor_url,product_name,product_url\nCyberArk,cyberark.com,Product,url.com"}'"'"' \'
echo "  --region $AWS_REGION \\"
echo '  output.json && cat output.json'
echo ""
echo "# Method 2: Using Python"
echo "python3 << 'EOF'"
echo "import boto3, json"
echo "client = boto3.client('bedrock-agentcore', region_name='$AWS_REGION')"
echo "response = client.invoke_agent_runtime("
echo "    agentRuntimeArn='$AGENT_ARN',"
echo "    runtimeSessionId='test-' + str(int(__import__('time').time())) + '000000000000000000000',"
echo "    payload=json.dumps({'input_csv':'vendor_name,vendor_url,product_name,product_url\\\\nCyberArk,cyberark.com,Product,url.com'})"
echo ")"
echo "print(json.loads(response['response'].read()))"
echo "EOF"
echo ""
echo "📊 View Logs:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups"
echo ""
echo "🎉 Ready to enrich vendor data at scale!"

# Save deployment info
cat > deployment-agentcore-info.txt <<EOF
Clio AI AgentCore Deployment
============================
Deployed: $(date)
AWS Account: $AWS_ACCOUNT_ID
Region: $AWS_REGION

Agent Runtime:
  Name: $AGENT_NAME
  ARN: $AGENT_ARN
  Image: $ECR_IMAGE_URI
  Execution Role: $EXECUTION_ROLE_ARN

Test Commands:

Method 1 - AWS CLI:
aws bedrock-agentcore invoke-agent-runtime \\
  --agent-runtime-arn "$AGENT_ARN" \\
  --runtime-session-id "test-session-\$(date +%s)000000000000000000000" \\
  --payload '{"input_csv":"vendor_name,vendor_url,product_name,product_url\\nCyberArk,cyberark.com,Product,url.com"}' \\
  --region $AWS_REGION \\
  output.json && cat output.json

Method 2 - Python:
import boto3, json
client = boto3.client('bedrock-agentcore', region_name='$AWS_REGION')
response = client.invoke_agent_runtime(
    agentRuntimeArn='$AGENT_ARN',
    runtimeSessionId='test-session-12345678901234567890123456789012',
    payload=json.dumps({'input_csv':'vendor_name,vendor_url,product_name,product_url\\nCyberArk,cyberark.com,Product,url.com'})
)
print(json.loads(response['response'].read()))

CloudWatch Logs:
/aws/bedrock-agentcore/runtimes/
EOF

echo -e "${GREEN}✓ Deployment info saved to: deployment-agentcore-info.txt${NC}"