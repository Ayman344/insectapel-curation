"""
Shared glossary for the Pass 3 curation app and reviewer PDF.

Each entry:
  - title: display label
  - short: one or two sentences (app popover / tooltip)
  - long: plain-language paragraph(s) for the PDF guide
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GlossaryEntry:
    key: str
    title: str
    short: str
    long: str


GLOSSARY: dict[str, GlossaryEntry] = {
    "purpose": GlossaryEntry(
        key="purpose",
        title="Why we are reviewing",
        short=(
            "We converted historical 1947 repellent names into chemical structures (SMILES). "
            "Your job is to check whether each structure truly matches the original name."
        ),
        long=(
            "The 1947 King USDA dataset lists chemical names tested as insect repellents. "
            "Modern machine-learning needs structures, not just names. We used computer programs "
            "to look up each name and assign a SMILES code (a line notation for a molecular structure). "
            "Automated checks catch many errors but not all. Human reviewers confirm, correct, or "
            "reject each assignment before the data is used for modeling."
        ),
    ),
    "archive_name": GlossaryEntry(
        key="archive_name",
        title="Archive name (1947 original)",
        short=(
            "The exact chemical name from the 1947 USDA dataset. "
            "This is the ground truth you compare everything against."
        ),
        long=(
            "The archive name is stored in the Chemical column. It is the wording from the 1947 "
            "King USDA repellent study. Spelling, punctuation, and archaic naming (e.g. old trivial "
            "names or abbreviations) are preserved. When you review a row, ask: does the drawn "
            "structure reasonably correspond to this historical name?"
        ),
    ),
    "resolved_name": GlossaryEntry(
        key="resolved_name",
        title="Resolved name",
        short=(
            "The name returned by online chemical databases when we looked up the archive name. "
            "It may differ in spelling or style from the 1947 wording."
        ),
        long=(
            "During Pass 1 and Pass 2, we sent the archive name to public chemistry databases "
            "(mainly CIRpy / PubChem-style lookups). The resolved name is what those services "
            "returned as their best match. A different spelling does not always mean a wrong "
            "structure — but a completely unrelated name is a red flag. Compare resolved name, "
            "archive name, and the structure picture together."
        ),
    ),
    "smiles": GlossaryEntry(
        key="smiles",
        title="SMILES",
        short=(
            "A text code describing the molecular structure. "
            "The app draws a 2D picture from this code."
        ),
        long=(
            "SMILES (Simplified Molecular Input Line Entry System) is a standard way to write "
            "a structure as text, e.g. CCO for ethanol. If the SMILES is wrong, every downstream "
            "check (SMARTS, IUPAC, modeling) will be wrong too. When in doubt, use Override SMILES "
            "only if you are confident in the correction, or Reject if no reliable structure exists."
        ),
    ),
    "pass1": GlossaryEntry(
        key="pass1",
        title="Pass 1",
        short="Direct database lookup of the archive name. About 4,014 names resolved.",
        long=(
            "Pass 1 sent each archive name to chemical identifier services with no extra "
            "manipulation. Status RESOLVED_PASS1 means a structure was found on the first try. "
            "These are generally the most trustworthy automatic hits, though some still need "
            "SMARTS or manual review."
        ),
    ),
    "pass2": GlossaryEntry(
        key="pass2",
        title="Pass 2",
        short=(
            "Second pass with spelling variants and smart retries. "
            "Status RESOLVED_PASS2. Higher risk than Pass 1."
        ),
        long=(
            "Pass 2 tried normalized spellings, fragments, and alternate forms of names that "
            "failed Pass 1. About 637 structures were found this way. Validation_Risk may show "
            "HIGH, MEDIUM, or LOW. HIGH-risk Pass 2 hits were later downgraded to PARTIAL_MATCH "
            "in a correction step. Treat Pass 2 rows with more skepticism than Pass 1."
        ),
    ),
    "pass3": GlossaryEntry(
        key="pass3",
        title="Pass 3",
        short=(
            "Validation pass: SMARTS rules, optional rescue lookups, and CCAST reverse naming."
        ),
        long=(
            "Pass 3 does not usually find new names from scratch. It checks structures we already "
            "have. Step 1 (local): SMARTS rules test whether the structure contains chemical "
            "groups suggested by the name; OPSIN/ChemSpider may rescue a few failures. "
            "Step 2 (CCAST GPU): converts SMILES back to a systematic IUPAC name and compares "
            "it to the archive name. Pass3_Status summarizes the outcome (VALIDATED_OK, "
            "NEEDS_REVIEW, etc.)."
        ),
    ),
    "smarts": GlossaryEntry(
        key="smarts",
        title="SMARTS check",
        short=(
            "A pattern test: does the structure contain the functional groups the name implies? "
            "FAIL means mismatch; SKIP means no rule applied."
        ),
        long=(
            "SMARTS is a language for describing substructures within a molecule. We wrote rules "
            "such as 'if the name says alcohol, the structure should contain an -OH group.' "
            "PASS: rule ran and matched. FAIL: rule ran and did not match — review required. "
            "SKIP: no rule applied (not proof of correctness). PARSE_ERROR: SMILES could not "
            "be read. NEEDS_REVIEW queue is mostly SMARTS FAIL rows."
        ),
    ),
    "iupac": GlossaryEntry(
        key="iupac",
        title="IUPAC name (reverse-generated)",
        short=(
            "A systematic name generated from the SMILES on CCAST. "
            "Shown as STOUT_IUPAC in the data."
        ),
        long=(
            "IUPAC names are standardized systematic chemical names. On CCAST we used a machine-learning "
            "model (chemical-converters) to go from SMILES to IUPAC — the reverse of naming. "
            "The result is a sanity check, not a ground-truth label. Old 1947 trivial names "
            "will often look very different from modern IUPAC strings even when the structure is correct."
        ),
    ),
    "similarity": GlossaryEntry(
        key="similarity",
        title="Similarity score (Jaro-Winkler)",
        short=(
            "A number from 0 to 1 measuring how alike two text strings are. "
            "Higher means more similar wording. Not proof the structure is correct."
        ),
        long=(
            "Jaro-Winkler compares the archive name to the generated IUPAC name (and sometimes "
            "to the resolved name). Scores near 1.0 mean similar spelling; scores below ~0.45 "
            "trigger SUSPICIOUS or LOW_SIMILARITY flags. Shared words can inflate scores even "
            "when structures are wrong — always prioritize the structure drawing and archive name "
            "over this number."
        ),
    ),
    "ccast_ok": GlossaryEntry(
        key="ccast_ok",
        title="CCAST flag: OK",
        short=(
            "IUPAC was generated and similarity was above the low threshold. "
            "A weak positive signal — still verify the structure visually."
        ),
        long=(
            "OK means the reverse naming step produced an IUPAC string and the Jaro-Winkler "
            "score was not in the lowest band. Many OK rows are fine, but hundreds of SMARTS FAIL "
            "rows also show CCAST OK because shared words in names can score well. Never use OK "
            "alone to skip review when SMARTS failed."
        ),
    ),
    "ccast_suspicious": GlossaryEntry(
        key="ccast_suspicious",
        title="CCAST flag: SUSPICIOUS",
        short="IUPAC was generated but similarity to the archive name is low. Review recommended.",
        long=(
            "SUSPICIOUS indicates the generated IUPAC name does not resemble the 1947 archive "
            "name very closely. This can mean a wrong structure, an archaic trivial name, or "
            "both. Open the structure image and judge whether it fits the archive name."
        ),
    ),
    "ccast_convert_failed": GlossaryEntry(
        key="ccast_convert_failed",
        title="CCAST flag: CONVERT_FAILED",
        short="The model could not generate an IUPAC name from this SMILES (GPU/runtime error).",
        long=(
            "CONVERT_FAILED means the reverse naming model returned nothing — often due to CUDA "
            "errors or difficult structures. The SMILES may still be valid. Review the structure "
            "on its own merits; do not assume failure because IUPAC is missing."
        ),
    ),
    "ccast_low_similarity": GlossaryEntry(
        key="ccast_low_similarity",
        title="CCAST flag: LOW_SIMILARITY",
        short="Very low text similarity between archive name and IUPAC. Strongest CCAST warning.",
        long=(
            "LOW_SIMILARITY is the strictest text-based flag. Treat these like SUSPICIOUS but "
            "with even more caution. Only a handful of rows have this flag in the current dataset."
        ),
    ),
    "ccast_approved": GlossaryEntry(
        key="ccast_approved",
        title="CCAST APPROVED (unquestionable tier)",
        short=(
            "Highest-confidence rows: SMARTS PASS, CCAST OK, Pass 1 lookup, "
            "and similarity >= 0.55. Reference only — no review required."
        ),
        long=(
            "CCAST APPROVED is our strict gold-standard tier (~1,044 rows). A row must meet ALL "
            "of: (1) Pass3_CCAST_Flag is OK, (2) SMARTS result is PASS (not SKIP or FAIL), "
            "(3) Status is RESOLVED_PASS1 (direct first-pass lookup, not Pass 2 retry), and "
            f"(4) Jaro-Winkler similarity between archive name and IUPAC is at least 0.55. "
            "Show these to reviewers as examples of good matches. They are not in the mandatory "
            "review queue. CCAST OK alone is weaker — hundreds of SMARTS-fail rows also show CCAST OK."
        ),
    ),
    "validated_ok": GlossaryEntry(
        key="validated_ok",
        title="VALIDATED_OK",
        short=(
            "Automated Pass 3 checks passed or were skipped without failure. "
            "Optional spot-check; no mandatory review unless you see a problem."
        ),
        long=(
            "VALIDATED_OK means SMARTS returned PASS or SKIP (no FAIL). These ~4,114 rows are "
            "the lowest-priority queue. You may browse them to spot obvious mistakes, but focus "
            "first on NEEDS_REVIEW. SKIP rows were not proven correct — only that no rule flagged them."
        ),
    ),
    "needs_review": GlossaryEntry(
        key="needs_review",
        title="NEEDS_REVIEW",
        short="SMARTS failed — structure may not match the name. Primary review queue.",
        long=(
            "NEEDS_REVIEW marks SMARTS FAIL rows (~537). This is the main workload. For each row, "
            "compare archive name, resolved name, and structure. Choose Confirm OK if you accept "
            "the SMILES, Override if you have a correction, Mark PARTIAL_MATCH if close but not "
            "exact, or Reject to clear the structure."
        ),
    ),
    "partial_match": GlossaryEntry(
        key="partial_match",
        title="PARTIAL_MATCH",
        short=(
            "Name matched a related but not exact structure (e.g. wrong salt form or isomer). "
            "Exclude from final modeling unless fixed."
        ),
        long=(
            "PARTIAL_MATCH rows (~526) are known ambiguous or high-risk matches from Pass 2 "
            "corrections. They are kept for transparency but should not be used as confident "
            "structures in models unless manually corrected."
        ),
    ),
    "failed": GlossaryEntry(
        key="failed",
        title="FAILED_BOTH_PASSES",
        short="No structure found in Pass 1 or Pass 2. Usually no SMILES to review.",
        long=(
            "About 1,596 names could not be resolved automatically. Some received a Pass 3 rescue "
            "structure (RESOLVED_PASS3). Rows with no SMILES have nothing to draw — browse only."
        ),
    ),
    "status_resolved_pass1": GlossaryEntry(
        key="status_resolved_pass1",
        title="Status: RESOLVED_PASS1",
        short="Structure found on the first (direct) lookup pass.",
        long="See Pass 1.",
    ),
    "status_resolved_pass2": GlossaryEntry(
        key="status_resolved_pass2",
        title="Status: RESOLVED_PASS2",
        short="Structure found only after Pass 2 variant / retry logic.",
        long="See Pass 2.",
    ),
    "curation_reviewed": GlossaryEntry(
        key="curation_reviewed",
        title="Reviewed / Not reviewed",
        short=(
            "After you apply an action, the row is marked Reviewed and locked so others "
            "do not repeat your work."
        ),
        long=(
            "Each reviewed row records who reviewed it, when, and what action they chose. "
            "Reviewed rows cannot be changed by other reviewers. Enter your name in the sidebar "
            "before reviewing. Progress is saved to the project repository after each review."
        ),
    ),
    "actions_confirm": GlossaryEntry(
        key="actions_confirm",
        title="Action: Confirm OK",
        short="You agree the current SMILES correctly represents the archive name.",
        long=(
            "Use Confirm OK when the structure picture matches the 1947 name and you see no "
            "obvious error. This marks the row as curated and ready for modeling tiers."
        ),
    ),
    "actions_partial": GlossaryEntry(
        key="actions_partial",
        title="Action: Mark PARTIAL_MATCH",
        short="Close related structure but not an exact match for the archive name.",
        long=(
            "Use when the structure is in the right chemical family but wrong form, salt, "
            "stereochemistry, or isomer. Downgrades confidence for modeling."
        ),
    ),
    "actions_reject": GlossaryEntry(
        key="actions_reject",
        title="Action: Reject",
        short="Clear the SMILES — structure should not be used.",
        long=(
            "Reject when the structure is clearly wrong and you cannot supply a better SMILES. "
            "The row is excluded from the curated modeling set."
        ),
    ),
    "actions_override": GlossaryEntry(
        key="actions_override",
        title="Action: Override SMILES",
        short="Replace the SMILES with a corrected structure you provide.",
        long=(
            "Use only when you are confident in the correction (e.g. from a trusted database "
            "or expert knowledge). Paste the new SMILES in the override box, then apply."
        ),
    ),
}


# Ordered sections for the PDF table of contents
PDF_SECTION_ORDER: list[str] = [
    "purpose",
    "archive_name",
    "resolved_name",
    "smiles",
    "pass1",
    "pass2",
    "pass3",
    "smarts",
    "iupac",
    "similarity",
    "ccast_ok",
    "ccast_suspicious",
    "ccast_convert_failed",
    "ccast_low_similarity",
    "ccast_approved",
    "validated_ok",
    "needs_review",
    "partial_match",
    "failed",
    "curation_reviewed",
    "actions_confirm",
    "actions_partial",
    "actions_reject",
    "actions_override",
]


# Queue definitions for the app (Phase B+)
REVIEW_QUEUES: list[dict] = [
    {
        "id": "needs_review",
        "label": "1. NEEDS_REVIEW (SMARTS fail)",
        "description": GLOSSARY["needs_review"].short,
        "required": True,
    },
    {
        "id": "ccast_convert_failed",
        "label": "2. CCAST CONVERT_FAILED",
        "description": GLOSSARY["ccast_convert_failed"].short,
        "required": True,
    },
    {
        "id": "ccast_suspicious",
        "label": "3. CCAST SUSPICIOUS",
        "description": GLOSSARY["ccast_suspicious"].short,
        "required": False,
    },
    {
        "id": "ccast_approved",
        "label": "4. CCAST APPROVED (reference)",
        "description": GLOSSARY["ccast_approved"].short,
        "required": False,
        "readonly": True,
    },
    {
        "id": "partial_match",
        "label": "5. PARTIAL_MATCH",
        "description": GLOSSARY["partial_match"].short,
        "required": False,
    },
    {
        "id": "still_failed",
        "label": "6. Still failed (no structure)",
        "description": GLOSSARY["failed"].short,
        "required": False,
    },
    {
        "id": "all",
        "label": "All rows",
        "description": "Browse the full dataset.",
        "required": False,
    },
]


def get_short(key: str) -> str:
    return GLOSSARY[key].short


def get_title(key: str) -> str:
    return GLOSSARY[key].title
