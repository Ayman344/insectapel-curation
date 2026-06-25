"""Validate Pass 2 first_segment rescues for likely false positives."""
from collections import Counter
from pathlib import Path

import pandas as pd

from pass2_validation import (
    classify_first_segment_risk,
    classify_first_word_risk,
    first_segment,
)

FINAL = Path(__file__).parent / "resolved_chemicals_final.xlsx"
OUT = Path(__file__).parent / "first_segment_validation.xlsx"


def classify_risk(row) -> tuple[str, str]:
    return classify_first_segment_risk(row)


def main():
    p2 = pd.read_excel(FINAL, sheet_name="Pass2_Rescued")
    fs = p2[p2["Resolution_Strategy"] == "first_segment"].copy()

    if fs.empty:
        print("No first_segment rescues found.")
        return

    name_col = "Chemical" if "Chemical" in fs.columns else "_name"
    risks, reasons, segs = [], [], []
    for _, row in fs.iterrows():
        risk, reason = classify_risk(row)
        risks.append(risk)
        reasons.append(reason)
        segs.append(first_segment(row.get(name_col, "")))

    fs["First_Segment"] = segs
    fs["Validation_Risk"] = risks
    fs["Validation_Reason"] = reasons

    print("=" * 70)
    print("FIRST_SEGMENT RESCUE VALIDATION")
    print("=" * 70)
    print(f"Total Pass 2 rescues:           {len(p2)}")
    print(f"first_segment rescues:          {len(fs)}")
    print()
    print("Risk breakdown:")
    for risk, n in Counter(risks).most_common():
        print(f"  {risk:8s}  {n:4d}  ({n/len(fs)*100:5.1f}%)")

    high = fs[fs["Validation_Risk"] == "HIGH"]
    medium = fs[fs["Validation_Risk"] == "MEDIUM"]
    low = fs[fs["Validation_Risk"] == "LOW"]

    print(f"\nLikely FALSE POSITIVES (HIGH):  {len(high)}")
    print(f"Needs review (MEDIUM):          {len(medium)}")
    print(f"Likely OK (LOW):                {len(low)}")

    # Sub-breakdown of HIGH reasons
    print("\nHIGH-risk reasons:")
    for reason, n in Counter(high["Validation_Reason"]).most_common(10):
        print(f"  [{n:3d}] {reason}")

    print("\n--- Sample HIGH-risk (first 15) ---")
    for _, row in high.head(15).iterrows():
        nm = str(row.get(name_col, ""))[:75]
        print(f"  {nm}")
        print(f"    -> {row['Resolved_Name']}  |  {row['Validation_Reason']}")

    print("\n--- Sample LOW-risk (first 10) ---")
    for _, row in low.head(10).iterrows():
        nm = str(row.get(name_col, ""))[:75]
        print(f"  {nm}")
        print(f"    -> {row['Resolved_Name']}")

    # Adjusted rescue count
    questionable = len(high) + len(medium)
    print()
    print("=" * 70)
    print("ADJUSTED ESTIMATES")
    print("=" * 70)
    print(f"first_segment rescues:                    {len(fs)}")
    print(f"Probably wrong (HIGH):                      {len(high)}")
    print(f"Uncertain (MEDIUM):                         {len(medium)}")
    print(f"Probably correct (LOW):                     {len(low)}")
    print()
    print(f"If HIGH are removed from Pass 2 rescues:")
    print(f"  Adjusted Pass 2 rescues:  {len(p2) - len(high)}  (was {len(p2)})")
    print(f"  Adjusted total resolved:  {5177 - len(high)}  (was 5177, ~{(5177-len(high))/7089*100:.1f}%)")

    export_cols = [c for c in fs.columns if not str(c).startswith("_")]
    with pd.ExcelWriter(OUT) as w:
        fs[export_cols].sort_values(["Validation_Risk", name_col]).to_excel(
            w, sheet_name="All_First_Segment", index=False
        )
        high[export_cols].to_excel(w, sheet_name="HIGH_Risk", index=False)
        medium[export_cols].to_excel(w, sheet_name="MEDIUM_Risk", index=False)
        low[export_cols].to_excel(w, sheet_name="LOW_Risk", index=False)

    print(f"\nExported: {OUT}")

    # Also check first_word strategy (same false-positive pattern)
    fw = p2[p2["Resolution_Strategy"] == "first_word"].copy()
    if not fw.empty:
        fw_risks, fw_reasons = [], []
        for _, row in fw.iterrows():
            risk, reason = classify_first_word_risk(row)
            fw_risks.append(risk)
            fw_reasons.append(reason)
        fw["Validation_Risk"] = fw_risks
        fw["Validation_Reason"] = fw_reasons
        print()
        print("=" * 70)
        print("FIRST_WORD RESCUE VALIDATION (related concern)")
        print("=" * 70)
        for risk, n in Counter(fw_risks).most_common():
            print(f"  {risk:8s}  {n:4d}  ({n/len(fw)*100:5.1f}%)")
        fw_high = sum(1 for r in fw_risks if r == "HIGH")
        print(f"\nCombined questionable (first_segment HIGH + first_word HIGH):")
        print(f"  {len(high) + fw_high} rescues may be wrong parent compounds")
        adj = 5177 - len(high) - fw_high
        print(f"  Adjusted total resolved: ~{adj} (~{adj/7089*100:.1f}%)")


if __name__ == "__main__":
    main()
