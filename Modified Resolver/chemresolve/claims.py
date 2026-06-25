"""Name → ClaimSet parser (precision over recall)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ELEMENT_MORPHEMES = {
    "S": r"thio|mercapt|sulf|sulph|thia|thiol",
    "N": (
        r"amino|amine|ammonium|amide|imide|imine|nitro|nitrile|cyano|azo|hydrazi|oxime|"
        r"\burea\b|carbamate|pyridine|morpholine|piperidine|piperazine|quinoline"
    ),
    "Cl": r"chloro|chloride",
    "Br": r"bromo|bromide",
    "F": r"fluoro|fluoride",
    "I": r"\biodo|iodide",
    "P": r"phospho|phosph",
    "Si": r"\bsila|silane|silox|silyl",
}

ESTER_ATE = (
    r"acetate|benzoate|propionate|propanoate|butyrate|butanoate|laurate|"
    r"palmitate|stearate|oleate|salicylate|phthalate|citrate|lactate|"
    r"tartrate|succinate|maleate|fumarate|abietate|formate|carbonate"
)
SALT_WORDS = (
    r"sodium|potassium|calcium|magnesium|ammonium|zinc|copper|cupric|cuprous|"
    r"ferric|ferrous|iron|lithium|barium|aluminum|aluminium|lead|mercur|silver|"
    r"\bsalt\b|hydrochloride|hydrobromide|\bhcl\b|sulfate|sulphate|nitrate\b"
)
MIXTURE_WORDS = r"\bmixture\b|\bmixed\b|\bblend\b|\bcondensate\b|reaction product"


@dataclass
class ClaimSet:
    connectivity: str = "single"
    functional_groups: set = field(default_factory=set)
    elements: set = field(default_factory=set)
    notes: list = field(default_factory=list)


def _f(pat: str, s: str) -> bool:
    return re.search(pat, s, re.I) is not None


def extract_claims(name: str) -> ClaimSet:
    raw = str(name).strip()
    low = raw.lower()
    cs = ClaimSet()

    if _f(MIXTURE_WORDS, low):
        cs.connectivity = "mixture"
        cs.notes.append("mixture keyword")
    if _f(SALT_WORDS, low):
        cs.connectivity = "salt"
        cs.notes.append("salt keyword -> multi-fragment allowed")
    is_salt = cs.connectivity == "salt"

    ester_hit = (
        _f(r"\bacid\b.*\bester\b", low)
        or _f(r"\bester\s+with\b", low)
        or _f(r"\b(mono|di|tri|tetra)?ester\b", low)
        or _f(ESTER_ATE, low)
    )
    if ester_hit and not is_salt:
        cs.functional_groups.add("ester")
        cs.notes.append("ester linkage implied")
    if _f(ESTER_ATE, low) and is_salt:
        cs.functional_groups.add("carboxylate")
        cs.notes.append("acylate + salt -> carboxylate")

    if _f(r"mercaptal|dithioacetal", low):
        cs.functional_groups.add("dithioacetal")
        cs.notes.append("S,S-acetal (mercaptal)")
    elif _f(r"mercaptol|dithioketal", low):
        cs.functional_groups.add("dithioketal")
        cs.notes.append("S,S-ketal (mercaptol)")
    elif _f(r"\bacetal\b", low):
        cs.functional_groups.add("acetal")
        cs.notes.append("O,O-acetal")
    elif _f(r"\bketal\b", low):
        cs.functional_groups.add("ketal")

    if low.endswith("amide") or _f(r"amide|\bamid\b|lactam", low):
        cs.functional_groups.add("amide")
    if _f(r"\bamine\b|amino", low):
        cs.functional_groups.add("amine")
    if _f(r"\bnitro\b|dinitro|trinitro", low):
        cs.functional_groups.add("nitro")
    if _f(r"alcohol|carbinol|\bdiol\b|\btriol\b|glycol|glycerol|enediol|anediol", low):
        cs.functional_groups.add("alcohol")
    if _f(r"\bketone\b|quinone", low):
        cs.functional_groups.add("ketone")
    if _f(r"phenol|cresol|xylenol|catechol|resorcinol|hydroquinone", low):
        cs.functional_groups.add("phenol")

    if _f(r"\bacid\b", low) and "ester" not in low and not is_salt and "acetate" not in low:
        cs.functional_groups.add("carboxylic_acid")
    if is_salt and _f(r"\bacid\b", low):
        cs.functional_groups.add("carboxylate")

    if "ester" in cs.functional_groups:
        cs.functional_groups.discard("phenol")
        cs.functional_groups.discard("alcohol")
        cs.notes.append("suppressed free OH claims: partner is esterified")

    for el, pat in ELEMENT_MORPHEMES.items():
        if _f(pat, low):
            cs.elements.add(el)
    if {"ester", "carboxylate", "carboxylic_acid", "acetal", "ketone", "alcohol", "phenol"} & cs.functional_groups:
        cs.elements.add("O")
    if {"dithioacetal", "dithioketal"} & cs.functional_groups:
        cs.elements.add("S")
    if {"amide", "amine", "nitro"} & cs.functional_groups:
        cs.elements.add("N")
    return cs


def repair_ocr_digits(name: str) -> str:
    """Variant helper: fix common OCR digit confusions (l→1, O→0)."""
    s = re.sub(r"(?<=[\d,\-])l(?=[\-\s]|one|ol|$)", "1", str(name))
    s = re.sub(r"(?<=\d)O(?=\d)", "0", s)
    return s


if __name__ == "__main__":
    battery = [
        "Acetaldehyde dioctyl mercaptal",
        "Acetic acid, o-allyl-p-cresol ester",
        "Abietic acid, ester with 2-allyl-4-hydroxy-3-methyl-2-cyclopenten-l-one",
        "Acetaldehyde, allyl 2-ethylhexyl acetal",
        "Abietic acid",
        "Abietic acid, ethyl ester",
        "Acetic acid, sodium salt",
        "Ammonium dinitro-o-cresylate",
        "Cinnamamide",
        "Cinnamamide, p-chloro-N,N-diethyl-",
        "1,2-Tetradecanediol",
        "Benzaldehyde diethyl acetal",
        "p-Nitrobenzoic acid, ethyl ester",
        "Camphor",
        "Sodium benzoate",
        "o-Cresol",
        "Succinic acid, monoethyl ester",
    ]
    for n in battery:
        c = extract_claims(n)
        print(
            f"{n}\n    conn={c.connectivity:7s} "
            f"FG={sorted(c.functional_groups)} elem={sorted(c.elements)}"
        )
