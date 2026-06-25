"""
Apply Pass 2 quality corrections:
- Reclassify HIGH-risk first_segment / first_word rescues as PARTIAL_MATCH
- Re-export resolved_chemicals_final.xlsx with corrected sheets/counts
- Regenerate structure HTML for the corrected resolved set
- Write correction notes and refresh PDF report
"""
from __future__ import annotations

import os
import shutil
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from generate_pdf_report import build_report, gather_stats
from pass2_validation import (
    ROOT_FALLBACK_STRATEGIES,
    classify_rescue_risk,
    is_high_risk_rescue,
)
from structure_html import generate_structure_html

ROOT = Path(__file__).parent
FINAL_XLSX = ROOT / "resolved_chemicals_final.xlsx"
FINAL_TEMP = Path(os.environ.get("TEMP", "/tmp")) / "resolved_chemicals_final.xlsx"
NOTES_PATH = ROOT / "CORRECTION_NOTES.md"
HTML_OUT = ROOT / "resolved_structures_corrected.html"


def load_workbook_path() -> Path:
    if FINAL_XLSX.exists():
        try:
            pd.read_excel(FINAL_XLSX, sheet_name="All_Data", nrows=1)
            return FINAL_XLSX
        except PermissionError:
            pass
    if FINAL_TEMP.exists():
        return FINAL_TEMP
    if FINAL_XLSX.exists():
        shutil.copy2(FINAL_XLSX, FINAL_TEMP)
        return FINAL_TEMP
    raise FileNotFoundError(f"Missing workbook: {FINAL_XLSX}")


