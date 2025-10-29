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
from config.reference import (
    get_product_attributes_list,
    get_product_context,
    get_taxonomy_list,
    get_taxonomy_with_definitions
)

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
    """
    software_type = state.get("software_type", "N/A")
    product_name = state["product_name"]
    
    from config.reference import get_taxonomy_list
    
    taxonomy_list = get_taxonomy_list()
    
    if not taxonomy_list:
        logger.warning("No taxonomy data available")
        return {
            "taxonomy_matches": [
                {"Taxonomy Name": "N/A"},
                {"Taxonomy Name": "N/A"}
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
    
    # Build numbered list of ALL taxonomies
    taxonomy_text = "\n".join([f"{i}. {tax}" for i, tax in enumerate(taxonomy_list, 1)])
    
    system_prompt = """You are a taxonomy classification expert. You match products to the most relevant taxonomy categories from a provided list.

CRITICAL RULES:
1. You MUST return the EXACT taxonomy text from the numbered list - copy it character-for-character
2. Do NOT paraphrase, shorten, or modify the taxonomy names
3. Do NOT make up new taxonomy names
4. If unsure, pick the closest match from the list"""
    
    prompt = f"""Product Name: {product_name}
Product Type: {software_type}

Available Taxonomy Categories (choose from this list):
{taxonomy_text}

Task: Select the 2 most relevant taxonomy categories for this product.

Examples of correct format:
- For a CRM product: "Software > Enterprise Applications > Customer Relationship Management Applications"  
- For security software: "Software > Software Infrastructure > Security > Identity and Access Management"

Return ONLY this JSON (copy taxonomy names EXACTLY from the numbered list above):
{{
    "match_1": "EXACT taxonomy from list",
    "match_2": "EXACT taxonomy from list"
}}"""
    
    try:
        response = await llm.call_async(
            prompt,
            system_prompt=system_prompt,
            model="sonnet"  # Use smarter model for better accuracy
        )
        
        if not response:
            return {
                "taxonomy_matches": [{"Taxonomy Name": "N/A"}, {"Taxonomy Name": "N/A"}]
            }
        
        json_str = extract_json_from_response(response)
        matches = json.loads(json_str)
        
        # Extract matches (handle both formats)
        match1 = matches.get("match_1") or matches.get("Top_Match_1", {}).get("Taxonomy Name", "N/A")
        match2 = matches.get("match_2") or matches.get("Top_Match_2", {}).get("Taxonomy Name", "N/A")
        
        # Validate exact match
        if match1 not in taxonomy_list:
            logger.warning(f"Invalid taxonomy returned: '{match1}'")
            # Try fuzzy match
            for tax in taxonomy_list:
                if match1.lower() in tax.lower() or tax.lower() in match1.lower():
                    logger.info(f"Fuzzy matched '{match1}' to '{tax}'")
                    match1 = tax
                    break
            else:
                match1 = "N/A"
        
        if match2 not in taxonomy_list:
            logger.warning(f"Invalid taxonomy returned: '{match2}'")
            for tax in taxonomy_list:
                if match2.lower() in tax.lower() or tax.lower() in match2.lower():
                    logger.info(f"Fuzzy matched '{match2}' to '{tax}'")
                    match2 = tax
                    break
            else:
                match2 = "N/A"
        
        result = [
            {"Taxonomy Name": match1},
            {"Taxonomy Name": match2}
        ]
        
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
    
    Returns top 3 attribute matches from products.csv
    Cache TTL: 1 day
    """
    software_type = state.get("software_type", "N/A")
    product_name = state["product_name"]
    
    # Get attributes list from reference data
    from config.reference import get_product_attributes_list
    
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
    
    # Build attribute list (use top 200 most common)
    attributes_sample = available_attributes[:200]
    attributes_text = "\n".join([f"{i}. {attr}" for i, attr in enumerate(attributes_sample, 1)])
    
    system_prompt = f"""You are matching products to attributes.

Available Product Attributes:
{attributes_text}

CRITICAL: You MUST return ONLY the EXACT attribute names from the list above. Do not paraphrase or modify them."""
    
    prompt = f"""Product: {product_name}
Type: {software_type}

Based on the available attributes above, identify the top 3 most relevant attributes for this product.

Return ONLY JSON in this exact format (use the EXACT attribute names from the list):
{{
    "Top_Attribute_1": {{"Attribute Name": "exact attribute from list"}},
    "Top_Attribute_2": {{"Attribute Name": "exact attribute from list"}},
    "Top_Attribute_3": {{"Attribute Name": "exact attribute from list"}}
}}

IMPORTANT: Copy the attribute names EXACTLY as they appear in the list. Do not modify or paraphrase."""
    
    try:
        response = await llm.call_async(prompt, system_prompt=system_prompt, model="haiku")
        
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
        
        # Extract matches
        attr1 = matches.get("Top_Attribute_1", {}).get("Attribute Name", "N/A")
        attr2 = matches.get("Top_Attribute_2", {}).get("Attribute Name", "N/A")
        attr3 = matches.get("Top_Attribute_3", {}).get("Attribute Name", "N/A")
        
        # Verify matches are in our attributes list (exact match validation)
        if attr1 not in available_attributes:
            logger.warning(f"LLM returned invalid attribute: {attr1}")
            attr1 = "N/A"
        if attr2 not in available_attributes:
            logger.warning(f"LLM returned invalid attribute: {attr2}")
            attr2 = "N/A"
        if attr3 not in available_attributes:
            logger.warning(f"LLM returned invalid attribute: {attr3}")
            attr3 = "N/A"
        
        result = [
            {"Attribute Name": attr1},
            {"Attribute Name": attr2},
            {"Attribute Name": attr3}
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