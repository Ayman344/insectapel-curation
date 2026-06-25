"""Structure-vs-name validator (RDKit SMARTS + connectivity)."""
from __future__ import annotations

from dataclasses import dataclass, field

from rdkit import Chem
from rdkit import RDLogger

from .claims import ClaimSet, extract_claims

RDLogger.DisableLog("rdApp.*")

FG_SMARTS = {
    "ester": "[CX3](=[OX1])[OX2][#6]",
    "carboxylic_acid": "[CX3](=O)[OX2H1]",
    "carboxylate": "[$([CX3](=O)[O-]),$([CX3](=O)[OX2H1])]",
    "dithioacetal": "[CX4]([SX2][#6])[SX2][#6]",
    "dithioketal": "[CX4]([SX2][#6])[SX2][#6]",
    "acetal": "[CX4]([OX2][#6])[OX2][#6]",
    "ketal": "[CX4]([OX2][#6])[OX2][#6]",
    "amide": "[NX3][CX3]=[OX1]",
    "amine": "[NX3;!$([NX3][CX3]=[OX1]);!$([NX3](=O))]",
    "nitro": "[$([NX3](=O)=O),$([NX3+](=O)[O-])]",
    "alcohol": "[OX2H]",
    "phenol": "[OX2H][c]",
    "ketone": "[#6][CX3](=[OX1])[#6]",
    "ether": "[OX2]([#6])[#6]",
}
_COMPILED = {k: Chem.MolFromSmarts(v) for k, v in FG_SMARTS.items()}


@dataclass
class Verdict:
    status: str
    reasons: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)


def validate(name: str, smiles: str, claims: ClaimSet | None = None) -> Verdict:
    cs = claims or extract_claims(name)
    v = Verdict(status="UNVERIFIED")

    if not smiles or str(smiles).strip().lower() in ("nan", "none", ""):
        return Verdict("PARSE_ERROR", ["empty SMILES"])
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return Verdict("PARSE_ERROR", ["RDKit cannot parse SMILES"])

    n_frag = len(Chem.GetMolFrags(mol))

    if cs.connectivity == "single" and n_frag > 1:
        return Verdict(
            "REJECT",
            [f"name implies one molecule but SMILES has {n_frag} fragments"],
            {"connectivity": False},
        )
    v.checks["connectivity"] = True

    present = {a.GetSymbol() for a in mol.GetAtoms()}
    for el in cs.elements:
        if el not in present:
            return Verdict(
                "REJECT",
                [f"name implies element {el} but SMILES has none"],
                {"element_missing": el},
            )
    if cs.elements:
        v.checks["elements"] = True

    fg_confirmed = []
    for fg in cs.functional_groups:
        patt = _COMPILED.get(fg)
        if patt is None:
            continue
        if mol.HasSubstructMatch(patt):
            fg_confirmed.append(fg)
        else:
            if cs.connectivity == "salt" and fg in ("carboxylate",):
                continue
            return Verdict(
                "REJECT",
                [f"name implies {fg} but SMILES lacks that group"],
                {"fg_missing": fg},
            )
    v.checks["functional_groups"] = fg_confirmed

    if fg_confirmed:
        v.status = "VERIFIED"
        v.reasons.append(f"structure confirms: {', '.join(sorted(fg_confirmed))}")
    else:
        v.status = "UNVERIFIED"
        v.reasons.append("passed all applicable checks; no strong functional-group cue to confirm")
    return v


if __name__ == "__main__":
    CASES = [
        ("Acetaldehyde dioctyl mercaptal", "CCCCCCCSC(C)SCCCCCCCC", "VERIFIED"),
        ("Acetaldehyde dioctyl mercaptal", "CCCCCCCOCSCCCCCCCC", "REJECT"),
        ("Acetic acid, o-allyl-p-cresol ester", "CC(=O)Oc1ccc(C)cc1CC=C", "VERIFIED"),
        ("Acetic acid, o-allyl-p-cresol ester", "CC(O)=O.Cc1ccc(O)c(CC=C)c1", "REJECT"),
        ("Sodium benzoate", "O=C([O-])c1ccccc1.[Na+]", "VERIFIED"),
        ("Acetic acid, sodium salt", "CC(=O)[O-].[Na+]", "VERIFIED"),
        ("Cinnamamide, p-chloro-N,N-diethyl-", "CCN(CC)C(=O)/C=C/c1ccc(Cl)cc1", "VERIFIED"),
        ("Camphor", "CC1(C)C2CCC1(C)C(=O)C2", "UNVERIFIED"),
        ("p-Nitrobenzoic acid, ethyl ester", "CCOC(=O)c1ccc([N+](=O)[O-])cc1", "VERIFIED"),
        ("Benzaldehyde diethyl acetal", "CCOC(OCC)c1ccccc1", "VERIFIED"),
    ]
    ok = True
    for name, smi, exp in CASES:
        got = validate(name, smi)
        flag = "PASS" if got.status == exp else "**FAIL**"
        if got.status != exp:
            ok = False
        print(
            f"[{flag}] want={exp:11s} got={got.status:11s} | {name[:42]:42s} | "
            f"{got.reasons[0][:60]}"
        )
    print("\nALL REGRESSION TESTS PASS" if ok else "\nSOME TESTS FAILED")