def apply_corrections(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    if "Validation_Risk" not in df.columns:
        df["Validation_Risk"] = ""
    if "Validation_Reason" not in df.columns:
        df["Validation_Reason"] = ""
    if "Previous_Status" not in df.columns:
        df["Previous_Status"] = ""

    reclassified = 0
    for idx, row in df.iterrows():
        if row.get("Status") != "RESOLVED_PASS2":
            continue
        if str(row.get("Resolution_Strategy") or "") not in ROOT_FALLBACK_STRATEGIES:
            continue

        risk, reason = classify_rescue_risk(row)
        df.at[idx, "Validation_Risk"] = risk
        df.at[idx, "Validation_Reason"] = reason

        high, high_reason = is_high_risk_rescue(row)
        if high:
            df.at[idx, "Previous_Status"] = row["Status"]
            df.at[idx, "Status"] = "PARTIAL_MATCH"
            df.at[idx, "Validation_Reason"] = high_reason
            reclassified += 1

    pass2_valid = df[df["Status"] == "RESOLVED_PASS2"]
    partial = df[df["Status"] == "PARTIAL_MATCH"]
    all_resolved = df[df["Status"].isin(["RESOLVED_PASS1", "RESOLVED_PASS2"])]

    summary = {
        "total_rows": len(df),
        "reclassified_to_partial": reclassified,
        "resolved_pass1": int((df["Status"] == "RESOLVED_PASS1").sum()),
        "resolved_pass2_valid": len(pass2_valid),
        "partial_match": len(partial),
        "still_failed": int((df["Status"] == "FAILED_BOTH_PASSES").sum()),
        "irregular": int((df["Status"] == "IRREGULAR_SKIPPED").sum()),
        "all_resolved": len(all_resolved),
        "nominal_resolved_before": 5177,
        "strategy_counts": Counter(pass2_valid["Resolution_Strategy"].dropna()),
        "partial_by_strategy": Counter(partial["Resolution_Strategy"].dropna()),
    }
    return df, summary


def export_workbook(df: pd.DataFrame, summary: dict, path: Path) -> None:
    export_cols = [c for c in df.columns if not str(c).startswith("_")]
    df_export = df[export_cols].copy()

    all_resolved = df_export[df_export["Status"].isin(["RESOLVED_PASS1", "RESOLVED_PASS2"])]
    pass2_valid = df_export[df_export["Status"] == "RESOLVED_PASS2"]
    partial = df_export[df_export["Status"] == "PARTIAL_MATCH"]
    still_failed = df_export[df_export["Status"] == "FAILED_BOTH_PASSES"]
    irregular = df_export[df_export["Status"] == "IRREGULAR_SKIPPED"]

    strat_rows = [
        {"Strategy": strategy, "Rescues": count}
        for strategy, count in summary["strategy_counts"].most_common()
    ]
    correction_rows = [
        {"Metric": "Report date", "Value": date.today().isoformat()},
        {"Metric": "Nominal resolved (before correction)", "Value": summary["nominal_resolved_before"]},
        {"Metric": "Reclassified to PARTIAL_MATCH", "Value": summary["reclassified_to_partial"]},
        {"Metric": "Valid Pass 2 rescues", "Value": summary["resolved_pass2_valid"]},
        {"Metric": "Total fully resolved", "Value": summary["all_resolved"]},
        {"Metric": "PARTIAL_MATCH rows", "Value": summary["partial_match"]},
        {"Metric": "Still failed", "Value": summary["still_failed"]},
        {"Metric": "Irregular skipped", "Value": summary["irregular"]},
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_export.to_excel(writer, sheet_name="All_Data", index=False)
        all_resolved.to_excel(writer, sheet_name="All_Resolved", index=False)
        pass2_valid.to_excel(writer, sheet_name="Pass2_Rescued", index=False)
        partial.to_excel(writer, sheet_name="Partial_Match", index=False)
        still_failed.to_excel(writer, sheet_name="Still_Failed", index=False)
        irregular.to_excel(writer, sheet_name="Irregular", index=False)
        pd.DataFrame(strat_rows).to_excel(writer, sheet_name="Strategy_Report", index=False)
        pd.DataFrame(correction_rows).to_excel(writer, sheet_name="Correction_Summary", index=False)

    print(f"Exported: {path}")
    print(f"  All_Data:           {len(df_export)}")
    print(f"  All_Resolved:       {len(all_resolved)}")
    print(f"  Pass2_Rescued:      {len(pass2_valid)}")
    print(f"  Partial_Match:      {len(partial)}")
    print(f"  Still_Failed:       {len(still_failed)}")
    print(f"  Irregular:          {len(irregular)}")


def write_notes(summary: dict, path: Path) -> None:
    total = summary["total_rows"]
    resolved = summary["all_resolved"]
    pct = resolved / total * 100 if total else 0

    lines = [
        "# Pass 2 Correction Notes",
        "",
        f"**Date:** {date.today().isoformat()}",
        "",
        "## Actions performed",
        "",
        "1. HIGH-risk `first_segment` and `first_word` Pass 2 rescues reclassified as `PARTIAL_MATCH`.",
        "2. `generate_smart_variants()` updated to skip root fallbacks for derivative names.",
        "3. `resolved_chemicals_final.xlsx` re-exported with corrected sheets and counts.",
        "4. Structure HTML regenerated for fully resolved compounds only.",
        "5. PDF report refreshed with post-correction statistics.",
        "",
        "## Status counts (after correction)",
        "",
        f"| Status | Count |",
        f"|--------|------:|",
        f"| RESOLVED_PASS1 | {summary['resolved_pass1']} |",
        f"| RESOLVED_PASS2 (valid) | {summary['resolved_pass2_valid']} |",
        f"| **Total fully resolved** | **{resolved} ({pct:.1f}%)** |",
        f"| PARTIAL_MATCH | {summary['partial_match']} |",
        f"| FAILED_BOTH_PASSES | {summary['still_failed']} |",
        f"| IRREGULAR_SKIPPED | {summary['irregular']} |",
        "",
        "## Reclassification",
        "",
        f"- Rows moved from `RESOLVED_PASS2` to `PARTIAL_MATCH`: **{summary['reclassified_to_partial']}**",
        f"- Nominal resolved before correction: **{summary['nominal_resolved_before']}**",
        "",
        "### PARTIAL_MATCH by original strategy",
        "",
    ]
    for strategy, count in summary["partial_by_strategy"].most_common():
        lines.append(f"- `{strategy}`: {count}")

    lines.extend(
        [
            "",
            "## Pass 2 logic fix",
            "",
            "Root fallback strategies (`first_segment`, `first_word`) are now suppressed when:",
            "",
            "- Name matches acid + ester or acid + salt pattern",
            "- Comma suffix indicates a derivative (ester, salt, carbonate, etc.)",
            "- Name matches multi-ester pattern",
            "- Acid-ester flip variants were already generated for the name",
            "",
            "## Output files",
            "",
            "- `resolved_chemicals_final.xlsx` (corrected)",
            "- `resolved_structures_corrected.html`",
            "- `Chemical_Name_Resolution_Report.pdf` (updated)",
            "- `first_segment_validation.xlsx` (run `validate_first_segment.py` to refresh)",
            "",
            "## PARTIAL_MATCH semantics",
            "",
            "These rows retain SMILES and resolved names for audit/review but are excluded",
            "from `All_Resolved` and the structure HTML gallery because the structure",
            "likely corresponds to a parent compound, not the full derivative name.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote notes: {path}")


def main() -> None:
    src = load_workbook_path()
    if src != FINAL_XLSX:
        print(f"Reading from temp copy: {src}")

    df = pd.read_excel(src, sheet_name="All_Data")
    if "_name" not in df.columns and "Chemical" in df.columns:
        df["_name"] = df["Chemical"]

    df, summary = apply_corrections(df)

    try:
        export_workbook(df, summary, FINAL_XLSX)
    except PermissionError:
        backup = ROOT / "resolved_chemicals_final_corrected.xlsx"
        export_workbook(df, summary, backup)
        print(f"WARNING: Could not overwrite locked file. Saved to {backup}")

    all_resolved = df[df["Status"].isin(["RESOLVED_PASS1", "RESOLVED_PASS2"])]
    generate_structure_html(
        all_resolved,
        HTML_OUT,
        title="Resolved Chemical Structures (Corrected)",
        subtitle=(
            f"Fully resolved compounds: {len(all_resolved)} "
            f"(PARTIAL_MATCH rows excluded)"
        ),
    )

    write_notes(summary, NOTES_PATH)

    stats = gather_stats()
    build_report(stats)
    print(f"PDF report updated: {ROOT / 'Chemical_Name_Resolution_Report.pdf'}")
    print(
        f"\nFinal: {summary['all_resolved']}/{summary['total_rows']} fully resolved "
        f"({summary['all_resolved']/summary['total_rows']*100:.1f}%), "
        f"{summary['partial_match']} PARTIAL_MATCH, "
        f"{summary['still_failed']} still failed"
    )


if __name__ == "__main__":
    main()
