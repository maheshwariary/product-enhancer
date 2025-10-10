"""
Centralized prompt templates for LLM calls
All prompts in one place for easy modification and version control
"""

PROMPTS = {
    # =============================================================================
    # Vendor Information Extraction
    # =============================================================================
    "vendor_info": """Extract vendor information for:
Vendor: {vendor_name}
Vendor URL: {vendor_url}
Product: {product_name}
Product URL: {product_url}

Find the following information about this vendor:
1. Legal Vendor Name (official legal entity name)
2. Official Vendor Website (canonical URL)
3. Acquiring Company Name (if the company was acquired, otherwise "N/A")
4. Wikipedia link (if available, otherwise "N/A")
5. LinkedIn profile (company LinkedIn URL, otherwise "N/A")
6. Founded Year (year company was founded, otherwise "N/A")

Research using the provided information and your knowledge base.

Return ONLY a JSON object with these EXACT keys:
{{
    "Legal_Vendor_Name": "",
    "Official_Vendor_Website": "",
    "Acquiring_Company_Name": "",
    "Wikipedia_link": "",
    "LinkedIn_profile": "",
    "Founded_Year": ""
}}

No markdown, no explanations, just the JSON object.""",

    # =============================================================================
    # Product Information Extraction
    # =============================================================================
    "product_info": """Analyze this product and extract key information:

Product Name: {product_name}
Product URL: {product_url}

Extract the following:
1. Product_name (official product name)
2. Product_Link (canonical URL)
3. Type_of_Product (e.g., "CRM Software", "Security Platform", "HR Management System")
4. Type_of_users (target audience, e.g., "Enterprise IT Teams", "Small Business Owners")
5. Tasks_a_user_can_perform (main tasks users can do, comma-separated)
6. Product_features (key features, comma-separated)

Research using the provided URL and your knowledge.

Return ONLY a JSON object with these EXACT keys:
{{
    "Product_name": "",
    "Product_Link": "",
    "Type_of_Product": "",
    "Type_of_users": "",
    "Tasks_a_user_can_perform": "",
    "Product_features": ""
}}

No markdown, no explanations, just the JSON object.""",

    # =============================================================================
    # Taxonomy Matching
    # =============================================================================
    "taxonomy_match": """Product: {product_name}
Type: {software_type}

Based on the available categories provided in the system instructions, identify the top 2 most relevant taxonomy matches.

Return ONLY JSON in this exact format:
{{
    "Top_Match_1": {{"Taxonomy Name": "exact category from list"}},
    "Top_Match_2": {{"Taxonomy Name": "exact category from list"}}
}}

No markdown, no explanations, just the JSON object.""",

    # =============================================================================
    # Attribute Matching
    # =============================================================================
    "attribute_match": """Product: {product_name}
Type: {software_type}

From the available attributes provided, select the 3 most relevant attributes for this product.

Return ONLY JSON in this exact format:
{{
    "Top_Attribute_1": {{"Attribute Name": "..."}},
    "Top_Attribute_2": {{"Attribute Name": "..."}},
    "Top_Attribute_3": {{"Attribute Name": "..."}}
}}

No markdown, no explanations, just the JSON object."""
}


def get_prompt(prompt_name: str, **kwargs) -> str:
    """
    Get a formatted prompt template
    
    Args:
        prompt_name: Name of the prompt template
        **kwargs: Variables to format into the prompt
        
    Returns:
        Formatted prompt string
    """
    template = PROMPTS.get(prompt_name)
    if not template:
        raise ValueError(f"Prompt '{prompt_name}' not found")
    
    return template.format(**kwargs)