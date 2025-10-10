import boto3
import json

AGENT_ARN = "arn:aws:bedrock-agentcore:us-west-2:389057546498:runtime/agent-03bwI69Ne6"

client = boto3.client('bedrock-agentcore', region_name='us-west-2')

# Test CSV
test_csv = """vendor_name,vendor_url,product_name,product_url
CyberArk Software Ltd.,cyberark.com,CyberArk Workforce Identity,https://www.cyberark.com/products/workforce-identity/"""

payload = {
    "input_csv": test_csv,
    "max_concurrent_rows": 10
}

print("🚀 Testing Clio AI...")
print()

response = client.invoke_agent_runtime(
    agentRuntimeArn=AGENT_ARN,
    runtimeSessionId='test-session-12345678901234567890123456789012',
    payload=json.dumps(payload)
)

result = json.loads(response['response'].read())

if result.get('status') == 'success':
    print("✅ SUCCESS!\n")
    print(f"Rows processed: {result.get('rows_processed')}\n")
    print("Enriched CSV Output:")
    print("="*100)
    print(result.get('output_csv'))
else:
    print(f"❌ Error: {result.get('error')}")