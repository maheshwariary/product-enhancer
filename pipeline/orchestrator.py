"""
LangGraph Pipeline Orchestrator
Defines the end-to-end enrichment pipeline with parallel processing
"""
import logging
import asyncio
from typing import Dict, Any
import pandas as pd
from langgraph.graph import StateGraph, END

from .state import VendorProductState
from .batch_processor import BatchProcessor
from .nodes import (
    fetch_vendor_info_node,
    fetch_product_details_node,
    extract_software_type_node,
    find_taxonomy_matches_node,
    find_attribute_matches_node,
    find_platform_taxonomy_node,
    format_output_node
)

logger = logging.getLogger(__name__)


async def parallel_fetch_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Node 1: Fetch vendor and product info in parallel
    Implements column-level parallelism within a row
    """
    vendor_task = fetch_vendor_info_node(state)
    product_task = fetch_product_details_node(state)
    
    vendor_result, product_result = await asyncio.gather(
        vendor_task,
        product_task,
        return_exceptions=True
    )
    
    # Handle exceptions
    merged = {}
    if isinstance(vendor_result, dict):
        merged.update(vendor_result)
    if isinstance(product_result, dict):
        merged.update(product_result)
    
    return merged


async def parallel_matching_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Node 3: Run all matching operations in parallel
    Implements column-level parallelism for taxonomy/attribute matching
    """
    taxonomy_task = find_taxonomy_matches_node(state)
    attribute_task = find_attribute_matches_node(state)
    platform_task = find_platform_taxonomy_node(state)
    
    taxonomy_result, attribute_result, platform_result = await asyncio.gather(
        taxonomy_task,
        attribute_task,
        platform_task,
        return_exceptions=True
    )
    
    # Merge results
    merged = {}
    if isinstance(taxonomy_result, dict):
        merged.update(taxonomy_result)
    if isinstance(attribute_result, dict):
        merged.update(attribute_result)
    if isinstance(platform_result, dict):
        merged.update(platform_result)
    
    return merged


def build_pipeline_graph() -> StateGraph:
    """
    Build the complete LangGraph pipeline
    
    Pipeline flow:
    1. parallel_fetch: Get vendor + product info simultaneously
    2. extract_type: Extract software type from product details
    3. parallel_matching: Match taxonomy + attributes simultaneously
    4. format_output: Format final enriched result
    """
    graph = StateGraph(VendorProductState)
    
    # Add nodes
    graph.add_node("parallel_fetch", parallel_fetch_node)
    graph.add_node("extract_type", extract_software_type_node)
    graph.add_node("parallel_matching", parallel_matching_node)
    graph.add_node("format_output", format_output_node)
    
    # Define edges (pipeline flow)
    graph.set_entry_point("parallel_fetch")
    graph.add_edge("parallel_fetch", "extract_type")
    graph.add_edge("extract_type", "parallel_matching")
    graph.add_edge("parallel_matching", "format_output")
    graph.add_edge("format_output", END)
    
    # Compile
    compiled = graph.compile()
    
    logger.info("Pipeline graph compiled successfully")
    return compiled


async def run_pipeline_for_row(row: Dict[str, Any], row_id: str) -> Dict[str, Any]:
    """
    Execute pipeline for a single row
    
    Args:
        row: Dictionary with vendor_name, vendor_url, product_name, product_url
        row_id: Unique identifier for this row
        
    Returns:
        Enriched result dictionary
    """
    # Initialize state
    initial_state: VendorProductState = {
        "row_id": row_id,
        "vendor_name": row.get("vendor_name", ""),
        "vendor_url": row.get("vendor_url", ""),
        "product_name": row.get("product_name", ""),
        "product_url": row.get("product_url", ""),
        "errors": [],
        "retry_count": 0
    }
    
    # Build and run graph
    graph = build_pipeline_graph()
    
    try:
        result_state = await graph.ainvoke(initial_state)
        return result_state.get("result", {})
        
    except Exception as e:
        logger.error(f"Pipeline failed for row {row_id}: {e}")
        return {
            "error": str(e),
            "row_id": row_id,
            "vendor_name": row.get("vendor_name", ""),
            "product_name": row.get("product_name", "")
        }


def process_dataframe_batch(
    df: pd.DataFrame,
    max_concurrent_rows: int = 20
) -> pd.DataFrame:
    """
    Process entire DataFrame through pipeline with row-level parallelism
    
    This is the main entry point for batch processing.
    
    Args:
        df: Input DataFrame with columns: vendor_name, vendor_url, product_name, product_url
        max_concurrent_rows: Maximum number of rows to process simultaneously
        
    Returns:
        Enriched DataFrame with all results
    """
    logger.info(f"Starting batch processing of {len(df)} rows with max_concurrent={max_concurrent_rows}")
    
    # Use BatchProcessor for row-level parallelism
    processor = BatchProcessor(
        max_concurrent=max_concurrent_rows,
        progress_bar=False  # Disable for Lambda
    )
    
    results_df = processor.process_batch_sync(df)
    
    logger.info(f"Batch processing complete: {len(results_df)} rows processed")
    
    return results_df