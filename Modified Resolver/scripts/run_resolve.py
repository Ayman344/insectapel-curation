"""Phase 6: full, checkpointed resolution run over the worklist.

Resolves every unique name (optionally filtered to one source year) through the
validator-gated resolver, writing results incrementally so the job is resumable
and safe to interrupt.

Examples
--------
# Resolve only the 1947 dataset (names that occur in 1947):
python scripts/run_resolve.py --year 1947

# Resolve everything (all three years):
python scripts/run_resolve.py --year all

# Small dry run:
python scripts/run_resolve.py --year 1947 --limit 25

Outputs (under --out-dir, default ./outputs):
  resolved_<year>.csv        one row per unique name with structure + verdict
  resolved_<year>.partial.csv rewritten every --flush-every names (crash safety)
Cache (under --cache): resolver API calls + outcomes, reused across runs.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chemresolve.cache import load_cache, save_cache
from chemresolve.io import load_pipeline_tables
from chemresolve.resolvers import resolve_name, resolver_availability


def select_names(worklist: pd.DataFrame, year: str) -> list[tuple[str, str]]:
    """Return [(name_to_resolve, norm_key), ...] for the requested year.

    'name_to_resolve' is a representative original spelling (resolvers prefer the
    original casing/punctuation over the lowercased norm_key).
    """
    rows: list[tuple[str, str]] = []
    for _, r in worklist.iterrows():
        years = r["years"] if isinstance(r["years"], (list, tuple)) else [r["years"]]
        if year != "all" and year not in [str(y) for y in years]:
            continue
        examples = r["example_names"]
        name = None
        if isinstance(examples, (list, tuple)) and examples:
            name = str(examples[0]).strip()
        if not name:
            name = str(r["norm_key"]).strip()
        if not name or name.lower() in ("nan", "none", "-"):
            continue
        rows.append((name, str(r["norm_key"])))
    return rows


def row_from_result(result, name: str) -> dict:
    d = result.to_dict()
    reject_log = d.pop("reject_log", []) or []
    d["resolve_name_used"] = name
    d["reject_count"] = len(reject_log)
    d["reject_reasons"] = " | ".join(
        f"{e.get('resolver','?')}:{e.get('reason','')}" for e in reject_log
    )[:500]
    return d


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(records).to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Full validator-gated resolution run")
    parser.add_argument("--year", default="1947",
                        help="Source year to resolve: 1947 | 1954 | 1967 | all")
    parser.add_argument("--data-dir", type=Path, default=ROOT)
    parser.add_argument("--cache", type=Path, default=ROOT / "cache" / "resolve_cache.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--limit", type=int, default=0,
                        help="Resolve at most N names (0 = no limit)")
    parser.add_argument("--flush-every", type=int, default=100,
                        help="Save cache + partial CSV every N names")
    args = parser.parse_args()

    print("=" * 70, flush=True)
    print(f"run_resolve | year={args.year} | data-dir={args.data_dir}", flush=True)
    print(f"Resolver availability: {resolver_availability()}", flush=True)

    _, worklist = load_pipeline_tables(args.data_dir, verbose=False)
    names = select_names(worklist, args.year)
    if args.limit:
        names = names[: args.limit]
    total = len(names)
    print(f"Names to resolve for year={args.year}: {total}", flush=True)

    cache = load_cache(args.cache)
    out_final = args.out_dir / f"resolved_{args.year}.csv"
    out_partial = args.out_dir / f"resolved_{args.year}.partial.csv"

    records: list[dict] = []
    counts: dict[str, int] = {}
    t0 = time.monotonic()

    for i, (name, _nk) in enumerate(names, start=1):
        result = resolve_name(name, cache)  # uses outcome cache => resumable
        counts[result.status] = counts.get(result.status, 0) + 1
        records.append(row_from_result(result, name))

        if i % args.flush_every == 0 or i == total:
            save_cache(cache, args.cache)
            write_csv(records, out_partial)
            elapsed = time.monotonic() - t0
            rate = i / elapsed if elapsed else 0
            eta_min = (total - i) / rate / 60 if rate else 0
            print(
                f"[{i}/{total}] {counts} | {rate:.1f} names/s | ETA ~{eta_min:.0f} min",
                flush=True,
            )

    save_cache(cache, args.cache)
    write_csv(records, out_final)
    if out_partial.exists():
        out_partial.unlink()

    print("=" * 70, flush=True)
    print(f"DONE year={args.year} | total={total} | {counts}", flush=True)
    print(f"Results: {out_final}", flush=True)
    print(f"Cache:   {args.cache}", flush=True)


if __name__ == "__main__":
    main()
