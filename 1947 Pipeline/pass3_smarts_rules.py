"""
RDKit SMARTS heuristics: check whether a SMILES plausibly matches name cues.

Used by pass3_local_validation.py on all RESOLVED_PASS1 and RESOLVED_PASS2 rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rdkit import Chem

from pass2_validation import ACID_ESTER, ACID_SALT, has_derivative_comma_suffix

# SMARTS patterns (RDKit)
PATTERNS = {
    "ester": "[#6]C(=O)O[#6]",
    "carboxylic_acid": "[CX3](=O)[OX2H1]",
    "carboxylate": "[CX3](=O)[O-]",
    "ether": "[#6][OD2]([#6])[#6]",
    "amine": "[NX3;H2,H1,H0;!$(NC=O)]",
    "ketone": "[#6][CX3](=O)[#6]",
    "alcohol": "[OX2H]",
    "phenol": "[OX2H][c]",
    "thiol": "[SX2H]",
    "amide": "[NX3][CX3](=[OX1])",
    "nitro": "[NX3+](=O)[O-]",
    "halide": "[F,Cl,Br,I]",
}

_COMPILED = {k: Chem.MolFromSmarts(v) for k, v in PATTERNS.items()}

ESTER_NAME = re.compile(
    r"\b(ester|diester|triester|monoester|tetraester|acetate|benzoate|propionate|"
    r"butyrate|laurate|palmitate|stearate|oleate|salicylate|phthalate|citrate|"
    r"lactate|tartrate|succinate|maleate|fumarate|carbonate)\b",
    re.I,
)
ACID_FREE = re.compile(r"\bacid\b", re.I)
AMINE_NAME = re.compile(r"\b(amine|ammonium|amino)\b", re.I)
ALCOHOL_NAME = re.compile(
    r"\b(alcohol|carbinol|diol|triol|glycol|glycerol)\b", re.I
)
KETONE_NAME = re.compile(r"\b(ketone|quinone)\b", re.I)
ETHER_NAME = re.compile(r"\b(ether|dioxane|oxane)\b", re.I)
AMIDE_NAME = re.compile(r"\b(amide|lactam)\b", re.I)
SALT_NAME = re.compile(
    r"\b(salt|sodium|potassium|calcium|magnesium|ammonium|copper|zinc)\b", re.I
)
MERCAPTAL_NAME = re.compile(r"\b(mercaptal|mercaptan|thio)\b", re.I)


@dataclass
class SmartsResult:
    result: str  # PASS, FAIL, SKIP, PARSE_ERROR
    expected: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    reason: str = ""


def _has_match(mol: Chem.Mol, key: str) -> bool:
    pat = _COMPILED.get(key)
    if pat is None:
        return False
    return mol.HasSubstructMatch(pat)


def _detect_expectations(name: str) -> list[str]:
    """Return SMARTS keys we expect to find based on the name."""
    n = str(name).strip()
    low = n.lower()
    if not n or n == "nan":
        return []

    expected: list[str] = []

    # Derivative comma names: ester/salt/carbonate suffix -> expect ester or salt, not free acid
    if ACID_ESTER.search(n) or ESTER_NAME.search(n):
        if not ACID_SALT.search(n):
            expected.append("ester")

    if ACID_SALT.search(n) or (
        SALT_NAME.search(n) and "acid" in low and has_derivative_comma_suffix(n)
    ):
        expected.append("carboxylate")

    if ACID_FREE.search(n) and "ester" not in low and not has_derivative_comma_suffix(n):
        # e.g. "Benzoic acid" without derivative suffix
        if not ACID_ESTER.search(n):
            expected.append("carboxylic_acid")

    if AMINE_NAME.search(n):
        expected.append("amine")
    if ALCOHOL_NAME.search(n):
        expected.append("alcohol")
    if KETONE_NAME.search(n):
        expected.append("ketone")
    if ETHER_NAME.search(n) and "ester" not in low:
        expected.append("ether")
    if AMIDE_NAME.search(n):
        expected.append("amide")
    if MERCAPTAL_NAME.search(n):
        expected.append("thiol")

    # Deduplicate preserving order
    seen = set()
    out = []
    for e in expected:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def validate_smiles_against_name(name: str, smiles: str) -> SmartsResult:
    """Compare name cues to SMARTS substructure presence in SMILES."""
    expected = _detect_expectations(name)
    if not expected:
        return SmartsResult(
            result="SKIP",
            reason="no strong functional-group cue in name for SMARTS check",
        )

    if not smiles or str(smiles).strip().lower() in ("nan", "none", ""):
        return SmartsResult(result="PARSE_ERROR", reason="missing SMILES")

    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return SmartsResult(result="PARSE_ERROR", reason="RDKit cannot parse SMILES")

    matched = [key for key in expected if _has_match(mol, key)]

    # Free acid should NOT be the only hit when ester expected
    if "ester" in expected and "ester" not in matched:
        return SmartsResult(
            result="FAIL",
            expected=expected,
            matched=matched,
            reason="name suggests ester/carbonate but SMILES has no ester linkage",
        )

    if "carboxylic_acid" in expected and "carboxylic_acid" not in matched and "carboxylate" not in matched:
        return SmartsResult(
            result="FAIL",
            expected=expected,
            matched=matched,
            reason="name suggests carboxylic acid but SMILES has no acid group",
        )

    if "carboxylate" in expected and "carboxylate" not in matched and "carboxylic_acid" not in matched:
        return SmartsResult(
            result="FAIL",
            expected=expected,
            matched=matched,
            reason="name suggests salt/carboxylate but SMILES has no carboxylate/acid",
        )

    for key in expected:
        if key in ("ester", "carboxylic_acid", "carboxylate"):
            continue
        if key not in matched:
            return SmartsResult(
                result="FAIL",
                expected=expected,
                matched=matched,
                reason=f"name suggests {key} but SMARTS pattern not found in SMILES",
            )

    return SmartsResult(
        result="PASS",
        expected=expected,
        matched=matched,
        reason="SMARTS patterns consistent with name cues",
    )
