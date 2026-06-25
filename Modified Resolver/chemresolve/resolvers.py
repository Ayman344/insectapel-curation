"""PubChem, OPSIN, and CIRpy lookups — each hit gated by validate()."""
from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable

import requests
from rdkit import Chem

from chemresolve.cache import get_api, get_outcome, set_api, set_outcome
from chemresolve.normalize import norm_key
from chemresolve.validate import validate
from chemresolve.variants import generate_variants

try:
    import cirpy

    _HAS_CIRPY = True
except ImportError:
    _HAS_CIRPY = False

try:
    from py2opsin import py2opsin

    _HAS_OPSIN = True
except ImportError:
    _HAS_OPSIN = False


@dataclass
class ResolutionResult:
    original_name: str
    norm_key: str
    status: str  # resolved | quarantine | failed | cached
    smiles: str | None = None
    inchikey: str | None = None
    verdict: str | None = None
    resolver: str | None = None
    variant_used: str | None = None
    strategy: str | None = None
    reject_log: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_name": self.original_name,
            "norm_key": self.norm_key,
            "status": self.status,
            "smiles": self.smiles,
            "inchikey": self.inchikey,
            "verdict": self.verdict,
            "resolver": self.resolver,
            "variant_used": self.variant_used,
            "strategy": self.strategy,
            "reject_log": self.reject_log,
        }


class RateLimiter:
    def __init__(self, min_interval_sec: float = 0.21):
        self._min = min_interval_sec
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        gap = self._min - (now - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


_pubchem_limiter = RateLimiter(0.21)


def smiles_to_inchikey(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToInchiKey(mol)


def lookup_pubchem(name: str, *, session: requests.Session | None = None) -> str | None:
    _pubchem_limiter.wait()
    sess = session or requests
    encoded = urllib.parse.quote(name, safe="")
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{encoded}/property/CanonicalSMILES/TXT"
    )
    try:
        resp = sess.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        return text if text and text.lower() != "n/a" else None
    except requests.RequestException:
        return None


def lookup_opsin(name: str) -> str | None:
    if not _HAS_OPSIN:
        return None
    try:
        smi = py2opsin(name)
        return str(smi).strip() if smi else None
    except Exception:
        return None


def lookup_cirpy(name: str) -> str | None:
    if not _HAS_CIRPY:
        return None
    try:
        smi = cirpy.resolve(name, "smiles")
        return str(smi).strip() if smi else None
    except Exception:
        return None


RESOLVER_FUNCS: dict[str, Callable[[str], str | None]] = {
    "pubchem": lookup_pubchem,
    "opsin": lookup_opsin,
    "cirpy": lookup_cirpy,
}


def _lookup_with_cache(
    cache: dict[str, Any],
    resolver: str,
    variant: str,
    lookup_fn: Callable[[str], str | None],
) -> str | None:
    cached = get_api(cache, resolver, variant)
    if cached is not None:
        return cached or None
    smi = lookup_fn(variant)
    set_api(cache, resolver, variant, smi or "")
    return smi


def resolve_name(
    name: str,
    cache: dict[str, Any],
    *,
    resolvers: tuple[str, ...] = ("pubchem", "opsin", "cirpy"),
    use_outcome_cache: bool = True,
) -> ResolutionResult:
    """Resolve one chemical name with validation gating."""
    nk = norm_key(name)
    if use_outcome_cache:
        hit = get_outcome(cache, nk)
        if hit and hit.get("status") == "resolved":
            return ResolutionResult(
                original_name=name,
                norm_key=nk,
                status="cached",
                smiles=hit.get("smiles"),
                inchikey=hit.get("inchikey"),
                verdict=hit.get("verdict"),
                resolver=hit.get("resolver"),
                variant_used=hit.get("variant_used"),
                strategy=hit.get("strategy"),
                reject_log=hit.get("reject_log", []),
            )

    reject_log: list[dict[str, str]] = []
    for variant, strategy in generate_variants(name):
        for resolver in resolvers:
            lookup_fn = RESOLVER_FUNCS.get(resolver)
            if lookup_fn is None:
                continue
            smiles = _lookup_with_cache(cache, resolver, variant, lookup_fn)
            if not smiles:
                continue
            verdict = validate(name, smiles)
            if verdict.status == "REJECT":
                reject_log.append(
                    {
                        "variant": variant,
                        "strategy": strategy,
                        "resolver": resolver,
                        "verdict": verdict.status,
                        "reason": verdict.reasons[0] if verdict.reasons else "",
                    }
                )
                continue
            if verdict.status in ("VERIFIED", "UNVERIFIED"):
                ik = smiles_to_inchikey(smiles)
                result = ResolutionResult(
                    original_name=name,
                    norm_key=nk,
                    status="resolved",
                    smiles=smiles,
                    inchikey=ik,
                    verdict=verdict.status,
                    resolver=resolver,
                    variant_used=variant,
                    strategy=strategy,
                    reject_log=reject_log,
                )
                set_outcome(cache, nk, result.to_dict())
                return result

    status = "quarantine" if reject_log else "failed"
    result = ResolutionResult(
        original_name=name,
        norm_key=nk,
        status=status,
        reject_log=reject_log,
    )
    set_outcome(cache, nk, result.to_dict())
    return result


def resolver_availability() -> dict[str, bool]:
    return {"pubchem": True, "opsin": _HAS_OPSIN, "cirpy": _HAS_CIRPY}
