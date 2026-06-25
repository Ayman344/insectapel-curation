"""Conservative normalization key and resolution worklist."""
from __future__ import annotations

import re
import unicodedata

import pandas as pd


def norm_key(name: str) -> str:
    """Normalize spelling only — never truncate or drop substituents."""
    s = unicodedata.normalize("NFKC", str(name))
    s = s.strip().lower()
    s = (
        s.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().strip(".")


def attach_norm_key(obs: pd.DataFrame) -> pd.DataFrame:
    out = obs.copy()
    out["norm_key"] = out["original_name"].map(norm_key)
    return out


def build_worklist(obs: pd.DataFrame) -> pd.DataFrame:
    """One row per unique norm_key with occurrence metadata."""
    if "norm_key" not in obs.columns:
        obs = attach_norm_key(obs)
    return (
        obs.groupby("norm_key")
        .agg(
            n_occurrences=("source_row_id", "size"),
            years=("source_year", lambda s: sorted(set(s))),
            example_names=("original_name", lambda s: sorted(set(s))[:3]),
            row_ids=("source_row_id", list),
        )
        .reset_index()
    )


def summarize_norm_key(obs: pd.DataFrame, worklist: pd.DataFrame | None = None) -> dict:
    wl = worklist if worklist is not None else build_worklist(obs)
    per_key_years = wl.set_index("norm_key")["years"].map(len)
    naive_n = obs["original_name"].str.lower().str.strip().nunique()
    key_n = obs["norm_key"].nunique()
    return {
        "total_occurrences": len(obs),
        "unique_naive": naive_n,
        "unique_norm_key": key_n,
        "keys_in_2plus_datasets": int((per_key_years >= 2).sum()),
        "keys_in_all_3": int((per_key_years == 3).sum()),
        "api_calls_saved_vs_naive": naive_n - key_n,
    }


def print_norm_key_summary(obs: pd.DataFrame, worklist: pd.DataFrame | None = None) -> dict:
    stats = summarize_norm_key(obs, worklist)
    print(f"Total occurrences:          {stats['total_occurrences']}")
    print(f"Unique (naive lower/strip): {stats['unique_naive']}")
    print(f"Unique (conservative key):  {stats['unique_norm_key']}")
    print(f"Keys in >=2 datasets:       {stats['keys_in_2plus_datasets']}")
    print(f"Keys in all 3 datasets:     {stats['keys_in_all_3']}")
    print(f"API calls saved vs naive:   {stats['api_calls_saved_vs_naive']}")
    return stats


def collapsed_spelling_groups(obs: pd.DataFrame, top_n: int = 10) -> list[tuple[str, list[str]]]:
    counts = obs.groupby("norm_key")["original_name"].nunique().sort_values(ascending=False)
    out = []
    for k, n in counts[counts > 1].head(top_n).items():
        spellings = sorted(obs.loc[obs["norm_key"] == k, "original_name"].unique())
        out.append((k, spellings))
    return out
