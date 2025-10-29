"""
Test taxonomy validation (no Bedrock needed)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config.reference import initialize_reference_data, get_taxonomy_list

os.environ['DATA_DIR'] = './data'

def test_validation():
    """Test if validation works"""
    
    print("=== LOADING DATA ===")
    initialize_reference_data()
    taxonomy_list = get_taxonomy_list()
    print(f"✅ Loaded {len(taxonomy_list)} taxonomies\n")
    
    # Simulate what LLM might return
    test_cases = [
        {
            "name": "Exact match (should pass)",
            "match": "Software > Apps Development and Deployment > Application Development Software > Business Rules Management"
        },
        {
            "name": "Partial match (should fail)",
            "match": "Software > Apps Development"
        },
        {
            "name": "Paraphrased (should fail)",
            "match": "Application Development Software"
        },
        {
            "name": "Identity and Access (likely what LLM would return)",
            "match": "Software > Enterprise Applications > Identity and Access Management"
        }
    ]
    
    print("=== TESTING VALIDATION ===\n")
    for test in test_cases:
        match = test["match"]
        is_valid = match in taxonomy_list
        
        if is_valid:
            print(f"✅ {test['name']}")
            print(f"   '{match}' - VALID\n")
        else:
            print(f"❌ {test['name']}")
            print(f"   '{match}' - INVALID")
            
            # Try to find similar
            similar = [t for t in taxonomy_list if any(word.lower() in t.lower() for word in match.split())][:5]
            if similar:
                print(f"   Similar entries found:")
                for s in similar:
                    print(f"     - {s}")
            print()
    
    # Search for Identity-related taxonomies
    print("=== IDENTITY-RELATED TAXONOMIES ===")
    identity_taxonomies = [t for t in taxonomy_list if 'identity' in t.lower() or 'access' in t.lower()]
    print(f"Found {len(identity_taxonomies)} identity/access-related taxonomies:\n")
    for i, tax in enumerate(identity_taxonomies[:10], 1):
        print(f"  {i}. {tax}")

if __name__ == "__main__":
    test_validation()