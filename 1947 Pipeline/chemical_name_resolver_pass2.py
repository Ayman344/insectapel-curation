# %% [markdown]
# # Chemical Name Resolver — Pass 2 (Smart Retry)
# 
# Takes the `FAILED_LOOKUP` rows from Pass 1 and applies smarter transformations:
# 
# 1. **Acid-ester name flip** — `"Acetic acid, bornyl ester"` → `"bornyl acetate"`
# 2. **Archaic term dictionary** — mercaptal → dithioacetal, carbinol → alcohol, etc.
# 3. **Prefix/suffix cleanup** — strip n-, iso-, sec-, tert- prefixes for retry
# 4. **Partial root search** — try base compound name alone
# 5. **PubChem fuzzy search** — search by name substring
# 6. **Disk caching** — saves progress every 100 rows, resumable if interrupted
# 
# **Input:** `resolved_chemicals.xlsx` from Pass 1 (upload the file)

# %% [markdown]
# ## 1. Install & Upload

# %%
# pip install pandas openpyxl pubchempy cirpy rdkit-pypi -q

import os, re, time, json, warnings
import pandas as pd
import numpy as np
from collections import Counter
warnings.filterwarnings("ignore")

from pass2_validation import should_skip_root_fallback

import pubchempy as pcp
try:
    import cirpy
    HAS_CIRPY = True
except ImportError:
    HAS_CIRPY = False

files = os.listdir()
print("Files in directory:", files)

# List files in the current directory
files = os.listdir()
print("Files in directory:", files)

# Pick the first file (or specify manually)
INPUT_FILE = files[5]
print(f"Uploaded: {INPUT_FILE}")

print(f"Uploaded: {INPUT_FILE}")
print(f"CIRpy available: {HAS_CIRPY}")

# %%
# Pick the first file (or specify manually)
INPUT_FILE = files[5]
print(f"Uploaded: {INPUT_FILE}")

# %% [markdown]
# ## 2. Load Failed Rows from Pass 1

# %%
NAME_COL = "Chemical"  #@param {type:"string"}

# Try loading the Failed_Lookup sheet first
try:
    df_fail = pd.read_excel(INPUT_FILE, sheet_name="Failed_Lookup")
    print(f"Loaded 'Failed_Lookup' sheet: {len(df_fail)} rows")
except:
    # Fallback: load All_Data and filter
    df_all = pd.read_excel(INPUT_FILE, sheet_name=0)
    df_fail = df_all[df_all["Status"] == "FAILED_LOOKUP"].copy()
    print(f"Filtered FAILED_LOOKUP from main sheet: {len(df_fail)} rows")

# Also load resolved rows to merge later
try:
    df_resolved = pd.read_excel(INPUT_FILE, sheet_name="Resolved")
    df_irregular = pd.read_excel(INPUT_FILE, sheet_name="Irregular")
    print(f"Loaded Resolved: {len(df_resolved)} | Irregular: {len(df_irregular)}")
except:
    df_all = pd.read_excel(INPUT_FILE, sheet_name=0)
    df_resolved = df_all[df_all["Status"] == "RESOLVED"].copy()
    df_irregular = df_all[df_all["Status"] == "IRREGULAR_SKIPPED"].copy()
    print(f"Filtered — Resolved: {len(df_resolved)} | Irregular: {len(df_irregular)}")

# Ensure name column
if NAME_COL not in df_fail.columns:
    candidates = [c for c in df_fail.columns if "chem" in c.lower() or "name" in c.lower()]
    if candidates:
        NAME_COL = candidates[0]
print(f"Name column: '{NAME_COL}'")

df_fail["_name"] = df_fail[NAME_COL].astype(str).str.strip()
print(f"\nReady to retry {len(df_fail)} failed names.")

# %% [markdown]
# ## 3. Archaic Chemistry Term Dictionary

