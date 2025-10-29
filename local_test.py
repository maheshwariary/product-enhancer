"""
Local test script to run the enrichment pipeline
NO AWS/cloud dependencies - runs completely locally
"""
import sys
import os
import pandas as pd
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set data directory
os.environ['DATA_DIR'] = str(Path(__file__).parent / 'data')

from pipeline.orchestrator import process_dataframe_batch
from config.reference import initialize_reference_data, get_reference_stats

def main():
    print("=" * 80)
    print("Clio AI - Local Test Runner")
    print("=" * 80)
    
    # Initialize reference data
    print("\nLoading reference data...")
    initialize_reference_data()
    
    # Show stats
    stats = get_reference_stats()
    print(f"   [OK] Products loaded: {stats['products_count']:,}")
    print(f"   [OK] Intents loaded: {stats['intents_count']:,}")
    print(f"   [OK] Taxonomy loaded: {stats.get('taxonomy_count', 0):,}")
    print(f"   [OK] Attributes extracted: {stats['attributes_count']:,}")
    
    # Create test input
    print("\nCreating test input...")
    test_data = {
        'vendor_name': [
            'Salesforce',
            'Microsoft',
            'Oracle'
        ],
        'vendor_url': [
            'salesforce.com',
            'microsoft.com',
            'oracle.com'
        ],
        'product_name': [
            'Sales Cloud',
            'Office 365',
            'Oracle Database'
        ],
        'product_url': [
            'https://www.salesforce.com/products/sales-cloud',
            'https://www.microsoft.com/en-us/microsoft-365',
            'https://www.oracle.com/database/'
        ]
    }
    
    input_df = pd.DataFrame(test_data)
    print(f"   [OK] Created {len(input_df)} test rows")
    print("\nInput:")
    print(input_df.to_string(index=False))
    
    # Process
    print("\nProcessing (this may take 30-60 seconds)...")
    print("   [Each row requires 3-4 LLM calls]")
    
    try:
        output_df = process_dataframe_batch(input_df, max_concurrent_rows=3)
        
        print("\n[SUCCESS] Processing complete!")
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        
        # Show key columns
        key_columns = [
            'vendor_name',
            'product_name',
            'legal_vendor_name',
            'product_type',
            'taxonomy_match_1',
            'taxonomy_match_2',
            'attribute_1',
            'attribute_2',
            'attribute_3'
        ]
        
        # Filter to existing columns
        display_cols = [col for col in key_columns if col in output_df.columns]
        
        print("\nVendor & Product Info:")
        print(output_df[['vendor_name', 'legal_vendor_name', 'product_name', 'product_type']].to_string(index=False))
        
        print("\nTaxonomy Matches:")
        taxonomy_cols = [col for col in ['vendor_name', 'taxonomy_match_1', 'taxonomy_match_2'] if col in output_df.columns]
        print(output_df[taxonomy_cols].to_string(index=False))
        
        print("\nAttribute Matches:")
        attr_cols = [col for col in ['vendor_name', 'attribute_1', 'attribute_2', 'attribute_3'] if col in output_df.columns]
        print(output_df[attr_cols].to_string(index=False))
        
        # Save full output
        output_path = Path(__file__).parent / 'deploy' / 'test_output_local.csv'
        output_df.to_csv(output_path, index=False)
        print(f"\nFull results saved to: {output_path}")
        
        # Check for N/A values
        print("\n" + "=" * 80)
        print("VALIDATION CHECK")
        print("=" * 80)
        
        taxonomy_na_count = (output_df['taxonomy_match_1'] == 'N/A').sum()
        attribute_na_count = (output_df['attribute_1'] == 'N/A').sum()
        
        if taxonomy_na_count > 0:
            print(f"[WARNING] Taxonomy: {taxonomy_na_count}/{len(output_df)} rows returned N/A")
        else:
            print(f"[OK] Taxonomy: All rows have valid matches!")
        
        if attribute_na_count > 0:
            print(f"[WARNING] Attributes: {attribute_na_count}/{len(output_df)} rows returned N/A")
        else:
            print(f"[OK] Attributes: All rows have valid matches!")
        
    except Exception as e:
        print(f"\n[ERROR] Error during processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()

