"""
Reference data loader for products.csv and intents.csv
Loads data once and provides lookup functions
"""
import os
import logging
import pandas as pd
from typing import List, Optional

logger = logging.getLogger(__name__)

# Global reference data
_products_df: Optional[pd.DataFrame] = None
_intents_df: Optional[pd.DataFrame] = None
_product_attributes: Optional[List[str]] = None


def initialize_reference_data():
    """
    Load reference data from CSV files
    Called once during Lambda cold start
    """
    global _products_df, _intents_df, _product_attributes
    
    if _products_df is not None:
        logger.info("Reference data already loaded")
        return
    
    try:
        data_dir = os.environ.get('DATA_DIR', '/app/data')
        
        # Load products.csv
        products_path = os.path.join(data_dir, 'products.csv')
        if os.path.exists(products_path):
            _products_df = pd.read_csv(products_path)
            logger.info(f"Loaded {len(_products_df)} products from {products_path}")
        else:
            logger.warning(f"Products file not found: {products_path}")
            _products_df = pd.DataFrame()
        
        # Load intents.csv
        intents_path = os.path.join(data_dir, 'intents.csv')
        if os.path.exists(intents_path):
            _intents_df = pd.read_csv(intents_path)
            logger.info(f"Loaded {len(_intents_df)} intents from {intents_path}")
        else:
            logger.warning(f"Intents file not found: {intents_path}")
            _intents_df = pd.DataFrame()
        
        # Extract unique product attributes
        if not _products_df.empty and 'PRODUCT_ATTRIBUTES' in _products_df.columns:
            attributes_set = set()
            for attrs in _products_df['PRODUCT_ATTRIBUTES'].dropna():
                if pd.notna(attrs):
                    for attr in str(attrs).split(','):
                        attr = attr.strip()
                        if attr:
                            attributes_set.add(attr)
            _product_attributes = sorted(list(attributes_set))
            logger.info(f"Extracted {len(_product_attributes)} unique product attributes")
        else:
            _product_attributes = []
            logger.warning("No product attributes found")
        
        logger.info("Reference data initialization complete")
        
    except Exception as e:
        logger.error(f"Error loading reference data: {e}", exc_info=True)
        # Initialize with empty dataframes on error
        _products_df = pd.DataFrame()
        _intents_df = pd.DataFrame()
        _product_attributes = []


def get_products_dataframe() -> pd.DataFrame:
    """Get the products DataFrame"""
    if _products_df is None:
        initialize_reference_data()
    return _products_df


def get_intents_dataframe() -> pd.DataFrame:
    """Get the intents DataFrame"""
    if _intents_df is None:
        initialize_reference_data()
    return _intents_df


def get_product_attributes_list() -> List[str]:
    """
    Get list of all unique product attributes
    
    Returns:
        List of attribute strings
    """
    if _product_attributes is None:
        initialize_reference_data()
    return _product_attributes or []


def get_product_context(product_name: str, top_n: int = 5) -> str:
    """
    Get context about a product from reference data
    
    Args:
        product_name: Product name to search for
        top_n: Number of similar products to return
        
    Returns:
        Formatted string with product context
    """
    if _products_df is None or _products_df.empty:
        return ""
    
    try:
        # Search for exact or partial matches
        matches = _products_df[
            _products_df['PRODUCT_NAME'].str.contains(product_name, case=False, na=False)
        ].head(top_n)
        
        if matches.empty:
            return ""
        
        # Format context
        context_lines = []
        for _, row in matches.iterrows():
            line = f"- {row['PRODUCT_NAME']}: {row.get('PRODUCT_DESCRIPTION', 'N/A')[:200]}"
            context_lines.append(line)
        
        return "\n".join(context_lines)
        
    except Exception as e:
        logger.error(f"Error getting product context: {e}")
        return ""


def search_products_by_name(product_name: str, limit: int = 10) -> pd.DataFrame:
    """
    Search products by name
    
    Args:
        product_name: Product name to search
        limit: Maximum results to return
        
    Returns:
        DataFrame with matching products
    """
    if _products_df is None or _products_df.empty:
        return pd.DataFrame()
    
    try:
        matches = _products_df[
            _products_df['PRODUCT_NAME'].str.contains(product_name, case=False, na=False)
        ].head(limit)
        return matches
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return pd.DataFrame()


def get_reference_stats() -> dict:
    """Get statistics about loaded reference data"""
    return {
        "products_count": len(_products_df) if _products_df is not None else 0,
        "intents_count": len(_intents_df) if _intents_df is not None else 0,
        "attributes_count": len(_product_attributes) if _product_attributes is not None else 0,
        "products_loaded": _products_df is not None,
        "intents_loaded": _intents_df is not None
    }