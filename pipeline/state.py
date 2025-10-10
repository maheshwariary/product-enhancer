"""
State definitions for LangGraph pipeline
This file preserves your battle-tested state schema
"""
from typing import TypedDict, Optional, List, Dict, Any
from typing_extensions import NotRequired


class VendorProductState(TypedDict):
    """
    State for vendor/product lookup pipeline
    
    This state flows through the entire LangGraph pipeline
    """
    
    # Input fields (required)
    row_id: str
    vendor_name: str
    vendor_url: str
    product_name: str
    product_url: str
    
    # Intermediate results (populated by nodes)
    vendor_details: NotRequired[Optional[Dict[str, Any]]]
    product_details: NotRequired[Optional[Dict[str, Any]]]
    software_type: NotRequired[Optional[str]]
    
    # Parallel matching results
    taxonomy_matches: NotRequired[Optional[List[Dict[str, Any]]]]
    attribute_matches: NotRequired[Optional[List[Dict[str, Any]]]]
    platform_matches: NotRequired[Optional[List[Dict[str, Any]]]]
    
    # Final output
    result: NotRequired[Optional[Dict[str, Any]]]
    
    # Metadata
    errors: List[str]
    retry_count: int
    processing_time: NotRequired[float]