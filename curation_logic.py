"""Queue masks and CCAST_APPROVED tier logic for the curation app."""
from __future__ import annotations

import pandas as pd

# Tier 1+2+3: SMARTS PASS + CCAST OK + Pass 1 + Jaro-Winkler >= 0.55
JW_APPROVED_MIN = 0.55

CURATION_COLUMNS = [
    "Row_ID",
    "CCAST_Approved",
    "Curation_Reviewed",
    "Curation_Reviewed_By",
    "Curation_Reviewed_At",
    "Curation_Action",
    "Curation_Notes",
]


def ccast_approved_mask(df: pd.DataFrame) -> pd.Series:
    """Strict unquestionable tier (~1,044 rows in current dataset)."""
    jw = pd.to_numeric(df.get("JaroWinkler_Score"), errors="coerce")
    return (
        (df.get("Pass3_CCAST_Flag") == "OK")
        & (df.get("Pass3_SMARTS_Result") == "PASS")
        & (df.get("Status") == "RESOLVED_PASS1")
        & (jw >= JW_APPROVED_MIN)
    )


def ensure_curation_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Row_ID" not in out.columns:
        out["Row_ID"] = out.index.astype(int)
    approved = ccast_approved_mask(out)
    out["CCAST_Approved"] = approved.map({True: "Yes", False: "No"})
    for col, default in [
        ("Curation_Reviewed", "No"),
        ("Curation_Reviewed_By", ""),
        ("Curation_Reviewed_At", ""),
        ("Curation_Action", ""),
        ("Curation_Notes", ""),
    ]:
        if col not in out.columns:
            out[col] = default
        out[col] = out[col].fillna(default).astype(str).replace("nan", default)
    return out


def is_reviewed(row: pd.Series) -> bool:
    return str(row.get("Curation_Reviewed", "No")).strip().lower() == "yes"


def queue_mask(df: pd.DataFrame, queue_id: str) -> pd.Series:
    if queue_id == "needs_review":
        return df["Pass3_Status"] == "NEEDS_REVIEW"
    if queue_id == "ccast_convert_failed":
        return df.get("Pass3_CCAST_Flag", pd.Series(dtype=str)) == "CONVERT_FAILED"
    if queue_id == "ccast_suspicious":
        return df.get("Pass3_CCAST_Flag", pd.Series(dtype=str)).isin(["SUSPICIOUS", "LOW_SIMILARITY"])
    if queue_id == "ccast_approved":
        return ccast_approved_mask(df)
    if queue_id == "partial_match":
        return df["Status"] == "PARTIAL_MATCH"
    if queue_id == "still_failed":
        return df["Status"] == "FAILED_BOTH_PASSES"
    if queue_id == "all":
        return pd.Series(True, index=df.index)
    raise ValueError(f"Unknown queue: {queue_id}")