# %%
# Maps archaic/uncommon terms to modern equivalents
ARCHAIC_DICT = {
    # Functional group terms
    "mercaptal": "dithioacetal",
    "mercaptol": "dithioketal",
    "mercaptan": "thiol",
    "carbinol": "methanol",    # as suffix: "dipentene carbinol" → needs context
    "pinacol": "2,3-dimethyl-2,3-butanediol",
    "glycol": "ethylene glycol",
    "glycerol": "glycerol",
    "furfurol": "furfural",
    "formol": "formaldehyde",
    "chloral": "trichloroacetaldehyde",
    "paraldehyde": "2,4,6-trimethyl-1,3,5-trioxane",

    # Trade name / old name → IUPAC
    "cellosolve": "2-ethoxyethanol",
    "carbitol": "2-(2-ethoxyethoxy)ethanol",
    "dowanol": "propylene glycol methyl ether",
    "dioxane": "1,4-dioxane",
    "dioxan": "1,4-dioxane",
    "trioxane": "1,3,5-trioxane",
    "picoline": "methylpyridine",
    "collidine": "2,4,6-trimethylpyridine",
    "lutidine": "dimethylpyridine",
    "xylidine": "dimethylaniline",
    "toluidine": "methylaniline",
    "anisole": "methoxybenzene",
    "phenetole": "ethoxybenzene",
    "cresol": "methylphenol",
    "xylenol": "dimethylphenol",
    "thymol": "2-isopropyl-5-methylphenol",
    "guaiacol": "2-methoxyphenol",
    "catechol": "1,2-benzenediol",
    "resorcinol": "1,3-benzenediol",
    "hydroquinone": "1,4-benzenediol",
    "pyrogallol": "1,2,3-benzenetriol",
    "orcinol": "3,5-dihydroxytoluene",
    "vanillin": "4-hydroxy-3-methoxybenzaldehyde",
    "coumarin": "2H-chromen-2-one",
    "quinoline": "quinoline",
    "isoquinoline": "isoquinoline",
    "acrolein": "2-propenal",
    "crotonaldehyde": "2-butenal",
    "mesityl oxide": "4-methylpent-3-en-2-one",
    "diacetone alcohol": "4-hydroxy-4-methylpentan-2-one",
    "pentaerythritol": "2,2-bis(hydroxymethyl)-1,3-propanediol",
}

# Acid name → ester suffix mapping
ACID_TO_ESTER = {
    "acetic": "acetate",
    "propionic": "propionate",
    "butyric": "butyrate",
    "valeric": "valerate",
    "caproic": "caproate",
    "caprylic": "caprylate",
    "capric": "caprate",
    "lauric": "laurate",
    "myristic": "myristate",
    "palmitic": "palmitate",
    "stearic": "stearate",
    "oleic": "oleate",
    "linoleic": "linoleate",
    "benzoic": "benzoate",
    "salicylic": "salicylate",
    "phthalic": "phthalate",
    "succinic": "succinate",
    "citric": "citrate",
    "tartaric": "tartrate",
    "oxalic": "oxalate",
    "malonic": "malonate",
    "maleic": "maleate",
    "fumaric": "fumarate",
    "glutaric": "glutarate",
    "adipic": "adipate",
    "sebacic": "sebacate",
    "azelaic": "azelate",
    "cinnamic": "cinnamate",
    "formic": "formate",
    "carbonic": "carbonate",
    "lactic": "lactate",
    "glycolic": "glycolate",
    "mandelic": "mandelate",
    "crotonic": "crotonate",
    "undecylenic": "undecylenate",
    "abietic": "abietate",
    "levulinic": "levulinate",
    "pyruvic": "pyruvate",
    "phosphoric": "phosphate",
    "sulfuric": "sulfate",
    "nitric": "nitrate",
    "boric": "borate",
    "thioglycolic": "thioglycolate",
    "phenylacetic": "phenylacetate",
    "toluic": "toluate",
    "nicotinic": "nicotinate",
    "isobutyric": "isobutyrate",
    "isovaleric": "isovalerate",
    "pelargonic": "pelargonate",
    "enanthic": "enanthate",
    "heptanoic": "heptanoate",
    "n-caproic": "hexanoate",
    "n-butyric": "butanoate",
    "n-valeric": "pentanoate",
    "iso-valeric": "3-methylbutanoate",
    "iso-butyric": "2-methylpropanoate",
    "chloroacetic": "chloroacetate",
    "dichloroacetic": "dichloroacetate",
    "trichloroacetic": "trichloroacetate",
    "bromoacetic": "bromoacetate",
    "cyanoacetic": "cyanoacetate",
    "acetoxypropionic": "acetoxypropionate",
}

# Common prefix aliases
PREFIX_STRIP = {
    "n-": "",
    "sec-": "",
    "tert-": "",
    "iso-": "iso",
    "dl-": "",
    "d-": "",
    "l-": "",
    "o-": "2-",
    "m-": "3-",
    "p-": "4-",
}

