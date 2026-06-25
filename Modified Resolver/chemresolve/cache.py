"""Persistent JSON cache for resolver API calls and final outcomes."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path("cache/resolve_cache.json")
_lock = threading.Lock()


def _empty() -> dict[str, Any]:
    return {"version": 1, "outcomes": {}, "api": {}}


def load_cache(path: Path | None = None) -> dict[str, Any]:
    p = path or _DEFAULT_PATH
    if not p.exists():
        return _empty()
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    if "outcomes" not in data:
        data = {"version": 1, "outcomes": data, "api": {}}
    return data


def save_cache(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def get_outcome(cache: dict[str, Any], norm_key: str) -> dict[str, Any] | None:
    return cache.get("outcomes", {}).get(norm_key)


def set_outcome(cache: dict[str, Any], norm_key: str, record: dict[str, Any]) -> None:
    cache.setdefault("outcomes", {})[norm_key] = record
    record["cached_at"] = datetime.now(timezone.utc).isoformat()


def api_cache_key(resolver: str, name: str) -> str:
    return f"{resolver}:{name.strip().lower()}"


def get_api(cache: dict[str, Any], resolver: str, name: str) -> str | None:
    entry = cache.get("api", {}).get(api_cache_key(resolver, name))
    if not entry:
        return None
    smi = entry.get("smiles")
    return str(smi) if smi else None


def set_api(cache: dict[str, Any], resolver: str, name: str, smiles: str | None) -> None:
    cache.setdefault("api", {})[api_cache_key(resolver, name)] = {
        "smiles": smiles,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
