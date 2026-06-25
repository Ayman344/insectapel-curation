"""Smoke test: import chemresolve and run regression batteries."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    for mod in ("chemresolve.claims", "chemresolve.validate"):
        print("=" * 60)
        print(f"python -m {mod}")
        rc = subprocess.call([sys.executable, "-m", mod], cwd=ROOT)
        if rc != 0:
            raise SystemExit(rc)

    from chemresolve.io import load_pipeline_tables

    print("=" * 60)
    print("load_pipeline_tables (quiet summary)")
    obs, wl = load_pipeline_tables(ROOT, verbose=False)
    print(f"obs={len(obs)} rows  worklist={len(wl)} unique norm_keys")
    print("\nPackage smoke test OK")


if __name__ == "__main__":
    main()