print(f"Loaded {len(ARCHAIC_DICT)} archaic term mappings")
print(f"Loaded {len(ACID_TO_ESTER)} acid→ester suffix mappings")
print(f"Loaded {len(PREFIX_STRIP)} prefix normalizations")

# %% [markdown]
# ## 4. Smart Name Transformer

# %%
def generate_smart_variants(name):
    """
    Generate multiple name variants using all transformation strategies.
    Returns: list of (variant_string, strategy_used) tuples.
    """
    raw = str(name).strip()
    low = raw.lower()
    variants = [(raw, "original")]

    # --------------------------------------------------
    # STRATEGY 1: Acid-ester name flip
    # "Acetic acid, bornyl ester" → "bornyl acetate"
    # "n-Caproic acid, n-octyl ester" → "n-octyl caproate"
    # --------------------------------------------------
    acid_ester_match = re.match(
        r'^(.+?)\s+acid,\s+(.+?)\s+ester\s*(.*)$', raw, re.IGNORECASE
    )
    if acid_ester_match:
        acid_part = acid_ester_match.group(1).strip()
        alcohol_part = acid_ester_match.group(2).strip()
        extra = acid_ester_match.group(3).strip()

        # Look up ester suffix
        acid_key = acid_part.lower().replace("acid", "").strip()
        # Try exact match first, then partial
        ester_suffix = ACID_TO_ESTER.get(acid_key)
        if not ester_suffix:
            # Try without n-, iso- prefix
            for prefix in ["n-", "iso-", "sec-", "tert-"]:
                if acid_key.startswith(prefix):
                    ester_suffix = ACID_TO_ESTER.get(acid_key[len(prefix):])
                    if ester_suffix:
                        break
        if not ester_suffix:
            # Generic: acid_name + "ate"
            ester_suffix = acid_key.rstrip('c') + "ate" if acid_key.endswith('ic') else acid_key + "ate"

        # Build flipped names
        flipped = f"{alcohol_part} {ester_suffix}".strip()
        variants.append((flipped, "acid_ester_flip"))

        # Also try without n-, iso- on the alcohol part
        clean_alcohol = re.sub(r'^[nN]-', '', alcohol_part)
        if clean_alcohol != alcohol_part:
            variants.append((f"{clean_alcohol} {ester_suffix}", "acid_ester_flip_clean"))

    # --------------------------------------------------
    # STRATEGY 2: Archaic term substitution
    # --------------------------------------------------
    for old_term, new_term in ARCHAIC_DICT.items():
        if old_term.lower() in low:
            replaced = re.sub(re.escape(old_term), new_term, raw, flags=re.IGNORECASE)
            variants.append((replaced, f"archaic_sub:{old_term}"))

    # --------------------------------------------------
    # STRATEGY 3: Strip parenthetical content
    # --------------------------------------------------
    stripped = re.sub(r'\s*\([^)]*\)', '', raw).strip()
    if stripped and stripped != raw:
        variants.append((stripped, "strip_parens"))

    # --------------------------------------------------
    # STRATEGY 4: Prefix normalization
    # "p-Aminobenzoic acid" → "4-Aminobenzoic acid"
    # --------------------------------------------------
    for prefix, replacement in PREFIX_STRIP.items():
        pattern = r'\b' + re.escape(prefix)
        if re.search(pattern, raw, re.IGNORECASE):
            normalized = re.sub(pattern, replacement, raw, flags=re.IGNORECASE).strip()
            if normalized != raw:
                variants.append((normalized, f"prefix_norm:{prefix}"))

    # --------------------------------------------------
    # STRATEGY 5: Comma cleanup
    # "N,N-Di-n-butyl furoamide" → try as-is
    # "Acid, modifier ester" → try without comma
    # --------------------------------------------------
    if "," in raw:
        # Try replacing comma with space
        no_comma = raw.replace(",", " ").strip()
        no_comma = re.sub(r'\s+', ' ', no_comma)
        variants.append((no_comma, "comma_to_space"))

    # --------------------------------------------------
    # STRATEGY 6: Extract root compound (first word/segment)
    # Skip when name is a derivative (ester/salt/carbonate) or acid-ester flip
    # variants were already generated — avoids resolving the parent compound.
    # --------------------------------------------------
    if not should_skip_root_fallback(raw, variants):
        first_seg = raw.split(",")[0].strip()
        if first_seg != raw:
            variants.append((first_seg, "first_segment"))

        first_word = raw.split()[0].strip() if raw.split() else ""
        if first_word and len(first_word) > 4 and first_word != raw:
            variants.append((first_word, "first_word"))

    # --------------------------------------------------
    # STRATEGY 7: Handle "diester", "triester", "monoester"
    # "Acetic acid, 1,4-butanediol diester" → "1,4-butanediol diacetate"
    # --------------------------------------------------
    multi_ester = re.match(
        r'^(.+?)\s+acid,\s+(.+?)\s+(di|tri|mono|tetra)ester\s*$', raw, re.IGNORECASE
    )
    if multi_ester:
        acid_part = multi_ester.group(1).strip()
        polyol_part = multi_ester.group(2).strip()
        multiplier = multi_ester.group(3).strip().lower()
        acid_key = acid_part.lower().strip()
        ester_suffix = ACID_TO_ESTER.get(acid_key, acid_key + "ate")
        variants.append((f"{polyol_part} {multiplier}{ester_suffix}", "multi_ester_flip"))

    # --------------------------------------------------
    # STRATEGY 8: "X of Y" → "Y X" rearrangement
    # --------------------------------------------------
    of_match = re.match(r'^(.+?)\s+of\s+(.+)$', raw, re.IGNORECASE)
    if of_match:
        variants.append((f"{of_match.group(2)} {of_match.group(1)}", "of_rearrange"))

    # --------------------------------------------------
    # STRATEGY 9: Strip stereochem prefixes for simpler lookup
    # "dl-Camphor" → "Camphor"
    # --------------------------------------------------
    no_stereo = re.sub(r'^[dlDL]+-|^\(\+/?-?\)-?|^\([RS]\)-?|^cis-|^trans-|^alpha-|^beta-|^meso-', '', raw).strip()
    if no_stereo and no_stereo != raw:
        variants.append((no_stereo, "strip_stereo"))

    # --------------------------------------------------
    # STRATEGY 10: Handle "X and Y" → try just X, then just Y
    # --------------------------------------------------
    and_match = re.match(r'^(.+?)\s+and\s+(.+)$', raw, re.IGNORECASE)
    if and_match:
        variants.append((and_match.group(1).strip(), "split_and_first"))
        variants.append((and_match.group(2).strip(), "split_and_second"))

    # Deduplicate preserving order
    seen = set()
    unique = []
    for v, strat in variants:
        v_clean = v.strip().rstrip(',').strip()
        if v_clean and v_clean.lower() not in seen and len(v_clean) > 2:
            seen.add(v_clean.lower())
            unique.append((v_clean, strat))

    return unique


