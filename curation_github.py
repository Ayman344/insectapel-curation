"""Load and save curation_progress.csv via GitHub API or local file."""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

PROGRESS_FILE = "curation_progress.csv"

PROGRESS_COLUMNS = [
    "Row_ID",
    "Curation_Reviewed",
    "Curation_Reviewed_By",
    "Curation_Reviewed_At",
    "Curation_Action",
    "Curation_Notes",
    "SMILES",
    "Status",
    "Pass3_Status",
]

MERGE_COLUMNS = [
    "Curation_Reviewed",
    "Curation_Reviewed_By",
    "Curation_Reviewed_At",
    "Curation_Action",
    "Curation_Notes",
    "SMILES",
    "Status",
    "Pass3_Status",
]


class AlreadyReviewedError(Exception):
    pass


class GitHubSyncError(Exception):
    pass


@dataclass
class GitHubConfig:
    token: str | None = None
    repo: str = "Ayman344/insectapel-curation"
    branch: str = "main"
    progress_path: str = PROGRESS_FILE
    local_path: Path | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    @property
    def owner(self) -> str:
        return self.repo.split("/")[0]

    @property
    def repo_name(self) -> str:
        return self.repo.split("/", 1)[1]


def empty_progress() -> pd.DataFrame:
    return pd.DataFrame(columns=PROGRESS_COLUMNS)


def progress_to_csv_bytes(df: pd.DataFrame) -> bytes:
    out = df[PROGRESS_COLUMNS].copy() if not df.empty else empty_progress()
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def progress_from_csv_bytes(data: bytes) -> pd.DataFrame:
    if not data.strip():
        return empty_progress()
    df = pd.read_csv(io.BytesIO(data))
    for col in PROGRESS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[PROGRESS_COLUMNS]


def merge_progress_into_df(base: pd.DataFrame, progress: pd.DataFrame) -> pd.DataFrame:
    out = base.copy()
    if progress is None or progress.empty:
        return out
    prog = progress.drop_duplicates(subset=["Row_ID"], keep="last").copy()
    prog["Row_ID"] = pd.to_numeric(prog["Row_ID"], errors="coerce")
    prog = prog.dropna(subset=["Row_ID"])
    prog_by_id = prog.set_index("Row_ID")
    for idx, row in out.iterrows():
        rid = int(row["Row_ID"])
        if rid not in prog_by_id.index:
            continue
        p = prog_by_id.loc[rid]
        if str(p.get("Curation_Reviewed", "No")).strip().lower() != "yes":
            continue
        for col in MERGE_COLUMNS:
            val = p.get(col, "")
            if pd.isna(val) or str(val).strip() in ("", "nan"):
                continue
            if col == "SMILES" and str(val).lower() in ("none", "nan"):
                out.at[idx, col] = None
            else:
                out.at[idx, col] = val
    return out


def row_to_progress_record(df: pd.DataFrame, key: Any) -> dict:
    row = df.loc[key]
    smiles = row.get("SMILES", "")
    if pd.isna(smiles):
        smiles = ""
    return {
        "Row_ID": int(row["Row_ID"]),
        "Curation_Reviewed": str(row.get("Curation_Reviewed", "Yes")),
        "Curation_Reviewed_By": str(row.get("Curation_Reviewed_By", "")),
        "Curation_Reviewed_At": str(row.get("Curation_Reviewed_At", "")),
        "Curation_Action": str(row.get("Curation_Action", "")),
        "Curation_Notes": str(row.get("Curation_Notes", "")),
        "SMILES": str(smiles) if smiles != "" else "",
        "Status": str(row.get("Status", "")),
        "Pass3_Status": str(row.get("Pass3_Status", "")),
    }


def is_row_reviewed_in_progress(progress: pd.DataFrame, row_id: int) -> bool:
    if progress.empty:
        return False
    sub = progress[progress["Row_ID"] == row_id]
    if sub.empty:
        return False
    return str(sub.iloc[-1]["Curation_Reviewed"]).strip().lower() == "yes"


