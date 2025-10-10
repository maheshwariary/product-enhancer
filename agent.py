"""
AWS AgentCore Entry Point - Clio AI
"""
import json
import logging
import os
import sys
from typing import Dict, Any
import pandas as pd
from io import StringIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))

# Import AgentCore SDK
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Import your pipeline
from pipeline.orchestrator import process_dataframe_batch
from config.reference import initialize_reference_data

# Create AgentCore app
app = BedrockAgentCoreApp()

_initialized = False

def initialize():
    """Initialize reference data once"""
    global _initialized
    if not _initialized:
        logger.info("🚀 Initializing Clio AI...")
        initialize_reference_data()
        _initialized = True
        logger.info("✅ Ready to process!")


@app.entrypoint
def invoke(payload: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    AgentCore entrypoint
    
    Payload format:
    {
        "input_csv": "vendor_name,vendor_url,product_name,product_url\\n...",
        "max_concurrent_rows": 20
    }
    """
    try:
        initialize()
        
        # Accept both shapes:
        # 1) { "input_csv": "...", "max_concurrent_rows": 20 }
        # 2) { "input": { "input_csv": "...", "max_concurrent_rows": 20 } }
        effective = payload.get('input') if isinstance(payload.get('input'), dict) else payload
        
        input_csv = effective.get('input_csv', '')
        max_concurrent = int(effective.get('max_concurrent_rows', 20))
        
        if not input_csv:
            return {'error': 'No input_csv provided', 'status': 'error'}
        
        logger.info(f"📥 Processing CSV...")
        
        # Parse CSV
        input_df = pd.read_csv(StringIO(input_csv))
        
        # Validate columns
        required = ['vendor_name', 'vendor_url', 'product_name', 'product_url']
        missing = [c for c in required if c not in input_df.columns]
        if missing:
            return {'error': f'Missing columns: {missing}', 'status': 'error'}
        
        logger.info(f"🔄 Processing {len(input_df)} rows...")
        
        # Process
        output_df = process_dataframe_batch(input_df, max_concurrent_rows=max_concurrent)
        
        # Return CSV
        output_csv = output_df.to_csv(index=False)
        
        logger.info(f"✅ Done! Processed {len(output_df)} rows")
        
        return {
            'output_csv': output_csv,
            'rows_processed': len(output_df),
            'status': 'success'
        }
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {'error': str(e), 'status': 'error'}


if __name__ == "__main__":
    app.run()  # Starts HTTP server on port 8080