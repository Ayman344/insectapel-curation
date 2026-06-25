"""
Pass 3 local validation and rescue pipeline.

1. SMARTS-validate ALL fully resolved rows (RESOLVED_PASS1 + RESOLVED_PASS2).
2. OPSIN + ChemSpider rescue for FAILED_BOTH_PASSES rows.
3. Export dataset_ready_for_ccast.xlsx for CCAST STOUT notebook.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from pass3_smarts_rules import validate_smiles_against_name

ROOT = Path(__file__).parent
INPUT_XLSX = ROOT / "resolved_chemicals_final.xlsx"
OUTPUT_XLSX = ROOT / "dataset_ready_for_ccast.xlsx"
OPSIN_CACHE = ROOT / "pass3_opsin_cache.json"
CHEMSPIDER_CACHE = ROOT / "pass3_chemspider_cache.json"

RESOLVED_STATUSES = frozenset({"RESOLVED_PASS1", "RESOLVED_PASS2"})
FAIL_STATUS = "FAILED_BOTH_PASSES"

OPSIN_API = "https://www.ebi.ac.uk/opsin/ws/{name}.json"


def name_col(df: pd.DataFrame) -> str:
    return "Chemical" if "Chemical" in df.columns else "_name"


def load_cache(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(path: Path, cache: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def opsin_lookup(name: str, cache: dict, delay: float = 0.25) -> tuple[str | None, str]:
    key = name.strip().lower()
    if key in cache:
        entry = cache[key]
        return entry.get("smiles"), entry.get("note", "cached")

    url = OPSIN_API.format(name=urllib.parse.quote(name.strip(), safe=""))
    try:
        time.sleep(delay)
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            note = f"HTTP {r.status_code}"
            cache[key] = {"smiles": None, "note": note}
            return None, note
        data = r.json()
        if data.get("status") == "SUCCESS" and data.get("smiles"):
            smi = data["smiles"]
            cache[key] = {"smiles": smi, "note": "opsin_api"}
            return smi, "opsin_api"
        note = data.get("message") or data.get("status") or "no_smiles"
        cache[key] = {"smiles": None, "note": note}
        return None, str(note)
    except Exception as exc:
        cache[key] = {"smiles": None, "note": str(exc)}
        return None, str(exc)


def chemspider_lookup(name: str, api_key: str, cache: dict, delay: float = 0.5) -> tuple[str | None, str]:
    key = name.strip().lower()
    if key in cache:
        entry = cache[key]
        return entry.get("smiles"), entry.get("note", "cached")

    try:
        from chemspipy import ChemSpider
    except ImportError:
        return None, "chemspipy not installed"

    try:
        time.sleep(delay)
        cs = ChemSpider(api_key)
        results = cs.search(name.strip())
        if not results:
            cache[key] = {"smiles": None, "note": "no_results"}
            return None, "no_results"
        compound = results[0] if isinstance(results, list) else next(iter(results), None)
        if compound is None:
            cache[key] = {"smiles": None, "note": "no_results"}
            return None, "no_results"
        smi = compound.smiles
        if smi:
            cache[key] = {"smiles": smi, "note": "chemspider"}
            return smi, "chemspider"
        cache[key] = {"smiles": None, "note": "empty_smiles"}
        return None, "empty_smiles"
    except Exception as exc:
        cache[key] = {"smiles": None, "note": str(exc)}
        return None, str(exc)


def run_smarts_validation(df: pd.DataFrame, ncol: str) -> pd.DataFrame:
    df = df.copy()
    mask = df["Status"].isin(RESOLVED_STATUSES)
    print(f"SMARTS validation: {mask.sum()} resolved rows (Pass 1 + Pass 2)")

    results, reasons, expected, matched = [], [], [], []
    for _, row in df.iterrows():
        if row["Status"] not in RESOLVED_STATUSES:
            results.append("")
            reasons.append("")
            expected.append("")
            matched.append("")
            continue
        nm = str(row.get(ncol, ""))
        smi = row.get("SMILES")
        vr = validate_smiles_against_name(nm, smi)
        results.append(vr.result)
        reasons.append(vr.reason)
        expected.append(";".join(vr.expected))
        matched.append(";".join(vr.matched))

    df["Pass3_SMARTS_Result"] = results
    df["Pass3_SMARTS_Reason"] = reasons
    df["Pass3_SMARTS_Expected"] = expected
    df["Pass3_SMARTS_Matched"] = matched

    # Set Pass3_Status for resolved rows
    pass3_status = df.get("Pass3_Status", pd.Series([""] * len(df)))
    if isinstance(pass3_status, str):
        pass3_status = pd.Series([""] * len(df))
    df["Pass3_Status"] = pass3_status.astype(str)

    for idx, row in df[mask].iterrows():
        r = row["Pass3_SMARTS_Result"]
        if r == "PASS":
            df.at[idx, "Pass3_Status"] = "VALIDATED_OK"
        elif r == "SKIP":
            df.at[idx, "Pass3_Status"] = "VALIDATED_OK"
            df.at[idx, "Pass3_SMARTS_Reason"] = row["Pass3_SMARTS_Reason"] + " (no rule; kept)"
        elif r in ("FAIL", "PARSE_ERROR"):
            df.at[idx, "Pass3_Status"] = "NEEDS_REVIEW"
        else:
            df.at[idx, "Pass3_Status"] = "NEEDS_REVIEW"

    counts = df.loc[mask, "Pass3_SMARTS_Result"].value_counts()
    print("SMARTS result breakdown:")
    for k, v in counts.items():
        print(f"  {k:12s}  {v}")
    review = (df.loc[mask, "Pass3_Status"] == "NEEDS_REVIEW").sum()
    print(f"  -> NEEDS_REVIEW: {review}")
    return df


def run_rescue(
    df: pd.DataFrame,
    ncol: str,
    *,
    use_chemspider: bool,
    api_key: str | None,
    limit: int | None,
) -> tuple[pd.DataFrame, list[dict]]:
    opsin_cache = load_cache(OPSIN_CACHE)
    cs_cache = load_cache(CHEMSPIDER_CACHE)
    log: list[dict] = []

    fail_idx = df.index[df["Status"] == FAIL_STATUS].tolist()
    if limit:
        fail_idx = fail_idx[:limit]
    print(f"Rescue attempts: {len(fail_idx)} failed rows")

    rescued = 0
    for i, idx in enumerate(fail_idx):
        nm = str(df.at[idx, ncol])
        if not nm or nm == "nan":
            continue

        smi, note = opsin_lookup(nm, opsin_cache)
        source = "opsin" if smi else ""
        if not smi and use_chemspider and api_key:
            smi, note = chemspider_lookup(nm, api_key, cs_cache)
            source = "chemspider" if smi else ""

        log.append({"Chemical": nm, "opsin_or_cs": source or "failed", "note": note, "smiles": smi})

        if smi:
            df.at[idx, "SMILES"] = smi
            df.at[idx, "Resolved_Name"] = nm
            df.at[idx, "Resolution_Source"] = f"pass3_{source}"
            df.at[idx, "Resolution_Strategy"] = f"pass3_{source}"
            df.at[idx, "Status"] = "RESOLVED_PASS3"
            df.at[idx, "Pass3_Status"] = "RESOLVED_PASS3"
            df.at[idx, "Pass3_Rescue_Source"] = source
            df.at[idx, "Pass3_Rescue_SMILES"] = smi
            rescued += 1

        if (i + 1) % 25 == 0:
            save_cache(OPSIN_CACHE, opsin_cache)
            if use_chemspider:
                save_cache(CHEMSPIDER_CACHE, cs_cache)
            print(f"  [{i+1}/{len(fail_idx)}] rescued so far: {rescued}")

    save_cache(OPSIN_CACHE, opsin_cache)
    if use_chemspider:
        save_cache(CHEMSPIDER_CACHE, cs_cache)
    print(f"Pass 3 rescues: {rescued}/{len(fail_idx)}")
    return df, log


def export_workbook(df: pd.DataFrame, log: list[dict], path: Path) -> None:
    export_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
    df_out = df[export_cols].copy()

    resolved_ok = df_out[df_out["Pass3_Status"] == "VALIDATED_OK"]
    needs_review = df_out[df_out["Pass3_Status"] == "NEEDS_REVIEW"]
    pass3_rescued = df_out[df_out["Status"] == "RESOLVED_PASS3"]
    still_failed = df_out[df_out["Status"] == FAIL_STATUS]
    for_ccast = df_out[
        df_out["Status"].isin(RESOLVED_STATUSES | {"RESOLVED_PASS3"})
        & df_out["SMILES"].notna()
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df_out.to_excel(w, sheet_name="All_Data", index=False)
        for_ccast.to_excel(w, sheet_name="For_CCAST", index=False)
        resolved_ok.to_excel(w, sheet_name="Resolved_Validated", index=False)
        needs_review.to_excel(w, sheet_name="Needs_Review", index=False)
        pass3_rescued.to_excel(w, sheet_name="Pass3_Rescued", index=False)
        still_failed.to_excel(w, sheet_name="Still_Failed", index=False)
        pd.DataFrame(log).to_excel(w, sheet_name="Rescue_Log", index=False)

    print(f"\nExported: {path}")
    print(f"  All_Data:           {len(df_out)}")
    print(f"  For_CCAST:          {len(for_ccast)}")
    print(f"  Resolved_Validated: {len(resolved_ok)}")
    print(f"  Needs_Review:       {len(needs_review)}")
    print(f"  Pass3_Rescued:       {len(pass3_rescued)}")
    print(f"  Still_Failed:       {len(still_failed)}")


def main():
    parser = argparse.ArgumentParser(description="Pass 3 local validation and rescue")
    parser.add_argument("--input", type=Path, default=INPUT_XLSX)
    parser.add_argument("--output", type=Path, default=OUTPUT_XLSX)
    parser.add_argument("--smarts-only", action="store_true", help="Skip OPSIN/ChemSpider rescue")
    parser.add_argument("--skip-chemspider", action="store_true", help="OPSIN only for rescue")
    parser.add_argument("--rescue-limit", type=int, default=None, help="Max failed rows to rescue (testing)")
    parser.add_argument("--rescue-only", action="store_true", help="Skip SMARTS (resume rescue only)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("CHEMSPIDER_API_KEY", "").strip()
    if api_key in ("", "your_key_here"):
        api_key = None

    print(f"Loading {args.input}")
    input_path = args.input
    if args.rescue_only and OUTPUT_XLSX.exists() and args.input == INPUT_XLSX:
        input_path = OUTPUT_XLSX
        print(f"  (rescue-only: using existing {OUTPUT_XLSX.name})")
    df = pd.read_excel(input_path, sheet_name="All_Data")
    ncol = name_col(df)
    if "_name" not in df.columns:
        df["_name"] = df[ncol]

    for col in (
        "Pass3_Status", "Pass3_SMARTS_Result", "Pass3_SMARTS_Reason",
        "Pass3_SMARTS_Expected", "Pass3_SMARTS_Matched",
        "Pass3_Rescue_Source", "Pass3_Rescue_SMILES", "Pass3_Notes",
    ):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).replace("nan", "")

    log: list[dict] = []
    if not args.rescue_only:
        df = run_smarts_validation(df, ncol)

    if not args.smarts_only:
        use_cs = not args.skip_chemspider and api_key is not None
        if not args.skip_chemspider and not api_key:
            print("WARNING: No CHEMSPIDER_API_KEY in .env - OPSIN only for rescue")
        df, log = run_rescue(
            df, ncol,
            use_chemspider=use_cs,
            api_key=api_key,
            limit=args.rescue_limit,
        )

    export_workbook(df, log, args.output)


if __name__ == "__main__":
    main()
