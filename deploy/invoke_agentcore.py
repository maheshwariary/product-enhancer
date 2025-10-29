"""
Product Matching MCP Server
Supports both interactive queries AND batch CSV processing
"""
import sys
import json
import boto3
import pandas as pd
from io import StringIO
from datetime import datetime
from pathlib import Path

AGENT_ARN = "arn:aws:bedrock-agentcore:us-west-2:389057546498:runtime/agent-03bwI69Ne6"

def log(msg):
    print(f"[PRODUCT-MATCHING-MCP] {datetime.now()}: {msg}", file=sys.stderr)

def enrich_vendor(vendor_name, vendor_url, product_name="", product_url=""):
    """Enrich a single vendor/product"""
    log(f"Enriching: {vendor_name}")
    
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    csv_input = f"vendor_name,vendor_url,product_name,product_url\n{vendor_name},{vendor_url},{product_name or vendor_name},{product_url or vendor_url}"
    
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN,
        runtimeSessionId=f'mcp-{int(__import__("time").time())}000000000000000',
        payload=json.dumps({"input_csv": csv_input})
    )
    
    result = json.loads(response['response'].read())
    
    if result.get('status') == 'success':
        df = pd.read_csv(StringIO(result['output_csv']))
        row = df.to_dict('records')[0]
        
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
                "features": row.get('product_features')
            },
            "taxonomy": {
                "match_1": row.get('taxonomy_match_1'),
                "match_2": row.get('taxonomy_match_2')
            }
        }
    else:
        return {"error": result.get('error')}

def enrich_csv_file(input_file_path, output_file_path, max_concurrent=20):
    """Batch process a CSV file"""
    log(f"Batch processing: {input_file_path}")
    
    # Validate input file
    input_path = Path(input_file_path)
    if not input_path.exists():
        return {"error": f"Input file not found: {input_file_path}"}
    
    # Read input CSV
    try:
        input_csv_text = input_path.read_text(encoding='utf-8')
    except Exception as e:
        return {"error": f"Failed to read input file: {e}"}
    
    # Count rows
    row_count = len(input_csv_text.strip().split('\n')) - 1
    log(f"Processing {row_count} rows with concurrency {max_concurrent}")
    
    # Estimate time
    estimated_minutes = (row_count / max_concurrent) * 0.5
    
    # Create boto3 client
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    
    # Generate session ID
    import uuid
    session_id = f'batch-{uuid.uuid4().hex}-{uuid.uuid4().hex}'
    
    # Call agent
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({
                "input_csv": input_csv_text,
                "max_concurrent_rows": max_concurrent
            })
        )
    except Exception as e:
        return {"error": f"Agent invocation failed: {e}"}
    
    # Parse response
    try:
        result = json.loads(response['response'].read())
    except Exception as e:
        return {"error": f"Failed to parse response: {e}"}
    
    if result.get('status') != 'success':
        return {"error": result.get('error', 'Unknown error')}
    
    # Save output
    output_path = Path(output_file_path)
    try:
        output_path.write_text(result['output_csv'], encoding='utf-8')
    except Exception as e:
        return {"error": f"Failed to save output: {e}"}
    
    return {
        "success": True,
        "rows_processed": result.get('rows_processed', row_count),
        "output_file": str(output_path.absolute()),
        "estimated_time_minutes": round(estimated_minutes, 1),
        "message": f"Successfully processed {result.get('rows_processed')} rows. Output saved to {output_path.absolute()}"
    }

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
                "serverInfo": {"name": "product-matching-mcp", "version": "1.0.0"}
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
                        "description": "Enrich a single vendor/product with detailed information. Use for 1-5 vendors.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "vendor_name": {"type": "string", "description": "Vendor company name"},
                                "vendor_url": {"type": "string", "description": "Vendor website URL"},
                                "product_name": {"type": "string", "description": "Product name (optional)"},
                                "product_url": {"type": "string", "description": "Product URL (optional)"}
                            },
                            "required": ["vendor_name", "vendor_url"]
                        }
                    },
                    {
                        "name": "enrich_csv_file",
                        "description": "Batch process a CSV file with 100s or 1000s of vendors. Provide full file paths. WARNING: This can take 60+ minutes for large files.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "input_file_path": {
                                    "type": "string",
                                    "description": "Full path to input CSV file (e.g., C:\\data\\vendors.csv)"
                                },
                                "output_file_path": {
                                    "type": "string",
                                    "description": "Full path where enriched CSV will be saved (e.g., C:\\data\\enriched.csv)"
                                },
                                "max_concurrent": {
                                    "type": "integer",
                                    "description": "Max concurrent rows to process (default: 20, max: 50)",
                                    "default": 20
                                }
                            },
                            "required": ["input_file_path", "output_file_path"]
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
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                    }
                }
            except Exception as e:
                log(f"Error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }
        
        elif tool_name == "enrich_csv_file":
            try:
                result = enrich_csv_file(
                    args["input_file_path"],
                    args["output_file_path"],
                    args.get("max_concurrent", 20)
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
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
    log("Starting Product Matching MCP Server")
    log(f"Using agent: {AGENT_ARN}")
    
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_mcp(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            log(f"Error: {e}")
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": 0,
                "error": {"code": -32603, "message": str(e)}
            }), flush=True)

if __name__ == "__main__":
    main()