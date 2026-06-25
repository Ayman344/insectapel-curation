"""Analysis of dataset_from_ccast.xlsx (CCAST Pass 3 reverse naming)."""
from __future__ import annotations

import difflib
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
CANDIDATES = [
    ROOT / "dataset_from_ccast.xlsx",
    Path(os.environ.get("TEMP", "/tmp")) / "dataset_from_ccast.xlsx",
]


def find_workbook() -> Path:
    for p in CANDIDATES:
        if not p.exists():
            continue
        try:
            with open(p, "rb"):
                pass
            return p
        except PermissionError:
            continue
    raise FileNotFoundError("dataset_from_ccast.xlsx not found (or file is locked)")


def jaro_winkler(a: str, b: str) -> float:
    try:
        from jellyfish import jaro_winkler_similarity

        return jaro_winkler_similarity(a, b)
    except ImportError:
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main() -> None:
    path = find_workbook()
    print(f"Source: {path}\n")

    all_data = pd.read_excel(path, sheet_name="All_Data")
    df = pd.read_excel(path, sheet_name="CCAST_Validated")

    print("=== CCAST_Validated summary ===")
    print(f"Rows: {len(df)}")
    print("\nPass3_CCAST_Flag:")
    print(df["Pass3_CCAST_Flag"].value_counts().to_string())

    iupac = df["STOUT_IUPAC"].astype(str)
    blank = iupac.str.strip().isin(["", "nan", "None"])
    print(f"\nBlank STOUT_IUPAC: {blank.sum()} ({blank.mean() * 100:.1f}%)")
    print("\nJaroWinkler vs 1947 Chemical:")
    print(df["JaroWinkler_Score"].describe().to_string())

    if "Resolved_Name" in df.columns:
        df = df.copy()
        df["JW_vs_Resolved"] = df.apply(
            lambda r: jaro_winkler(
                str(r.get("Resolved_Name", "") or "").lower(),
                str(r.get("STOUT_IUPAC", "") or "").lower(),
            )
            if str(r.get("STOUT_IUPAC", "")).strip() not in ("", "nan")
            else 0.0,
            axis=1,
        )
        print("\nJaroWinkler vs Resolved_Name (CIRpy):")
        print(df["JW_vs_Resolved"].describe().to_string())
        print(f"  >= 0.45: {(df['JW_vs_Resolved'] >= 0.45).sum()}")
        print(f"  >= 0.30: {(df['JW_vs_Resolved'] >= 0.30).sum()}")

    if "Pass3_SMARTS_Result" in df.columns:
        print("\nSMARTS x CCAST flag:")
        print(pd.crosstab(df["Pass3_SMARTS_Result"], df["Pass3_CCAST_Flag"]).to_string())

    if "Final_Status" in df.columns:
        print("\nFinal_Status x CCAST flag:")
        print(pd.crosstab(df["Final_Status"], df["Pass3_CCAST_Flag"]).to_string())

    dup = int(df["Chemical"].duplicated().sum())
    print(f"\nDuplicate Chemical names in CCAST_Validated: {dup}")

    print("\n=== First 10 rows ===")
    for _, r in df.head(10).iterrows():
        chem = str(r["Chemical"])[:50]
        iup = str(r["STOUT_IUPAC"])[:65]
        print(f"{r['Pass3_CCAST_Flag']:14} JW={r['JaroWinkler_Score']:.3f} | {chem}")
        print(f"  -> {iup}")

    print("\n=== OK samples (top 8 by JW) ===")
    ok = df[df["Pass3_CCAST_Flag"] == "OK"].sort_values("JaroWinkler_Score", ascending=False)
    for _, r in ok.head(8).iterrows():
        print(f"JW={r['JaroWinkler_Score']:.3f} | {r['Chemical']}")
        print(f"  -> {r['STOUT_IUPAC']}")

    print("\n=== SUSPICIOUS (all) ===")
    for _, r in df[df["Pass3_CCAST_Flag"] == "SUSPICIOUS"].iterrows():
        print(f"JW={r['JaroWinkler_Score']:.3f} | {r['Chemical']}")
        print(f"  -> {r['STOUT_IUPAC']}")

    low_nonzero = df[(df["Pass3_CCAST_Flag"] == "LOW_SIMILARITY") & (df["JaroWinkler_Score"] > 0.15)]
    print(f"\n=== LOW_SIMILARITY with JW > 0.15: {len(low_nonzero)} ===")
    for _, r in low_nonzero.sort_values("JaroWinkler_Score", ascending=False).head(6).iterrows():
        print(f"JW={r['JaroWinkler_Score']:.3f} | {r['Chemical']}")
        print(f"  -> {r['STOUT_IUPAC']}")

    if "JW_vs_Resolved" in df.columns:
        print("\n=== Best JW vs Resolved_Name (top 6) ===")
        for _, r in df.sort_values("JW_vs_Resolved", ascending=False).head(6).iterrows():
            print(f"JW_res={r['JW_vs_Resolved']:.3f} | Chem={r['Chemical']}")
            print(f"  Resolved={r.get('Resolved_Name', '')}")
            print(f"  IUPAC={r['STOUT_IUPAC']}")

    print("\n=== All_Data merge ===")
    flagged = all_data["Pass3_CCAST_Flag"].notna().sum()
    print(f"Rows with CCAST columns: {flagged} / {len(all_data)}")
    print(all_data["Pass3_CCAST_Flag"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
