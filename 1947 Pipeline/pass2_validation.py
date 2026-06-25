"""Shared Pass 2 validation patterns and root-fallback guards."""
from __future__ import annotations

import re

DERIVATIVE_AFTER_COMMA = re.compile(
    r"\b(ester|diester|triester|monoester|tetraester|salt|sodium|potassium|"
    r"calcium|copper|zinc|ether|amide|anilide|toluidid|xylidid|mercaptal|"
    r"hydrogenated|condensate|residue|derivative|compound|carbonate)\b",
    re.I,
)
ACID_ESTER = re.compile(r"\bacid,\s+.+\bester\b", re.I)
ACID_SALT = re.compile(r"\bacid,\s+.+\bsalt\b", re.I)
MULTI_ESTER = re.compile(
    r"^(.+?)\s+acid,\s+(.+?)\s+(di|tri|mono|tetra)ester\b", re.I
)
MULTI_PART = re.compile(r",\s*.+,")

ROOT_FALLBACK_STRATEGIES = frozenset({"first_segment", "first_word"})
DERIVATIVE_FLIP_STRATEGIES = frozenset(
    {"acid_ester_flip", "acid_ester_flip_clean", "multi_ester_flip"}
)


def name_field(row) -> str:
    return str(row.get("Chemical") or row.get("_name") or "")


def first_segment(name: str) -> str:
    return str(name).split(",")[0].strip()


def comma_suffix(name: str) -> str:
    return name.split(",", 1)[1] if "," in name else ""


def has_derivative_comma_suffix(name: str) -> bool:
    suffix = comma_suffix(name)
    return bool(suffix and DERIVATIVE_AFTER_COMMA.search(suffix))


def should_skip_root_fallback(name: str, variants: list | None = None) -> bool:
    """
  Return True when first_segment / first_word would likely resolve a parent
  compound instead of the intended derivative.
    """
    raw = str(name).strip()
    if not raw:
        return True
    if ACID_ESTER.search(raw):
        return True
    if ACID_SALT.search(raw):
        return True
    if MULTI_ESTER.search(raw):
        return True
    if has_derivative_comma_suffix(raw):
        return True
    if variants and any(strategy in DERIVATIVE_FLIP_STRATEGIES for _, strategy in variants):
        return True
    return False


def classify_first_segment_risk(row) -> tuple[str, str]:
    name = name_field(row)
    resolved = str(row.get("Resolved_Name") or "")
    fs = first_segment(name)

    if not name or name == "nan":
        return "UNKNOWN", "missing name"

    if resolved and resolved.lower() != fs.lower():
        return "REVIEW", f"resolved '{resolved}' != first_segment '{fs}'"

    if ACID_ESTER.search(name):
        return "HIGH", "acid + ester name - likely resolved parent acid, not ester"

    if ACID_SALT.search(name):
        return "HIGH", "acid + salt - likely resolved free acid, not salt"

    if has_derivative_comma_suffix(name):
        return "HIGH", "comma suffix describes a derivative (ester/salt/carbonate/etc.)"

    if MULTI_PART.search(name):
        return "MEDIUM", "multiple comma-separated parts - first segment may be incomplete"

    if "(" in name and ")" in name:
        if "," in name and name.index("(") > name.index(","):
            return "LOW", "parenthetical after main comma segment"
        if fs.count("(") == 0 and "(" in name:
            return "MEDIUM", "parenthetical in later segment stripped from first_segment"

    if re.search(r"\bacid\b", fs, re.I) and "," in name:
        return "MEDIUM", "first segment is an acid but name has more after comma"

    if len(fs) < len(name) * 0.5 and len(name) > 30:
        return "MEDIUM", "first segment is much shorter than full name"

    return "LOW", "first segment appears to be the intended lookup name"


def classify_first_word_risk(row) -> tuple[str, str]:
    name = name_field(row)
    if not name or name == "nan":
        return "UNKNOWN", "missing name"

    if ACID_ESTER.search(name) or has_derivative_comma_suffix(name):
        return "HIGH", "derivative name truncated to first word"

    first = name.split()[0] if name.split() else ""
    if len(first) < len(name) * 0.4 and len(name) > 25:
        return "MEDIUM", "first word is much shorter than full name"

    return "LOW", "first word appears to be the intended lookup name"


def classify_rescue_risk(row) -> tuple[str, str]:
    strategy = str(row.get("Resolution_Strategy") or "")
    if strategy == "first_segment":
        return classify_first_segment_risk(row)
    if strategy == "first_word":
        return classify_first_word_risk(row)
    return "N/A", "not a root-fallback strategy"


def is_high_risk_rescue(row) -> tuple[bool, str]:
    strategy = str(row.get("Resolution_Strategy") or "")
    if strategy not in ROOT_FALLBACK_STRATEGIES:
        return False, ""
    risk, reason = classify_rescue_risk(row)
    return risk == "HIGH", reason
