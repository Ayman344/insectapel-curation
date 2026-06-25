"""Chemical name resolution rebuild — importable package."""

from chemresolve.claims import ClaimSet, extract_claims, repair_ocr_digits
from chemresolve.resolvers import ResolutionResult, resolve_name, resolver_availability
from chemresolve.validate import Verdict, validate
from chemresolve.variants import generate_variants

__all__ = [
    "ClaimSet",
    "ResolutionResult",
    "Verdict",
    "extract_claims",
    "generate_variants",
    "repair_ocr_digits",
    "resolve_name",
    "resolver_availability",
    "validate",
]