# Test the transformer
test_names = [
    "Acetic acid, bornyl ester",
    "n-Caproic acid, n-octyl ester",
    "Acetaldehyde dioctyl mercaptal",
    "Acetic acid, 1,4-butanediol diester",
    "p-Aminobenzoic acid, butyl ester (Butesin)",
    "dl-Camphor",
]

print("Smart transformer test:")
print("=" * 70)
for name in test_names:
    variants = generate_smart_variants(name)
    print(f"\n  Input: {name}")
    for i, (v, strat) in enumerate(variants[:8]):  # show max 8
        print(f"    [{i+1}] {v:50s} ({strat})")
    if len(variants) > 8:
        print(f"    ... +{len(variants)-8} more variants")

# %% [markdown]
# ## 5. Resolver with Disk Cache

# %%
CACHE_FILE = "pass2_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def resolve_with_variants(name, variants, cache, max_retries=2):
    """
    Try each variant through PubChem → CIRpy.
    Returns: (smiles, resolved_name, source, strategy)
    """
    # Check cache first
    cache_key = name.lower().strip()
    if cache_key in cache:
        entry = cache[cache_key]
        return entry["smiles"], entry["resolved"], entry["source"], entry["strategy"]

    for variant, strategy in variants:
        # --- PubChem ---
        for attempt in range(max_retries):
            try:
                results = pcp.get_compounds(variant, 'name')
                if results:
                    smiles = results[0].canonical_smiles
                    if smiles:
                        cache[cache_key] = {
                            "smiles": smiles, "resolved": variant,
                            "source": "pubchem", "strategy": strategy
                        }
                        return smiles, variant, "pubchem", strategy
                break
            except pcp.PubChemHTTPError:
                time.sleep(1.5)
            except Exception:
                break

        # --- CIRpy ---
        if HAS_CIRPY:
            try:
                smiles = cirpy.resolve(variant, 'smiles')
                if smiles:
                    cache[cache_key] = {
                        "smiles": smiles, "resolved": variant,
                        "source": "cirpy", "strategy": strategy
                    }
                    return smiles, variant, "cirpy", strategy
            except Exception:
                pass

    # All variants failed
    cache[cache_key] = {
        "smiles": None, "resolved": None,
        "source": "failed", "strategy": "all_failed"
    }
    return None, None, "failed", "all_failed"


