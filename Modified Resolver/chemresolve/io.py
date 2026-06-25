"""Load and profile the three USDA repellent datasets."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DATASET_SPEC: dict[str, tuple[str, str]] = {
    "1947": ("1947-King-USDA_Dataset.csv", "Chemical"),
    "1954": ("1954-King_dataset.csv", "Chemical"),
    "1967": ("1967_USDA_datasetcsv.csv", "MATERIAL"),
}


def read_csv_any_encoding(path: os.PathLike | str) -> pd.DataFrame:
    last: Exception | None = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str)
        except Exception as exc:
            last = exc
    raise last  # type: ignore[misc]


def profile_datasets(data_dir: os.PathLike | str = ".") -> None:
    """Print schema summary for each CSV (Phase 0)."""
    for year, (fname, _) in DATASET_SPEC.items():
        path = Path(data_dir) / fname
        print("=" * 70)
        print(f"{year}: {fname}")
        if not path.exists():
            print("  !! NOT FOUND at this path")
            continue
        df = read_csv_any_encoding(path)
        print(f"  rows={len(df)}  cols={len(df.columns)}")
        print(f"  columns: {list(df.columns)}")
        print("  non-null counts:")
        print(df.notna().sum().to_string().replace("\n", "\n    "))
        print("  first 3 rows:")
        print(df.head(3).to_string()[:1500])


def load_observations(
    data_dir: os.PathLike | str = ".",
    *,
    verbose: bool = True,
) -> pd.DataFrame:
    """Build tidy long observation table with year-namespaced traits."""
    frames: list[pd.DataFrame] = []
    for year, (fname, name_col) in DATASET_SPEC.items():
        path = Path(data_dir) / fname
        df = read_csv_any_encoding(path)

        junk = [c for c in df.columns if str(c).startswith("Unnamed")]
        if verbose:
            for c in junk:
                vals = df[c].dropna().tolist()
                print(f"[{year}] dropping junk column {c!r}; non-null values seen: {vals[:5]}")
        df = df.drop(columns=junk)

        trait_cols = [c for c in df.columns if c != name_col]
        out = pd.DataFrame(
            {
                "source_year": year,
                "source_row_id": [f"{year}_{i}" for i in range(len(df))],
                "original_name": df[name_col].astype(str).str.strip(),
            }
        )
        for c in trait_cols:
            out[f"y{year}_{c}"] = df[c]
        frames.append(out)

    obs = pd.concat(frames, ignore_index=True)
    if verbose:
        print(f"\nObservation table: {len(obs)} rows  |  {obs['source_year'].value_counts().to_dict()}")
        print(f"Columns: {list(obs.columns)}")
    return obs


def load_pipeline_tables(
    data_dir: os.PathLike | str = ".",
    *,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load observations, attach norm_key, and build worklist."""
    from chemresolve.normalize import attach_norm_key, build_worklist

    obs = load_observations(data_dir, verbose=verbose)
    obs = attach_norm_key(obs)
    worklist = build_worklist(obs)
    if verbose:
        from chemresolve.normalize import print_norm_key_summary

        print_norm_key_summary(obs, worklist)
    return obs, worklist
