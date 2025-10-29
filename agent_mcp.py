"""
Clio AI - MCP Server for Cursor/Claude Desktop
Exposes vendor/product enrichment as MCP tools
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
import json
import pandas as pd
from io import StringIO

# Import your existing pipeline
from pipeline.orchestrator import process_dataframe_batch
from config.reference import initialize_reference_data

# Initialize MCP server
mcp = FastMCP(
    host="0.0.0.0",
    port=8000,
    stateless_http=True
)

# Initialize reference data
initialize_reference_data()


@mcp.tool()
def enrich_vendor(vendor_name: str, vendor_url: str, product_name: str = "", product_url: str = "") -> dict:
    """
    Enrich a single vendor/product with detailed information.
    
    Args:
        vendor_name: Name of the vendor company
        vendor_url: Vendor's website URL
        product_name: Product name (optional)
        product_url: Product URL (optional)
    
    Returns:
        Enriched vendor and product information including taxonomy matches
    """
    # Create input DataFrame
    input_df = pd.DataFrame([{
        'vendor_name': vendor_name,
        'vendor_url': vendor_url,
        'product_name': product_name or vendor_name,
        'product_url': product_url or vendor_url
    }])
    
    # Process through pipeline
    result_df = process_dataframe_batch(input_df, max_concurrent_rows=1)
    
    # Convert to dict
    result = result_df.to_dict('records')[0]
    
    return {
        "vendor_info": {
            "legal_name": result.get('legal_vendor_name'),
            "website": result.get('official_vendor_website'),
            "acquiring_company": result.get('acquiring_company'),
            "wikipedia": result.get('wikipedia_link'),
            "linkedin": result.get('linkedin_profile'),
            "founded_year": result.get('founded_year')
        },
        "product_info": {
            "type": result.get('product_type'),
            "users": result.get('product_users'),
            "tasks": result.get('product_tasks'),
            "features": result.get('product_features')
        },
        "taxonomy": {
            "match_1": result.get('taxonomy_match_1'),
            "match_2": result.get('taxonomy_match_2')
        },
        "attributes": {
            "attribute_1": result.get('attribute_1'),
            "attribute_2": result.get('attribute_2'),
            "attribute_3": result.get('attribute_3')
        }
    }


@mcp.tool()
def enrich_csv_batch(csv_data: str, max_concurrent: int = 20) -> str:
    """
    Enrich multiple vendors/products from CSV data.
    
    Args:
        csv_data: CSV string with columns: vendor_name, vendor_url, product_name, product_url
        max_concurrent: Maximum concurrent rows to process (default: 20)
    
    Returns:
        Enriched CSV as string
    """
    # Parse input CSV
    input_df = pd.read_csv(StringIO(csv_data))
    
    # Validate columns
    required = ['vendor_name', 'vendor_url', 'product_name', 'product_url']
    missing = [c for c in required if c not in input_df.columns]
    if missing:
        return f"Error: Missing required columns: {missing}"
    
    # Process
    result_df = process_dataframe_batch(input_df, max_concurrent_rows=max_concurrent)
    
    # Return as CSV
    return result_df.to_csv(index=False)


@mcp.tool()
def search_product_taxonomy(product_type: str) -> list:
    """
    Search for matching taxonomy categories for a product type.
    
    Args:
        product_type: Type of product/software (e.g., "CRM Software", "Security Platform")
    
    Returns:
        List of matching taxonomy categories
    """
    from config.reference import get_product_attributes_list
    
    attributes = get_product_attributes_list()
    
    # Simple keyword matching
    product_type_lower = product_type.lower()
    matches = [attr for attr in attributes if any(word in attr.lower() for word in product_type_lower.split())]
    
    return matches[:10]  # Top 10 matches


@mcp.tool()
def get_vendor_info(vendor_name: str, vendor_url: str) -> dict:
    """
    Get detailed information about a vendor company.
    
    Args:
        vendor_name: Name of the vendor
        vendor_url: Vendor's website
    
    Returns:
        Vendor details including legal name, acquiring company, social links
    """
    return enrich_vendor(vendor_name, vendor_url)['vendor_info']


@mcp.tool()
def get_product_info(product_name: str, product_url: str) -> dict:
    """
    Get detailed information about a product.
    
    Args:
        product_name: Name of the product
        product_url: Product's URL
    
    Returns:
        Product details including type, users, tasks, features
    """
    return enrich_vendor("", "", product_name, product_url)['product_info']


if __name__ == "__main__":
    # Run MCP server
    mcp.run(transport="streamable-http")