print("Resolver with disk cache ready.")
print(f"Cache file: {CACHE_FILE}")
existing_cache = load_cache()
print(f"Existing cache entries: {len(existing_cache)}")

# %% [markdown]
# ## 6. Run Pass 2 Batch Resolution

# %%
cache = load_cache()

print(f"Pass 2: Retrying {len(df_fail)} failed names with smart transformations...")
print(f"Estimated time: {len(df_fail) * 1.0 / 60:.0f}–{len(df_fail) * 2.0 / 60:.0f} minutes")
print(f"(More variants per name = more API calls per name)\n")

results = []
n_success = 0
n_fail = 0
n_cached = 0
strategy_counts = Counter()
batch_start = time.time()

for idx, (df_idx, row) in enumerate(df_fail.iterrows()):
    name = row["_name"]

    # Check if already in cache (from previous interrupted run)
    cache_key = name.lower().strip()
    was_cached = cache_key in cache

    # Generate smart variants
    variants = generate_smart_variants(name)

    # Resolve
    smiles, resolved, source, strategy = resolve_with_variants(name, variants, cache)

    results.append({
        "smiles": smiles,
        "resolved_name": resolved,
        "source": source,
        "strategy": strategy,
        "n_variants_tried": len(variants),
    })

    if smiles:
        n_success += 1
        strategy_counts[strategy] += 1
    else:
        n_fail += 1

    if was_cached:
        n_cached += 1

    # Progress every 50 rows
    if (idx + 1) % 50 == 0 or idx == 0:
        elapsed = time.time() - batch_start
        rate = (idx + 1) / elapsed if elapsed > 0 else 0
        remaining = (len(df_fail) - idx - 1) / rate / 60 if rate > 0 else 0
        hit_rate = n_success / (idx + 1) * 100
        print(f"  [{idx+1:5d}/{len(df_fail)}]  "
              f"RESCUED: {n_success}  STILL_FAILED: {n_fail}  "
              f"Hit: {hit_rate:.1f}%  "
              f"Rate: {rate:.1f}/sec  "
              f"ETA: {remaining:.1f} min")

    # Save cache every 100 rows
    if (idx + 1) % 100 == 0:
        save_cache(cache)

    # Rate limiting
    if not was_cached:
        time.sleep(0.15)

# Final cache save
save_cache(cache)

elapsed_total = (time.time() - batch_start) / 60
print(f"\n{'='*70}")
print(f"  PASS 2 COMPLETE in {elapsed_total:.1f} minutes")
print(f"  Rescued:      {n_success}/{len(df_fail)} ({n_success/len(df_fail)*100:.1f}%)")
print(f"  Still failed: {n_fail}/{len(df_fail)} ({n_fail/len(df_fail)*100:.1f}%)")
print(f"  From cache:   {n_cached}")
print(f"{'='*70}")

# %% [markdown]
# ## 7. Strategy Effectiveness Report

# %%
print("\nWhich strategies rescued compounds:")
print("=" * 60)
for strat, count in strategy_counts.most_common():
    pct = count / n_success * 100 if n_success > 0 else 0
    print(f"  {strat:35s} {count:5d}  ({pct:5.1f}% of rescues)")

# Source breakdown
source_counts = Counter(r["source"] for r in results)
print(f"\nResolution source breakdown:")
print("-" * 40)
for src, count in source_counts.most_common():
    print(f"  {src:15s} {count:5d}")

# Variants tried distribution
variant_counts = [r["n_variants_tried"] for r in results]
print(f"\nVariants generated per name:")
print(f"  Min:  {min(variant_counts)}")
print(f"  Max:  {max(variant_counts)}")
print(f"  Mean: {np.mean(variant_counts):.1f}")

# %% [markdown]
# ## 8. Merge with Pass 1 Results

