"""
Processing nodes for LangGraph pipeline
All nodes in one file for clarity and maintainability
"""
import json
import logging
from typing import Dict, Any

from .state import VendorProductState
from .bedrock_client import get_llm_manager, extract_json_from_response
from .cache_manager import get_cache_manager
from config.prompts import PROMPTS
from config.reference import get_product_attributes_list, get_product_context

logger = logging.getLogger(__name__)


# =============================================================================
# NODE 1: Vendor Info Fetching
# =============================================================================

async def fetch_vendor_info_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Fetch vendor information using LLM
    
    Extracts: Legal name, website, acquiring company, Wikipedia, LinkedIn, founded year
    Cache TTL: 7 days (vendor info changes rarely)
    """
    vendor_name = state["vendor_name"]
    vendor_url = state["vendor_url"]
    product_name = state["product_name"]
    product_url = state["product_url"]
    
    # Check cache first
    cache = get_cache_manager()
    cached = cache.get(
        type="vendor_info",
        vendor_name=vendor_name,
        vendor_url=vendor_url
    )
    
    if cached:
        return {"vendor_details": cached}
    
    llm = get_llm_manager()
    
    # Use centralized prompt
    prompt = PROMPTS["vendor_info"].format(
        vendor_name=vendor_name,
        vendor_url=vendor_url,
        product_name=product_name,
        product_url=product_url
    )
    
    try:
        response = await llm.call_async(prompt, model="sonnet")
        
        if not response:
            return {
                "vendor_details": None,
                "errors": state.get("errors", []) + ["Vendor info fetch failed"]
            }
        
        # Parse JSON
        json_str = extract_json_from_response(response)
        vendor_details = json.loads(json_str)
        
        # Cache result (7 days TTL)
        cache.set(
            vendor_details,
            ttl_seconds=7 * 24 * 3600,
            type="vendor_info",
            vendor_name=vendor_name,
            vendor_url=vendor_url
        )
        
        return {"vendor_details": vendor_details}
        
    except Exception as e:
        logger.error(f"Vendor fetch error: {e}")
        return {
            "vendor_details": None,
            "errors": state.get("errors", []) + [f"Vendor error: {str(e)}"]
        }


# =============================================================================
# NODE 2: Product Info Fetching
# =============================================================================

async def fetch_product_details_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Fetch product details using LLM
    
    Extracts: Product name, link, type, users, tasks, features
    Cache TTL: 7 days
    """
    product_name = state["product_name"]
    product_url = state["product_url"]
    
    # Check cache
    cache = get_cache_manager()
    cached = cache.get(
        type="product_details",
        product_url=product_url
    )
    
    if cached:
        return {"product_details": cached}
    
    llm = get_llm_manager()
    
    prompt = PROMPTS["product_info"].format(
        product_name=product_name,
        product_url=product_url
    )
    
    try:
        response = await llm.call_async(prompt, model="sonnet")
        
        if not response:
            return {
                "product_details": None,
                "errors": state.get("errors", []) + ["Product fetch failed"]
            }
        
        json_str = extract_json_from_response(response)
        product_details = json.loads(json_str)
        
        # Cache (7 days TTL)
        cache.set(
            product_details,
            ttl_seconds=7 * 24 * 3600,
            type="product_details",
            product_url=product_url
        )
        
        return {"product_details": product_details}
        
    except Exception as e:
        logger.error(f"Product fetch error: {e}")
        return {
            "product_details": None,
            "errors": state.get("errors", []) + [f"Product error: {str(e)}"]
        }


# =============================================================================
# NODE 3: Extract Software Type
# =============================================================================