def upsert_progress_row(progress: pd.DataFrame, record: dict) -> pd.DataFrame:
    out = progress.copy() if not progress.empty else empty_progress()
    rid = int(record["Row_ID"])
    out = out[out["Row_ID"] != rid]
    out = pd.concat([out, pd.DataFrame([record])], ignore_index=True)
    return out[PROGRESS_COLUMNS]


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_progress_github(config: GitHubConfig) -> tuple[pd.DataFrame, str | None]:
    if not config.enabled:
        raise GitHubSyncError("GitHub token not configured")
    url = (
        f"https://api.github.com/repos/{config.owner}/{config.repo_name}"
        f"/contents/{config.progress_path}"
    )
    resp = requests.get(
        url,
        headers=_api_headers(config.token),
        params={"ref": config.branch},
        timeout=30,
    )
    if resp.status_code == 404:
        return empty_progress(), None
    if resp.status_code != 200:
        raise GitHubSyncError(f"GitHub fetch failed ({resp.status_code}): {resp.text[:200]}")
    payload = resp.json()
    content = base64.b64decode(payload["content"])
    return progress_from_csv_bytes(content), payload.get("sha")


def push_progress_github(
    config: GitHubConfig,
    progress: pd.DataFrame,
    sha: str | None,
    message: str,
) -> str | None:
    if not config.enabled:
        raise GitHubSyncError("GitHub token not configured")
    url = (
        f"https://api.github.com/repos/{config.owner}/{config.repo_name}"
        f"/contents/{config.progress_path}"
    )
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(progress_to_csv_bytes(progress)).decode("ascii"),
        "branch": config.branch,
    }
    if sha:
        body["sha"] = sha
    resp = requests.put(url, headers=_api_headers(config.token), json=body, timeout=30)
    if resp.status_code not in (200, 201):
        raise GitHubSyncError(f"GitHub push failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json().get("content", {}).get("sha")


def fetch_progress_local(path: Path) -> tuple[pd.DataFrame, str | None]:
    if not path.exists():
        return empty_progress(), None
    return progress_from_csv_bytes(path.read_bytes()), "local"


def push_progress_local(path: Path, progress: pd.DataFrame) -> None:
    path.write_bytes(progress_to_csv_bytes(progress))


def load_progress(config: GitHubConfig) -> tuple[pd.DataFrame, str | None, str]:
    if config.enabled:
        df, sha = fetch_progress_github(config)
        return df, sha, "github"
    if config.local_path:
        df, sha = fetch_progress_local(config.local_path)
        return df, sha, "local"
    return empty_progress(), None, "none"


def save_review(
    config: GitHubConfig,
    record: dict,
    *,
    max_retries: int = 3,
) -> str:
    row_id = int(record["Row_ID"])
    reviewer = record.get("Curation_Reviewed_By", "reviewer")
    action = record.get("Curation_Action", "review")
    message = f"Curation Row_ID {row_id} by {reviewer}: {action}"

    last_err: Exception | None = None
    for _ in range(max_retries):
        try:
            progress, sha, mode = load_progress(config)
            if is_row_reviewed_in_progress(progress, row_id):
                raise AlreadyReviewedError(
                    f"Row_ID {row_id} was already reviewed by another user. Refresh and skip."
                )
            progress = upsert_progress_row(progress, record)
            if mode == "github":
                push_progress_github(config, progress, sha, message)
                return "github"
            if config.local_path:
                push_progress_local(config.local_path, progress)
                return "local"
            raise GitHubSyncError("No GitHub token or local path configured for saving.")
        except AlreadyReviewedError:
            raise
        except GitHubSyncError as exc:
            last_err = exc
            if "409" in str(exc) or "422" in str(exc):
                continue
            raise
    raise GitHubSyncError(f"Could not save after {max_retries} tries: {last_err}")


def config_from_streamlit_secrets(local_path: Path) -> GitHubConfig:
    try:
        import streamlit as st

        secrets = st.secrets
        token = secrets.get("GITHUB_TOKEN") or secrets.get("github", {}).get("token")
        repo = secrets.get("GITHUB_REPO", "Ayman344/insectapel-curation")
        branch = secrets.get("GITHUB_BRANCH", "main")
        return GitHubConfig(
            token=str(token) if token else None,
            repo=str(repo),
            branch=str(branch),
            local_path=local_path,
        )
    except Exception:
        return GitHubConfig(local_path=local_path)
