"""
Local MCP Wrapper for Clio AI
Uses your WORKING agent (agent-03bwI69Ne6) via boto3 (handles SigV4 automatically)
"""
import sys
import json
import boto3
import pandas as pd
from io import StringIO
from datetime import datetime

# Your WORKING agent (the one we deployed first, not the MCP one)
AGENT_ARN = "arn:aws:bedrock-agentcore:us-west-2:389057546498:runtime/agent-03bwI69Ne6"

def log(msg):
    """Log to stderr"""
    print(f"[CLIO-MCP] {datetime.now()}: {msg}", file=sys.stderr)

def enrich_vendor(vendor_name, vendor_url, product_name="", product_url=""):
    """Call the working agent"""
    log(f"Enriching: {vendor_name}")
    
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    
    # Create CSV input
    csv_input = f"vendor_name,vendor_url,product_name,product_url\n{vendor_name},{vendor_url},{product_name or vendor_name},{product_url or vendor_url}"
    
    # Call agent
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN,
        runtimeSessionId=f'mcp-{int(__import__("time").time())}000000000000000000000',
        payload=json.dumps({"input_csv": csv_input})
    )
    
    result = json.loads(response['response'].read())
    
    if result.get('status') == 'success':
        # Parse output CSV
        df = pd.read_csv(StringIO(result['output_csv']))
        row = df.to_dict('records')[0]
        
        # Format nicely
        return {
            "vendor": {
                "legal_name": row.get('legal_vendor_name'),
                "website": row.get('official_vendor_website'),
                "wikipedia": row.get('wikipedia_link'),
                "linkedin": row.get('linkedin_profile'),
                "founded": row.get('founded_year')
            },
            "product": {
                "type": row.get('product_type'),
                "users": row.get('product_users'),
                "tasks": row.get('product_tasks'),
                "features": row.get('product_features')
            },
            "taxonomy": {
                "match_1": row.get('taxonomy_match_1'),
                "match_2": row.get('taxonomy_match_2')
            },
            "attributes": {
                "attr_1": row.get('attribute_1'),
                "attr_2": row.get('attribute_2'),
                "attr_3": row.get('attribute_3')
            }
        }
    else:
        return {"error": result.get('error')}

def handle_mcp(request):
    """Handle MCP protocol requests"""
    method = request.get("method")
    req_id = request.get("id", 0)
    
    if method == "initialize":
        log("Initialize request")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "clio-ai", "version": "1.0.0"}
            }
        }
    
    elif method == "tools/list":
        log("List tools request")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "enrich_vendor",
                        "description": "Enrich vendor and product information with detailed research data including legal names, Wikipedia links, product taxonomy matches, and attribute classifications",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "vendor_name": {
                                    "type": "string",
                                    "description": "Name of the vendor company (e.g., 'CyberArk', 'Salesforce')"
                                },
                                "vendor_url": {
                                    "type": "string",
                                    "description": "Vendor's website URL (e.g., 'cyberark.com', 'salesforce.com')"
                                },
                                "product_name": {
                                    "type": "string",
                                    "description": "Product name (optional, defaults to vendor name)"
                                },
                                "product_url": {
                                    "type": "string",
                                    "description": "Product URL (optional, defaults to vendor URL)"
                                }
                            },
                            "required": ["vendor_name", "vendor_url"]
                        }
                    }
                ]
            }
        }
    
    elif method == "tools/call":
        tool_name = request["params"]["name"]
        args = request["params"]["arguments"]
        
        log(f"Tool call: {tool_name}")
        
        if tool_name == "enrich_vendor":
            try:
                result = enrich_vendor(
                    args["vendor_name"],
                    args["vendor_url"],
                    args.get("product_name", ""),
                    args.get("product_url", "")
                )
                
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                log(f"Error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }
    
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    }

def main():
    log("Starting Clio AI MCP Server")
    log(f"Using agent: {AGENT_ARN}")
    
    # Read MCP requests from stdin
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_mcp(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            log(f"Fatal error: {e}")
            error = {
                "jsonrpc": "2.0",
                "id": 0,
                "error": {"code": -32603, "message": str(e)}
            }
            print(json.dumps(error), flush=True)

if __name__ == "__main__":
    main()