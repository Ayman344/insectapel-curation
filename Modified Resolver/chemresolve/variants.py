"""Conservative name variant generator (no truncating strategies)."""
from __future__ import annotations

import re

from chemresolve.claims import repair_ocr_digits

ARCHAIC_DICT = {
    "mercaptal": "dithioacetal",
    "mercaptol": "dithioketal",
    "mercaptan": "thiol",
    "furfurol": "furfural",
    "formol": "formaldehyde",
    "chloral": "trichloroacetaldehyde",
    "paraldehyde": "2,4,6-trimethyl-1,3,5-trioxane",
    "cellosolve": "2-ethoxyethanol",
    "carbitol": "2-(2-ethoxyethoxy)ethanol",
    "dioxane": "1,4-dioxane",
    "dioxan": "1,4-dioxane",
    "cresol": "methylphenol",
    "xylenol": "dimethylphenol",
    "catechol": "1,2-benzenediol",
    "resorcinol": "1,3-benzenediol",
    "hydroquinone": "1,4-benzenediol",
}

ACID_TO_ESTER = {
    "acetic": "acetate",
    "propionic": "propionate",
    "butyric": "butyrate",
    "caproic": "caproate",
    "caprylic": "caprylate",
    "capric": "caprate",
    "lauric": "laurate",
    "palmitic": "palmitate",
    "stearic": "stearate",
    "oleic": "oleate",
    "benzoic": "benzoate",
    "salicylic": "salicylate",
    "phthalic": "phthalate",
    "succinic": "succinate",
    "citric": "citrate",
    "tartaric": "tartrate",
    "maleic": "maleate",
    "fumaric": "fumarate",
    "formic": "formate",
    "carbonic": "carbonate",
    "lactic": "lactate",
    "abietic": "abietate",
    "cinnamic": "cinnamate",
    "nicotinic": "nicotinate",
    "n-caproic": "hexanoate",
    "iso-butyric": "2-methylpropanoate",
}

PREFIX_STRIP = {
    "n-": "",
    "sec-": "",
    "tert-": "",
    "iso-": "iso",
    "dl-": "",
    "d-": "",
    "l-": "",
    "o-": "2-",
    "m-": "3-",
    "p-": "4-",
}


def _acid_key_to_ester_suffix(acid_part: str) -> str | None:
    acid_key = acid_part.lower().replace("acid", "").strip()
    if acid_key in ACID_TO_ESTER:
        return ACID_TO_ESTER[acid_key]
    for prefix in ("n-", "iso-", "sec-", "tert-"):
        if acid_key.startswith(prefix):
            stripped = acid_key[len(prefix) :]
            if stripped in ACID_TO_ESTER:
                return ACID_TO_ESTER[stripped]
    if acid_key.endswith("ic") and len(acid_key) > 3:
        return acid_key[:-2] + "ate"
    return None


def generate_variants(name: str) -> list[tuple[str, str]]:
    """Return ordered (variant, strategy) pairs. No first_segment / split_and_*."""
    raw = str(name).strip()
    low = raw.lower()
    variants: list[tuple[str, str]] = [(raw, "original")]

    ocr = repair_ocr_digits(raw)
    if ocr != raw:
        variants.append((ocr, "ocr_digit_repair"))

    acid_ester_match = re.match(r"^(.+?)\s+acid,\s+(.+?)\s+ester\s*(.*)$", raw, re.IGNORECASE)
    if acid_ester_match:
        acid_part = acid_ester_match.group(1).strip()
        alcohol_part = acid_ester_match.group(2).strip()
        ester_suffix = _acid_key_to_ester_suffix(acid_part)
        if ester_suffix:
            flipped = f"{alcohol_part} {ester_suffix}".strip()
            variants.append((flipped, "acid_ester_flip"))
            clean_alcohol = re.sub(r"^[nN]-", "", alcohol_part)
            if clean_alcohol != alcohol_part:
                variants.append((f"{clean_alcohol} {ester_suffix}", "acid_ester_flip_clean"))

    for old_term, new_term in ARCHAIC_DICT.items():
        if old_term.lower() in low:
            replaced = re.sub(re.escape(old_term), new_term, raw, flags=re.IGNORECASE)
            variants.append((replaced, f"archaic_sub:{old_term}"))

    stripped = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    if stripped and stripped != raw:
        variants.append((stripped, "strip_parens"))

    for prefix, replacement in PREFIX_STRIP.items():
        pattern = r"\b" + re.escape(prefix)
        if re.search(pattern, raw, re.IGNORECASE):
            normalized = re.sub(pattern, replacement, raw, flags=re.IGNORECASE).strip()
            if normalized != raw:
                variants.append((normalized, f"prefix_norm:{prefix}"))

    if "," in raw:
        no_comma = re.sub(r"\s+", " ", raw.replace(",", " ")).strip()
        variants.append((no_comma, "comma_to_space"))

    multi_ester = re.match(
        r"^(.+?)\s+acid,\s+(.+?)\s+(di|tri|mono|tetra)ester\s*$", raw, re.IGNORECASE
    )
    if multi_ester:
        acid_part = multi_ester.group(1).strip()
        polyol_part = multi_ester.group(2).strip()
        multiplier = multi_ester.group(3).strip().lower()
        ester_suffix = _acid_key_to_ester_suffix(acid_part)
        if ester_suffix:
            variants.append((f"{polyol_part} {multiplier}{ester_suffix}", "multi_ester_flip"))

    of_match = re.match(r"^(.+?)\s+of\s+(.+)$", raw, re.IGNORECASE)
    if of_match:
        variants.append((f"{of_match.group(2)} {of_match.group(1)}", "of_rearrange"))

    no_stereo = re.sub(
        r"^[dlDL]+-|^\(\+/?-?\)-?|^\([RS]\)-?|^cis-|^trans-|^alpha-|^beta-|^meso-",
        "",
        raw,
    ).strip()
    if no_stereo and no_stereo != raw:
        variants.append((no_stereo, "strip_stereo"))

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for v, strat in variants:
        v_clean = v.strip().rstrip(",").strip()
        key = v_clean.lower()
        if v_clean and key not in seen and len(v_clean) > 2:
            seen.add(key)
            unique.append((v_clean, strat))
    return unique