def extract_software_type_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Extract software type from product details
    
    This is a synchronous node (no LLM call)
    """
    product_details = state.get("product_details")
    
    if not product_details:
        return {
            "software_type": "N/A",
            "errors": state.get("errors", []) + ["No product details available"]
        }
    
    software_type = product_details.get("Type_of_Product", "N/A")
    
    # Clean software type
    if isinstance(software_type, list):
        software_type = ", ".join(software_type)
    
    return {"software_type": software_type if software_type else "N/A"}


# =============================================================================
# NODE 4: Taxonomy Matching
# =============================================================================

async def find_taxonomy_matches_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Match product to taxonomy using reference data
    
    Uses products.csv to find top 2 matches
    Cache TTL: 1 day
    """
    software_type = state.get("software_type", "N/A")
    product_name = state["product_name"]
    
    # Get reference data context
    product_context = get_product_context(product_name)
    available_attributes = get_product_attributes_list()
    
    if not available_attributes:
        logger.warning("No reference data available for taxonomy matching")
        return {
            "taxonomy_matches": [
                {"Taxonomy Name": "N/A - Reference data not loaded"},
                {"Taxonomy Name": "N/A - Reference data not loaded"}
            ]
        }
    
    # Check cache
    cache = get_cache_manager()
    cached = cache.get(
        type="taxonomy_match",
        software_type=software_type,
        product_name=product_name
    )
    
    if cached:
        return {"taxonomy_matches": cached}
    
    llm = get_llm_manager()
    
    # Build prompt with reference data
    attributes_list = "\n".join([f"- {attr}" for attr in available_attributes[:50]])
    
    system_prompt = f"""You are matching products to taxonomy categories.

Available Product Attributes/Categories from our database:
{attributes_list}

{f"Reference Product Info:\\n{product_context}" if product_context else ""}

Find the 2 most relevant categories for this product."""
    
    prompt = f"""Product: {product_name}
Type: {software_type}

Based on the available categories above, identify the top 2 most relevant taxonomy matches.

Return ONLY JSON:
{{
    "Top_Match_1": {{"Taxonomy Name": "exact category from list"}},
    "Top_Match_2": {{"Taxonomy Name": "exact category from list"}}
}}"""
    
    try:
        response = await llm.call_async(
            prompt,
            system_prompt=system_prompt,
            model="haiku"  # Use faster model for matching
        )
        
        if not response:
            return {
                "taxonomy_matches": [{"Taxonomy Name": "N/A"}, {"Taxonomy Name": "N/A"}]
            }
        
        json_str = extract_json_from_response(response)
        matches = json.loads(json_str)
        
        result = [
            matches.get("Top_Match_1", {}),
            matches.get("Top_Match_2", {})
        ]
        
        # Cache result (1 day TTL)
        cache.set(
            result,
            ttl_seconds=24 * 3600,
            type="taxonomy_match",
            software_type=software_type,
            product_name=product_name
        )
        
        return {"taxonomy_matches": result}
        
    except Exception as e:
        logger.error(f"Taxonomy matching error: {e}")
        return {
            "taxonomy_matches": [{"Taxonomy Name": "N/A"}, {"Taxonomy Name": "N/A"}]
        }


# =============================================================================
# NODE 5: Attribute Matching
# =============================================================================

async def find_attribute_matches_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Find attribute matches using reference data
    
    Returns top 3 attribute matches
    Cache TTL: 1 day
    """
    software_type = state.get("software_type", "N/A")
    product_name = state["product_name"]
    
    available_attributes = get_product_attributes_list()
    
    if not available_attributes:
        return {
            "attribute_matches": [
                {"Attribute Name": "N/A"},
                {"Attribute Name": "N/A"},
                {"Attribute Name": "N/A"}
            ]
        }
    
    cache = get_cache_manager()
    cached = cache.get(
        type="attribute_match",
        software_type=software_type,
        product_name=product_name
    )
    
    if cached:
        return {"attribute_matches": cached}
    
    llm = get_llm_manager()
    
    attributes_list = "\n".join([f"- {attr}" for attr in available_attributes[:100]])
    
    prompt = f"""Product: {product_name}
Type: {software_type}

From these available attributes:
{attributes_list}

Select the 3 most relevant attributes for this product.

