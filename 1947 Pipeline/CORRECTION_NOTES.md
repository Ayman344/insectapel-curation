# Pass 2 Correction Notes

**Date:** 2026-06-15

## Actions performed

1. HIGH-risk `first_segment` and `first_word` Pass 2 rescues reclassified as `PARTIAL_MATCH`.
2. `generate_smart_variants()` updated to skip root fallbacks for derivative names.
3. `resolved_chemicals_final.xlsx` re-exported with corrected sheets and counts.
4. Structure HTML regenerated for fully resolved compounds only.
5. PDF report refreshed with post-correction statistics.

## Status counts (after correction)

| Status | Count |
|--------|------:|
| RESOLVED_PASS1 | 4014 |
| RESOLVED_PASS2 (valid) | 637 |
| **Total fully resolved** | **4651 (65.6%)** |
| PARTIAL_MATCH | 526 |
| FAILED_BOTH_PASSES | 1626 |
| IRREGULAR_SKIPPED | 286 |

## Reclassification

- Rows moved from `RESOLVED_PASS2` to `PARTIAL_MATCH`: **526**
- Nominal resolved before correction: **5177**

### PARTIAL_MATCH by original strategy

- `first_segment`: 513
- `first_word`: 13

## Pass 2 logic fix

Root fallback strategies (`first_segment`, `first_word`) are now suppressed when:

- Name matches acid + ester or acid + salt pattern
- Comma suffix indicates a derivative (ester, salt, carbonate, etc.)
- Name matches multi-ester pattern
- Acid-ester flip variants were already generated for the name

## Output files

- `resolved_chemicals_final.xlsx` (corrected)
- `resolved_structures_corrected.html`
- `Chemical_Name_Resolution_Report.pdf` (updated)
- `first_segment_validation.xlsx` (run `validate_first_segment.py` to refresh)

## PARTIAL_MATCH semantics

These rows retain SMILES and resolved names for audit/review but are excluded
from `All_Resolved` and the structure HTML gallery because the structure
likely corresponds to a parent compound, not the full derivative name.
