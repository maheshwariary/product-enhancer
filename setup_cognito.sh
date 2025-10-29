#!/bin/bash

echo "🔐 Setting up Cognito authentication for Clio AI MCP..."
echo ""

# Set passwords (you can change these)
TEMP_PASSWORD="TempPass123!"
PERMANENT_PASSWORD="ClioAI2025!"

# Create User Pool
echo "Creating Cognito User Pool..."
export POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "ClioAI-MCP" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region us-west-2 \
  --query 'UserPool.Id' \
  --output text)

echo "✅ Pool ID: $POOL_ID"

# Create App Client
echo "Creating App Client..."
export CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "ClioAI-Client" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --region us-west-2 \
  --query 'UserPoolClient.ClientId' \
  --output text)

echo "✅ Client ID: $CLIENT_ID"

# Create User
echo "Creating user..."
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username "clio-user" \
  --temporary-password "$TEMP_PASSWORD" \
  --region us-west-2 \
  --message-action SUPPRESS > /dev/null 2>&1

# Set Permanent Password
aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username "clio-user" \
  --password "$PERMANENT_PASSWORD" \
  --region us-west-2 \
  --permanent > /dev/null 2>&1

echo "✅ User created: clio-user"

# Get Bearer Token
echo "Generating bearer token..."
export BEARER_TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME='clio-user',PASSWORD="$PERMANENT_PASSWORD" \
  --region us-west-2 \
  --query 'AuthenticationResult.AccessToken' \
  --output text)

# Calculate Discovery URL
export DISCOVERY_URL="https://cognito-idp.us-west-2.amazonaws.com/$POOL_ID/.well-known/openid-configuration"

echo ""
echo "================================================"
echo "✅ COGNITO SETUP COMPLETE!"
echo "================================================"
echo ""
echo "📋 SAVE THESE VALUES:"
echo ""
echo "Discovery URL:"
echo "$DISCOVERY_URL"
echo ""
echo "Client ID:"
echo "$CLIENT_ID"
echo ""
echo "Bearer Token (valid for 1 hour):"
echo "$BEARER_TOKEN"
echo ""
echo "Username: clio-user"
echo "Password: $PERMANENT_PASSWORD"
echo ""

# Save to file
cat > cognito_config.txt <<EOF
Clio AI MCP - Cognito Configuration
===================================

Discovery URL:
$DISCOVERY_URL

Client ID:
$CLIENT_ID

Bearer Token (expires in 1 hour):
$BEARER_TOKEN

Username: clio-user
Password: $PERMANENT_PASSWORD

To get a new token when expired:
aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME='clio-user',PASSWORD='$PERMANENT_PASSWORD' \
  --region us-west-2 \
  --query 'AuthenticationResult.AccessToken' \
  --output text

Generated: $(date)
EOF

echo "💾 Configuration saved to: cognito_config.txt"
echo ""
echo "🎯 NEXT STEPS:"
echo "1. Run: agentcore configure -e agent_mcp.py --protocol MCP"
echo "2. When asked for OAuth, type: yes"
echo "3. Paste Discovery URL from above"
echo "4. Paste Client ID from above"
echo "5. Run: agentcore launch --local-build"