Return ONLY JSON:
{{
    "Top_Attribute_1": {{"Attribute Name": "..."}},
    "Top_Attribute_2": {{"Attribute Name": "..."}},
    "Top_Attribute_3": {{"Attribute Name": "..."}}
}}"""
    
    try:
        response = await llm.call_async(prompt, model="haiku")
        
        if not response:
            return {
                "attribute_matches": [
                    {"Attribute Name": "N/A"},
                    {"Attribute Name": "N/A"},
                    {"Attribute Name": "N/A"}
                ]
            }
        
        json_str = extract_json_from_response(response)
        matches = json.loads(json_str)
        
        result = [
            matches.get("Top_Attribute_1", {}),
            matches.get("Top_Attribute_2", {}),
            matches.get("Top_Attribute_3", {})
        ]
        
        cache.set(
            result,
            ttl_seconds=24 * 3600,
            type="attribute_match",
            software_type=software_type,
            product_name=product_name
        )
        
        return {"attribute_matches": result}
        
    except Exception as e:
        logger.error(f"Attribute matching error: {e}")
        return {
            "attribute_matches": [
                {"Attribute Name": "N/A"},
                {"Attribute Name": "N/A"},
                {"Attribute Name": "N/A"}
            ]
        }


# =============================================================================
# NODE 6: Platform Taxonomy (Simplified)
# =============================================================================

async def find_platform_taxonomy_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Platform taxonomy matching
    
    Simplified version - can be extended based on needs
    """
    # Placeholder for now
    return {
        "platform_matches": [
            {"Taxonomy Code": "Software"},
            {"Taxonomy Code": "SaaS"}
        ]
    }


# =============================================================================
# NODE 7: Format Output
# =============================================================================

def format_output_node(state: VendorProductState) -> Dict[str, Any]:
    """
    Format final output with all enriched data
    
    This is the final node that produces the output row
    """
    # Extract all results
    vendor_details = state.get("vendor_details", {}) or {}
    product_details = state.get("product_details", {}) or {}
    taxonomy_matches = state.get("taxonomy_matches", [])
    attribute_matches = state.get("attribute_matches", [])
    platform_matches = state.get("platform_matches", [])
    
    # Build output dictionary
    result = {
        # Original input
        "vendor_name": state["vendor_name"],
        "vendor_url": state["vendor_url"],
        "product_name": state["product_name"],
        "product_url": state["product_url"],
        
        # Vendor info
        "legal_vendor_name": vendor_details.get("Legal_Vendor_Name", "N/A"),
        "official_vendor_website": vendor_details.get("Official_Vendor_Website", "N/A"),
        "acquiring_company": vendor_details.get("Acquiring_Company_Name", "N/A"),
        "wikipedia_link": vendor_details.get("Wikipedia_link", "N/A"),
        "linkedin_profile": vendor_details.get("LinkedIn_profile", "N/A"),
        "founded_year": vendor_details.get("Founded_Year", "N/A"),
        
        # Product info
        "product_type": product_details.get("Type_of_Product", "N/A"),
        "product_users": product_details.get("Type_of_users", "N/A"),
        "product_tasks": product_details.get("Tasks_a_user_can_perform", "N/A"),
        "product_features": product_details.get("Product_features", "N/A"),
        
        # Taxonomy matches (JSON string)
        "taxonomy_match_1": taxonomy_matches[0].get("Taxonomy Name", "N/A") if len(taxonomy_matches) > 0 else "N/A",
        "taxonomy_match_2": taxonomy_matches[1].get("Taxonomy Name", "N/A") if len(taxonomy_matches) > 1 else "N/A",
        
        # Attribute matches
        "attribute_1": attribute_matches[0].get("Attribute Name", "N/A") if len(attribute_matches) > 0 else "N/A",
        "attribute_2": attribute_matches[1].get("Attribute Name", "N/A") if len(attribute_matches) > 1 else "N/A",
        "attribute_3": attribute_matches[2].get("Attribute Name", "N/A") if len(attribute_matches) > 2 else "N/A",
        
        # Platform
        "platform_1": platform_matches[0].get("Taxonomy Code", "N/A") if len(platform_matches) > 0 else "N/A",
        "platform_2": platform_matches[1].get("Taxonomy Code", "N/A") if len(platform_matches) > 1 else "N/A",
        
        # Metadata
        "errors": "; ".join(state.get("errors", [])) if state.get("errors") else "None",
        "row_id": state["row_id"]
    }
    
    return {"result": result}