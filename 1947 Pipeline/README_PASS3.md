# Pass 3 — Validation and Advanced Rescue

## Overview

| Step | Script | Where | Output |
|------|--------|-------|--------|
| 1 | `pass3_local_validation.py` | Local PC | `dataset_ready_for_ccast.xlsx` |
| 2 | `pass3_ccast_validation.ipynb` | CCAST GPU Jupyter | `dataset_from_ccast.xlsx` |
| 3 | `pass3_curation_app.py` | Local PC (Streamlit) | `dataset_curated_final.xlsx` |

## Prerequisites (local)

```powershell
cd Decoding_Names
pip install pandas openpyxl rdkit-pypi python-dotenv requests chemspipy jellyfish streamlit
```

## ChemSpider API key

The key is stored in **`.env`** in this folder (gitignored — not committed to git).  
You do **not** need to create it manually if it is already present.

**CCAST GPU notebook does NOT need ChemSpider or `.env`.**  
ChemSpider runs only on your **local PC** during `pass3_local_validation.py` rescue step.

---

## Step 1 — Local validation and rescue

### SMARTS only (recommended first run)

Validates **all 4,651** `RESOLVED_PASS1` + `RESOLVED_PASS2` rows:

```powershell
python pass3_local_validation.py --smarts-only
```

**Latest SMARTS results:**
- PASS: ~1,944
- SKIP (no rule): ~2,170 → kept as `VALIDATED_OK`
- FAIL: ~537 → `NEEDS_REVIEW`

### Full rescue (OPSIN + ChemSpider on 1,626 failures)

```powershell
python pass3_local_validation.py
```

Or OPSIN only (saves ChemSpider quota):

```powershell
python pass3_local_validation.py --skip-chemspider
```

Test on 50 rows:

```powershell
python pass3_local_validation.py --rescue-limit 50
```

Resume rescue without re-running SMARTS:

```powershell
python pass3_local_validation.py --rescue-only
```

### Output sheets (`dataset_ready_for_ccast.xlsx`)

| Sheet | Contents |
|-------|----------|
| `All_Data` | Full dataset + Pass3 columns |
| `For_CCAST` | Rows with SMILES for STOUT (upload this to CCAST) |
| `Resolved_Validated` | SMARTS PASS/SKIP |
| `Needs_Review` | SMARTS FAIL |
| `Pass3_Rescued` | New OPSIN/ChemSpider hits |
| `Still_Failed` | No structure |
| `Rescue_Log` | API attempt log |

### Pass3 columns

- `Pass3_Status` — `VALIDATED_OK`, `NEEDS_REVIEW`, `RESOLVED_PASS3`
- `Pass3_SMARTS_Result` — PASS / FAIL / SKIP / PARSE_ERROR
- `Pass3_SMARTS_Reason`, `Pass3_SMARTS_Expected`, `Pass3_SMARTS_Matched`
- `Pass3_Rescue_Source`, `Pass3_Rescue_SMILES`

---

## Step 2 — CCAST GPU notebook

1. Start a **GPU** Jupyter session on CCAST
2. Upload to the notebook directory:
   - `dataset_ready_for_ccast.xlsx`
   - `pass3_ccast_validation.py`
   - `pass3_ccast_validation.ipynb`
3. **Restart kernel**, then **Run All**
4. Download `dataset_from_ccast.xlsx`

### What CCAST does

- `chemical-converters`: SMILES → systematic IUPAC name (Hugging Face model)
- Jaro-Winkler: compare IUPAC vs original 1947 name (and vs `Resolved_Name`)
- Flag if score **< 0.45** (`SUSPICIOUS` / `LOW_SIMILARITY`)
- **`CONVERT_FAILED`** if the model produced no IUPAC (CUDA/runtime error)

Low similarity scores are **review hints**, not automatic rejections.

### After the run — sanity check

```python
filled = df["STOUT_IUPAC"].notna().sum()  # should be ~all rows
```

If most `STOUT_IUPAC` values are empty, CUDA failed mid-run. **Restart kernel**, set `RESUME = True` in the notebook, and re-run (uses `ccast_checkpoint.csv`).

### Install on CCAST (if needed)

```bash
pip install chemical-converters jellyfish openpyxl pandas
```

---

## Step 3 — Streamlit curation (after CCAST)

```powershell
pip install streamlit
streamlit run pass3_curation_app.py
```

Loads `dataset_from_ccast.xlsx` when present, else `dataset_ready_for_ccast.xlsx`.

---

## File sync workflow

```
Local PC                          CCAST GPU Jupyter
────────                          ─────────────────
resolved_chemicals_final.xlsx
        │
        ▼
pass3_local_validation.py
        │
        ▼
dataset_ready_for_ccast.xlsx  ──upload──►  pass3_ccast_validation.ipynb
                                                    │
                                                    ▼
dataset_from_ccast.xlsx     ◄──download──  dataset_from_ccast.xlsx
        │
        ▼
pass3_curation_app.py (Streamlit)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Excel `PermissionError` | Close file in Excel |
| No ChemSpider rescues | Check `.env` key; use `--skip-chemspider` |
| OPSIN returns nothing | Expected for archaic 1947 names |
| CCAST CUDA false | Start a **GPU** session, not CPU |
| Most STOUT_IUPAC blank | CUDA crashed; restart kernel, set `RESUME = True`, re-run |
| chemical-converters import error | `pip install chemical-converters` on CCAST |

---

## Module reference

| File | Role |
|------|------|
| `pass3_smarts_rules.py` | RDKit SMARTS vs name cues |
| `pass2_validation.py` | Pass 2 heuristic patterns (shared) |
| `pass3_local_validation.py` | Local pipeline |
| `pass3_ccast_validation.py` | SMILES→IUPAC + similarity + checkpoint/resume |
| `pass3_ccast_validation.ipynb` | CCAST notebook |
| `PASS3_Pipeline_Plan.pdf` | Approved plan document |
