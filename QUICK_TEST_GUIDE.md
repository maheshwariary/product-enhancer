# Quick Test Guide

## Test the Implementation in 3 Steps

### Step 1: Activate Environment
```powershell
cd "C:\Users\mahes\OneDrive\Documents\Product Matching Agent\clio-agentcore"
..\venv\Scripts\Activate.ps1
```

### Step 2: Run Test
```powershell
python local_test.py
```

### Step 3: Check Results
```powershell
# View full output
cat deploy\test_output_local.csv

# Or open in Excel/CSV viewer
```

---

## What You Should See

### ✅ Success Indicators:
```
📚 Loading reference data...
   ✓ Products loaded: 20,825
   ✓ Intents loaded: 10,859
   ✓ Taxonomy loaded: 169
   ✓ Attributes extracted: [large number]

✅ Processing complete!

🔍 VALIDATION CHECK
✅ Taxonomy: All rows have valid matches!
✅ Attributes: All rows have valid matches!
```

### Example Output:
```
Vendor: Salesforce
Taxonomy 1: Software > Enterprise Applications > Customer Relationship Management Applications
Taxonomy 2: Software > Enterprise Applications > Sales and Marketing > Sales
Attribute 1: Business Management
Attribute 2: CRM
Attribute 3: Software as a Service (SaaS)
```

---

## Troubleshooting

### ❌ If you see "N/A" values:

1. **Check reference data:**
```python
python -c "
from config.reference import initialize_reference_data, get_reference_stats
import os
os.environ['DATA_DIR'] = 'data'
initialize_reference_data()
print(get_reference_stats())
"
```

Expected output:
```python
{
  'products_count': 20825,
  'intents_count': 10859,
  'taxonomy_count': 169,
  'attributes_count': [large number],
  'products_loaded': True,
  'intents_loaded': True,
  'taxonomy_loaded': True
}
```

2. **Check files exist:**
```powershell
dir data\*.csv
```

Should show:
- `products.csv`
- `intents.csv`
- `taxonomy.csv`

3. **Check for errors:**
Look for error messages in the console output.

---

## What Changed?

### Before Fix:
```csv
taxonomy_match_1,taxonomy_match_2,attribute_1,attribute_2,attribute_3
N/A,N/A,N/A,N/A,N/A
```

### After Fix:
```csv
taxonomy_match_1,taxonomy_match_2,attribute_1,attribute_2,attribute_3
Software > Enterprise Applications > CRM,Software > Enterprise Applications > Sales,Business Management,CRM,SaaS
```

---

## Files Modified

1. **`config/reference.py`** - Added taxonomy loading
2. **`pipeline/nodes.py`** - Fixed taxonomy/attribute matching

---

## Performance Notes

- **Per Row:** ~30-60 seconds (4 LLM calls)
- **3 Rows:** ~60-90 seconds total
- **Caching:** Repeat queries are instant

---

*Quick Reference - October 16, 2025*







