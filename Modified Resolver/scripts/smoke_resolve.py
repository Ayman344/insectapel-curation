"""Phase 5a: smoke-test resolution on a small name sample."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chemresolve.cache import load_cache, save_cache
from chemresolve.io import load_pipeline_tables
from chemresolve.resolvers import resolve_name, resolver_availability

# Canary names from validate regression + a few hard 1947-style names
CANARY_NAMES = [
    "Acetaldehyde dioctyl mercaptal",
    "Acetic acid, o-allyl-p-cresol ester",
    "Abietic acid, ethyl ester",
    "Sodium benzoate",
    "Camphor",
    "Acetic acid, sodium salt",
    "Benzaldehyde diethyl acetal",
    "Cinnamamide",
    "Abietic acid, ester with 2-allyl-4-hydroxy-3-methyl-2-cyclopenten-l-one",
    "p-Nitrobenzoic acid, ethyl ester",
]


def pick_smoke_names(worklist, n_extra: int = 40) -> list[str]:
    """Canary set + first diverse names from worklist."""
    names = list(CANARY_NAMES)
    examples = worklist["example_names"].tolist()
    for group in examples:
        if isinstance(group, list) and group:
            candidate = str(group[0]).strip()
            if len(candidate) > 2 and candidate not in names:
                names.append(candidate)
        if len(names) >= n_extra + len(CANARY_NAMES):
            break
    return names[: n_extra + len(CANARY_NAMES)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test chemresolve resolvers")
    parser.add_argument("--limit", type=int, default=20, help="Max names to resolve")
    parser.add_argument("--data-dir", type=Path, default=ROOT)
    parser.add_argument("--cache", type=Path, default=ROOT / "cache" / "resolve_cache.json")
    args = parser.parse_args()

    print("Resolver availability:", resolver_availability())
    _, worklist = load_pipeline_tables(args.data_dir, verbose=False)
    names = pick_smoke_names(worklist)[: args.limit]

    cache = load_cache(args.cache)
    counts: dict[str, int] = {}
    print(f"\nResolving {len(names)} names...\n")
    for name in names:
        result = resolve_name(name, cache, use_outcome_cache=False)
        counts[result.status] = counts.get(result.status, 0) + 1
        line = (
            f"{result.status:10s} | {result.verdict or '-':11s} | "
            f"{result.resolver or '-':7s} | {name[:50]}"
        )
        print(line)
        if result.reject_log:
            print(f"           rejects: {len(result.reject_log)}")

    save_cache(cache, args.cache)
    print(f"\nSummary: {counts}")
    print(f"Cache saved: {args.cache}")


if __name__ == "__main__":
    main()