# %%
# Update failed rows with Pass 2 results
results_df = pd.DataFrame(results)
df_fail["SMILES"] = results_df["smiles"].values
df_fail["Resolved_Name"] = results_df["resolved_name"].values
df_fail["Resolution_Source"] = results_df["source"].apply(
    lambda s: f"pass2_{s}" if s != "failed" else "failed_pass2"
).values
df_fail["Resolution_Strategy"] = results_df["strategy"].values

# Update status
df_fail["Status"] = df_fail["SMILES"].apply(
    lambda s: "RESOLVED_PASS2" if pd.notna(s) else "FAILED_BOTH_PASSES"
)

# Add strategy column to Pass 1 resolved
df_resolved["Resolution_Strategy"] = "pass1_direct"
df_resolved["Status"] = "RESOLVED_PASS1"

# Add to irregular
df_irregular["Resolution_Strategy"] = "skipped"
if "Status" not in df_irregular.columns:
    df_irregular["Status"] = "IRREGULAR_SKIPPED"

# Combine all
# Ensure matching columns
common_cols = list(set(df_resolved.columns) & set(df_fail.columns) & set(df_irregular.columns))
df_final = pd.concat([
    df_resolved[common_cols],
    df_fail[common_cols],
    df_irregular[common_cols]
]).sort_index()

# Grand summary
print("\nCOMBINED RESULTS (Pass 1 + Pass 2):")
print("=" * 60)
for status, count in df_final["Status"].value_counts().items():
    pct = count / len(df_final) * 100
    print(f"  {status:30s} {count:5d}  ({pct:5.1f}%)")

total_resolved = df_final["Status"].str.contains("RESOLVED").sum()
total = len(df_final)
print(f"\n  TOTAL RESOLVED: {total_resolved}/{total} ({total_resolved/total*100:.1f}%)")
print(f"  TOTAL FAILED:   {total - total_resolved - len(df_irregular)}/{total}")
print(f"  IRREGULAR:      {len(df_irregular)}/{total}")

# %% [markdown]
# ## 9. Inspect Remaining Failures

# %%
still_failed = df_fail[df_fail["Status"] == "FAILED_BOTH_PASSES"]

print(f"Still failed after both passes: {len(still_failed)}")
print(f"\nSample of persistent failures (first 40):")
print("=" * 70)
for _, row in still_failed.head(40).iterrows():
    print(f"  {row['_name'][:85]}")

# %% [markdown]
# ## 10. Export Final Combined Results

# %%
FINAL_OUTPUT = "resolved_chemicals_final.xlsx"

# Clean internal columns
export_cols = [c for c in df_final.columns if not c.startswith("_")]
df_export = df_final[export_cols].copy()

with pd.ExcelWriter(FINAL_OUTPUT) as writer:
    # All data
    df_export.to_excel(writer, sheet_name="All_Data", index=False)

    # All resolved (pass 1 + pass 2)
    all_resolved = df_export[df_export["Status"].str.contains("RESOLVED", na=False)]
    all_resolved.to_excel(writer, sheet_name="All_Resolved", index=False)

    # Pass 2 rescues only
    p2_rescued = df_export[df_export["Status"] == "RESOLVED_PASS2"]
    p2_rescued.to_excel(writer, sheet_name="Pass2_Rescued", index=False)

    # Still failed
    still_fail_export = df_export[df_export["Status"] == "FAILED_BOTH_PASSES"]
    still_fail_export.to_excel(writer, sheet_name="Still_Failed", index=False)

    # Irregular
    irreg_export = df_export[df_export["Status"] == "IRREGULAR_SKIPPED"]
    irreg_export.to_excel(writer, sheet_name="Irregular", index=False)

    # Strategy effectiveness
    strat_data = [{"Strategy": s, "Rescues": c} for s, c in strategy_counts.most_common()]
    pd.DataFrame(strat_data).to_excel(writer, sheet_name="Strategy_Report", index=False)

print(f"Exported: {FINAL_OUTPUT}")
print(f"  Sheet 'All_Data':        {len(df_export)} rows")
print(f"  Sheet 'All_Resolved':    {len(all_resolved)} rows")
print(f"  Sheet 'Pass2_Rescued':   {len(p2_rescued)} rows")
print(f"  Sheet 'Still_Failed':    {len(still_fail_export)} rows")
print(f"  Sheet 'Irregular':       {len(irreg_export)} rows")
print(f"  Sheet 'Strategy_Report': effectiveness breakdown")

# files.download(FINAL_OUTPUT)  # Colab only


