"""Streamlit curation app for Pass 3 flagged rows."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from rdkit import Chem
from rdkit.Chem import Draw

from curation_glossary import GLOSSARY, REVIEW_QUEUES, get_short
from curation_github import (
    AlreadyReviewedError,
    GitHubSyncError,
    config_from_streamlit_secrets,
    load_progress,
    merge_progress_into_df,
    row_to_progress_record,
    save_review,
)
from curation_logic import ensure_curation_columns, is_reviewed, queue_mask

ROOT = Path(__file__).parent
CCAST_FILE = ROOT / "dataset_from_ccast.xlsx"
LOCAL_FILE = ROOT / "dataset_ready_for_ccast.xlsx"
OUT_FILE = ROOT / "dataset_curated_final.xlsx"
GUIDE_PDF = ROOT / "Curation_Reviewer_Guide.pdf"
PROGRESS_LOCAL = ROOT / "curation_progress.csv"


@st.cache_data
def load_baseline() -> pd.DataFrame:
    path = CCAST_FILE if CCAST_FILE.exists() else LOCAL_FILE
    if not path.exists():
        raise FileNotFoundError(
            "Missing dataset_from_ccast.xlsx — add it to the repo for cloud deploy."
        )
    df = pd.read_excel(path, sheet_name="All_Data")
    return ensure_curation_columns(df)


def load_merged_dataset() -> pd.DataFrame:
    config = config_from_streamlit_secrets(PROGRESS_LOCAL)
    base = load_baseline()
    try:
        progress, _, mode = load_progress(config)
        st.session_state.sync_mode = mode
        st.session_state.github_configured = config.enabled
    except GitHubSyncError as exc:
        st.session_state.sync_mode = "error"
        st.session_state.sync_error = str(exc)
        progress = pd.DataFrame()
    return merge_progress_into_df(base, progress)


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


def field_line(glossary_key: str, label: str, value) -> None:
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"**{label}:** {value}")
    with c2:
        with st.popover("ℹ️"):
            st.write(GLOSSARY[glossary_key].short)


def refresh_data() -> None:
    st.session_state.export_df = load_merged_dataset()
    st.session_state.queue_pos = 0


def main():
    st.set_page_config(page_title="Pass 3 Curation", layout="wide")
    st.title("Pass 3 Chemical Name Curation")

    if "export_df" not in st.session_state:
        st.session_state.export_df = load_merged_dataset()

    df = st.session_state.export_df
    ncol = "Chemical" if "Chemical" in df.columns else "_name"

    # Sidebar
    st.sidebar.header("Reviewer")
    reviewer = st.sidebar.text_input(
        "Your name (required to review)",
        value=st.session_state.get("reviewer_name", ""),
        help=get_short("curation_reviewed"),
    )
    st.session_state.reviewer_name = reviewer.strip()

    sync_mode = st.session_state.get("sync_mode", "none")
    if sync_mode == "github":
        st.sidebar.success("Progress sync: GitHub")
    elif sync_mode == "local":
        st.sidebar.warning("Progress sync: local file only (set GITHUB_TOKEN for cloud)")
    elif sync_mode == "error":
        st.sidebar.error(f"Sync error: {st.session_state.get('sync_error', '')[:120]}")

    if st.sidebar.button("Refresh from GitHub", use_container_width=True):
        refresh_data()
        st.rerun()

    reviewed_total = int((df["Curation_Reviewed"].str.lower() == "yes").sum())
    st.sidebar.caption(f"**{reviewed_total}** rows reviewed globally")

    if GUIDE_PDF.exists():
        st.sidebar.download_button(
            "Download reviewer guide (PDF)",
            data=GUIDE_PDF.read_bytes(),
            file_name="Curation_Reviewer_Guide.pdf",
            mime="application/pdf",
        )

    queue_labels = [q["label"] for q in REVIEW_QUEUES]
    queue_by_label = {q["label"]: q for q in REVIEW_QUEUES}
    choice = st.sidebar.selectbox("Queue", queue_labels)
    qmeta = queue_by_label[choice]
    qid = qmeta["id"]
    readonly_queue = qmeta.get("readonly", False)

    base_mask = queue_mask(df, qid)
    sub_all = df[base_mask]
    sub_unreviewed = sub_all[~sub_all.apply(is_reviewed, axis=1)]

    st.sidebar.caption(qmeta["description"])
    st.sidebar.markdown("---")
    st.sidebar.write(f"**Total in queue:** {len(sub_all)}")
    st.sidebar.write(f"**Reviewed:** {len(sub_all) - len(sub_unreviewed)}")
    st.sidebar.write(f"**Remaining:** {len(sub_unreviewed)}")

    only_unreviewed = st.sidebar.checkbox(
        "Show only unreviewed",
        value=not readonly_queue,
        disabled=readonly_queue,
    )
    sub = sub_unreviewed if only_unreviewed else sub_all

    if sub.empty:
        st.success("No rows in this view — queue complete or try another filter.")
        return

    nav1, nav2, nav3 = st.sidebar.columns(3)
    if nav1.button("◀ Prev", use_container_width=True):
        st.session_state.queue_pos = max(0, st.session_state.queue_pos - 1)
    if nav3.button("Next ▶", use_container_width=True):
        st.session_state.queue_pos = min(len(sub) - 1, st.session_state.queue_pos + 1)
    if nav2.button("Next unreviewed", use_container_width=True):
        st.session_state.queue_pos = 0

    st.session_state.queue_pos = min(st.session_state.queue_pos, len(sub) - 1)
    st.session_state.queue_pos = max(0, st.session_state.queue_pos)
    row = sub.iloc[st.session_state.queue_pos]
    reviewed = is_reviewed(row)

    if row.get("CCAST_Approved") == "Yes":
        st.success(
            "**CCAST APPROVED** — SMARTS PASS + CCAST OK + Pass 1 + similarity ≥ 0.55. Reference example."
        )
    if reviewed:
        st.info(
            f"**REVIEWED** by {row.get('Curation_Reviewed_By', '')} "
            f"on {row.get('Curation_Reviewed_At', '')} — Action: {row.get('Curation_Action', '')}"
        )
    elif readonly_queue:
        st.info("**Reference row** — CCAST APPROVED tier; no review action required.")
    else:
        st.warning("**NOT REVIEWED** — This row still needs a reviewer decision.")

    st.caption(
        f"Queue: {choice} · Row {st.session_state.queue_pos + 1} of {len(sub)} · "
        f"Row_ID {row.get('Row_ID', row.name)}"
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Names and flags")
        field_line("archive_name", "Archive name (1947)", row.get(ncol, ""))
        field_line("resolved_name", "Resolved name", row.get("Resolved_Name", ""))
        field_line("status_resolved_pass1", "Pass 1/2 status", row.get("Status", ""))
        field_line("pass3", "Pass3_Status", row.get("Pass3_Status", ""))
        field_line(
            "smarts",
            "SMARTS",
            f"{row.get('Pass3_SMARTS_Result', '')} — {row.get('Pass3_SMARTS_Reason', '')}",
        )
        if "Pass3_CCAST_Flag" in row.index:
            flag = row.get("Pass3_CCAST_Flag", "")
            flag_key = {
                "OK": "ccast_ok",
                "SUSPICIOUS": "ccast_suspicious",
                "CONVERT_FAILED": "ccast_convert_failed",
                "LOW_SIMILARITY": "ccast_low_similarity",
            }.get(str(flag), "ccast_ok")
            field_line(flag_key, "CCAST flag", flag)
            field_line("similarity", "Jaro-Winkler score", row.get("JaroWinkler_Score", ""))
            field_line("iupac", "IUPAC (from SMILES)", row.get("STOUT_IUPAC", ""))
        field_line("ccast_approved", "CCAST_Approved tier", row.get("CCAST_Approved", "No"))
        field_line("smiles", "SMILES", "")
        st.code(str(row.get("SMILES", "")))

    with c2:
        img = mol_image(row.get("SMILES", ""))
        if img:
            st.image(img, caption="Structure from current SMILES")
        else:
            st.warning("No valid structure to draw")

    if readonly_queue:
        st.divider()
        st.caption("This queue is for reference. Switch to Queue 1 (NEEDS_REVIEW) to record decisions.")
    elif reviewed:
        st.divider()
        st.caption("This row is locked. Contact the team lead if it must be reopened.")
        if row.get("Curation_Notes"):
            st.write("**Reviewer notes:**", row.get("Curation_Notes"))
    else:
        st.divider()
        st.subheader("Your decision")
        action = st.radio(
            "Action",
            ["Confirm OK", "Mark PARTIAL_MATCH", "Reject (clear SMILES)", "Override SMILES"],
            help=get_short("actions_confirm"),
        )
        override = st.text_input("Override SMILES (if selected)", "")
        notes = st.text_input("Notes (optional)", "")

        if st.button("Apply to this row", type="primary"):
            if not reviewer:
                st.error("Enter your name in the sidebar before applying.")
            elif action == "Override SMILES" and not override.strip():
                st.error("Enter a SMILES string for override.")
            else:
                key = row.name
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                if action == "Confirm OK":
                    df.at[key, "Pass3_Status"] = "CURATED_OK"
                    df.at[key, "Curation_Action"] = "Confirm OK"
                elif action == "Mark PARTIAL_MATCH":
                    df.at[key, "Status"] = "PARTIAL_MATCH"
                    df.at[key, "Pass3_Status"] = "PARTIAL_MATCH"
                    df.at[key, "Curation_Action"] = "PARTIAL_MATCH"
                elif action == "Reject (clear SMILES)":
                    df.at[key, "SMILES"] = None
                    df.at[key, "Status"] = "FAILED_BOTH_PASSES"
                    df.at[key, "Pass3_Status"] = "REJECTED"
                    df.at[key, "Curation_Action"] = "Reject"
                elif action == "Override SMILES":
                    df.at[key, "SMILES"] = override.strip()
                    df.at[key, "Pass3_Status"] = "CURATED_OK"
                    df.at[key, "Curation_Action"] = "Override SMILES"
                df.at[key, "Curation_Reviewed"] = "Yes"
                df.at[key, "Curation_Reviewed_By"] = reviewer
                df.at[key, "Curation_Reviewed_At"] = now
                df.at[key, "Curation_Notes"] = notes.strip()

                config = config_from_streamlit_secrets(PROGRESS_LOCAL)
                record = row_to_progress_record(df, key)
                try:
                    mode = save_review(config, record)
                    st.session_state.export_df = df
                    st.success(f"Saved to {mode} — Row_ID {record['Row_ID']} locked for other reviewers.")
                    st.rerun()
                except AlreadyReviewedError as exc:
                    st.error(str(exc))
                    refresh_data()
                    st.rerun()
                except GitHubSyncError as exc:
                    st.error(f"Could not save to GitHub: {exc}")
                    st.session_state.export_df = df
                    st.warning("Change kept in this browser session only. Download Excel as backup.")

    st.divider()
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
