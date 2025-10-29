"""
Standard AgentCore Handler (Non-MCP Protocol)
Entry point for AgentCore Runtime
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import pandas as pd
from io import StringIO
from pipeline.orchestrator import process_dataframe_batch
from config.reference import initialize_reference_data

# Initialize reference data on cold start
initialize_reference_data()

def lambda_handler(event, context):
    """
    Standard AgentCore handler
    
    Input format:
    {
        "input_csv": "vendor_name,vendor_url,product_name,product_url\\n...",
        "max_concurrent_rows": 50
    }
    
    Output format:
    {
        "status": "success",
        "output_csv": "enriched CSV string",
        "rows_processed": 100
    }
    """
    try:
        # Parse input
        input_csv = event.get('input_csv')
        max_concurrent = event.get('max_concurrent_rows', 20)
        
        if not input_csv:
            return {
                'status': 'error',
                'error': 'Missing input_csv parameter'
            }
        
        # Parse CSV
        try:
            df = pd.read_csv(StringIO(input_csv))
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Invalid CSV format: {str(e)}'
            }
        
        # Validate columns
        required = ['vendor_name', 'vendor_url', 'product_name', 'product_url']
        missing = [c for c in required if c not in df.columns]
        if missing:
            return {
                'status': 'error',
                'error': f'Missing required columns: {missing}'
            }
        
        # Process ALL rows with batching (this is your existing logic!)
        result_df = process_dataframe_batch(df, max_concurrent_rows=max_concurrent)
        
        # Return all results
        return {
            'status': 'success',
            'output_csv': result_df.to_csv(index=False),
            'rows_processed': len(result_df)
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

# For local testing
if __name__ == "__main__":
    test_event = {
        "input_csv": "vendor_name,vendor_url,product_name,product_url\nSalesforce,salesforce.com,Sales Cloud,salesforce.com",
        "max_concurrent_rows": 1
    }
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))