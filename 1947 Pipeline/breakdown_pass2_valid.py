"""Break down valid Pass 2 rescues by strategy and risk tier."""
from collections import Counter
from pathlib import Path

import pandas as pd

from pass2_validation import ROOT_FALLBACK_STRATEGIES, classify_rescue_risk

ROOT = Path(__file__).parent
FINAL = ROOT / "resolved_chemicals_final.xlsx"
OUT = ROOT / "pass2_valid_breakdown.xlsx"


def main():
    p2 = pd.read_excel(FINAL, sheet_name="Pass2_Rescued")
    partial = pd.read_excel(FINAL, sheet_name="Partial_Match")

    print("=" * 72)
    print("VALID PASS 2 RESCUES: STRATEGY x RISK TIER")
    print("=" * 72)
    print(f"Pass2_Rescued sheet: {len(p2)} rows")
    print(f"Partial_Match sheet: {len(partial)} rows")
    print()

    risks, reasons = [], []
    for _, row in p2.iterrows():
        strat = str(row.get("Resolution_Strategy", ""))
        if strat in ROOT_FALLBACK_STRATEGIES:
            risk, reason = classify_rescue_risk(row)
        else:
            risk, reason = "N/A", "not a root-fallback strategy"
        risks.append(risk)
        reasons.append(reason)

    p2 = p2.copy()
    p2["Risk_Tier"] = risks
    p2["Risk_Reason"] = reasons

    ct = pd.crosstab(p2["Resolution_Strategy"], p2["Risk_Tier"], margins=True)
    col_order = [c for c in ["HIGH", "MEDIUM", "LOW", "REVIEW", "UNKNOWN", "N/A"] if c in ct.columns]
    if "All" in ct.columns:
        col_order.append("All")
    print(ct[col_order].to_string())
    print()

    print("Risk tier totals (valid Pass 2 only):")
    for tier, n in Counter(risks).most_common():
        print(f"  {tier:8s}  {n:4d}  ({n / len(p2) * 100:5.1f}%)")

    print()
    print("Strategy totals (valid Pass 2 only):")
    for strat, n in p2["Resolution_Strategy"].value_counts().items():
        print(f"  {strat:35s}  {n:4d}")

    fb = p2[p2["Resolution_Strategy"].isin(ROOT_FALLBACK_STRATEGIES)]
    print()
    print("=" * 72)
    print("ROOT-FALLBACK STRATEGIES STILL MARKED VALID (not demoted)")
    print("=" * 72)
    name_col = "Chemical" if "Chemical" in p2.columns else "_name"
    for tier in ["MEDIUM", "LOW", "REVIEW"]:
        sub = fb[fb["Risk_Tier"] == tier]
        if sub.empty:
            continue
        print(f"\n--- {tier} ({len(sub)}) ---")
        for _, row in sub.head(8).iterrows():
            nm = str(row.get(name_col, ""))[:70]
            resolved = row.get("Resolved_Name", "")
            print(f"  {nm}")
            print(f"    -> {resolved}  [{row['Resolution_Strategy']}]")
        if len(sub) > 8:
            print(f"  ... +{len(sub) - 8} more")

    detail_rows = []
    for strat in sorted(p2["Resolution_Strategy"].unique(), key=str):
        sub = p2[p2["Resolution_Strategy"] == strat]
        for tier in ["HIGH", "MEDIUM", "LOW", "REVIEW", "UNKNOWN", "N/A"]:
            n = int((sub["Risk_Tier"] == tier).sum())
            if n:
                detail_rows.append({"Strategy": strat, "Risk_Tier": tier, "Count": n})
        detail_rows.append({"Strategy": strat, "Risk_Tier": "SUBTOTAL", "Count": len(sub)})

    export_cols = [c for c in p2.columns if not str(c).startswith("_")]
    with pd.ExcelWriter(OUT) as w:
        pd.DataFrame(detail_rows).to_excel(w, sheet_name="Summary", index=False)
        ct.reset_index().to_excel(w, sheet_name="Crosstab", index=False)
        p2[export_cols].sort_values(["Resolution_Strategy", "Risk_Tier"]).to_excel(
            w, sheet_name="All_Valid_Pass2", index=False
        )
        fb.sort_values("Risk_Tier").to_excel(w, sheet_name="Fallback_Still_Valid", index=False)

    print(f"\nExported: {OUT}")


if __name__ == "__main__":
    main()
