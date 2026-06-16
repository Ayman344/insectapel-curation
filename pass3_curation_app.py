"""Streamlit curation app for Pass 3 flagged rows."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st
from rdkit import Chem
from rdkit.Chem import Draw

ROOT = Path(__file__).parent
CCAST_FILE = ROOT / "dataset_from_ccast.xlsx"
LOCAL_FILE = ROOT / "dataset_ready_for_ccast.xlsx"
OUT_FILE = ROOT / "dataset_curated_final.xlsx"


@st.cache_data
def load_data() -> pd.DataFrame:
    path = CCAST_FILE if CCAST_FILE.exists() else LOCAL_FILE
    if not path.exists():
        raise FileNotFoundError(
            "Missing dataset_from_ccast.xlsx — add it to the repo for cloud deploy."
        )
    return pd.read_excel(path, sheet_name="All_Data")


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    export_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df[export_cols].to_excel(w, sheet_name="All_Data", index=False)
    return buf.getvalue()


def mol_image(smiles: str):
    mol = Chem.MolFromSmiles(str(smiles))
    if mol:
        return Draw.MolToImage(mol, size=(280, 280))
    return None


def main():
    st.set_page_config(page_title="Pass 3 Curation", layout="wide")
    st.title("Pass 3 Chemical Name Curation")

    if "export_df" not in st.session_state:
        st.session_state.export_df = load_data()
    df = st.session_state.export_df
    ncol = "Chemical" if "Chemical" in df.columns else "_name"

    filter_opts = {
        "NEEDS_REVIEW (SMARTS fail)": df["Pass3_Status"] == "NEEDS_REVIEW",
        "CCAST CONVERT_FAILED": df.get("Pass3_CCAST_Flag", pd.Series(dtype=str)) == "CONVERT_FAILED",
        "CCAST SUSPICIOUS": df.get("Pass3_CCAST_Flag", pd.Series(dtype=str)) == "SUSPICIOUS",
        "CCAST LOW_SIMILARITY": df.get("Pass3_CCAST_Flag", pd.Series(dtype=str)) == "LOW_SIMILARITY",
        "PARTIAL_MATCH": df["Status"] == "PARTIAL_MATCH",
        "Still failed": df["Status"] == "FAILED_BOTH_PASSES",
        "All rows": pd.Series(True, index=df.index),
    }

    choice = st.sidebar.selectbox("Show", list(filter_opts.keys()))
    sub = df[filter_opts[choice]].copy()
    st.sidebar.write(f"Rows: {len(sub)}")
    if "Pass3_CCAST_Flag" in df.columns:
        st.sidebar.markdown("---")
        st.sidebar.caption("Queue sizes")
        for label, mask in filter_opts.items():
            if label != "All rows":
                st.sidebar.write(f"{label}: {int(mask.sum())}")

    if sub.empty:
        st.info("No rows for this filter.")
        return

    idx = st.sidebar.number_input("Row index in filter", 0, max(0, len(sub) - 1), 0)
    row = sub.iloc[int(idx)]

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Original name")
        st.write(row.get(ncol, ""))
        st.write("**Status:**", row.get("Status", ""))
        st.write("**Pass3_Status:**", row.get("Pass3_Status", ""))
        st.write("**SMARTS:**", row.get("Pass3_SMARTS_Result", ""), "-", row.get("Pass3_SMARTS_Reason", ""))
        if "Pass3_CCAST_Flag" in row:
            st.write("**CCAST flag:**", row.get("Pass3_CCAST_Flag", ""))
            st.write("**Jaro-Winkler:**", row.get("JaroWinkler_Score", ""))
            st.write("**STOUT IUPAC:**", row.get("STOUT_IUPAC", ""))
        st.write("**Resolved name:**", row.get("Resolved_Name", ""))
        st.code(str(row.get("SMILES", "")))

    with c2:
        img = mol_image(row.get("SMILES", ""))
        if img:
            st.image(img, caption="Current SMILES structure")
        else:
            st.warning("No valid structure")

    st.divider()
    action = st.radio("Action", ["Confirm OK", "Mark PARTIAL_MATCH", "Reject (clear SMILES)", "Override SMILES"])
    override = st.text_input("Override SMILES (if selected)", "")

    if st.button("Apply to this row"):
        key = row.name
        if action == "Confirm OK":
            df.at[key, "Pass3_Status"] = "CURATED_OK"
        elif action == "Mark PARTIAL_MATCH":
            df.at[key, "Status"] = "PARTIAL_MATCH"
            df.at[key, "Pass3_Status"] = "PARTIAL_MATCH"
        elif action == "Reject (clear SMILES)":
            df.at[key, "SMILES"] = None
            df.at[key, "Status"] = "FAILED_BOTH_PASSES"
            df.at[key, "Pass3_Status"] = "REJECTED"
        elif action == "Override SMILES" and override.strip():
            df.at[key, "SMILES"] = override.strip()
            df.at[key, "Pass3_Status"] = "CURATED_OK"
        st.session_state.export_df = df
        st.success("Updated. Download Excel below when finished.")

    st.download_button(
        label="Download dataset_curated_final.xlsx",
        data=df_to_excel_bytes(st.session_state.export_df),
        file_name="dataset_curated_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if OUT_FILE.parent.exists():
        if st.button("Also save locally (PC only)"):
            OUT_FILE.write_bytes(df_to_excel_bytes(st.session_state.export_df))
            st.success(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    main()
