"""
Generate Curation Reviewer Guide PDF for non-technical reviewers.

Run:  python generate_curation_guide_pdf.py
Output: Curation_Reviewer_Guide.pdf
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from curation_glossary import GLOSSARY, PDF_SECTION_ORDER

ROOT = Path(__file__).parent
OUT = ROOT / "Curation_Reviewer_Guide.pdf"


def sanitize(text: str) -> str:
    replacements = {
        "\u2014": "-", "\u2013": "-",
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2192": "->", "\u2190": "<-",
        "\u2026": "...", "\u2264": "<=", "\u2265": ">=",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class GuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, "Curation Reviewer Guide - 1947 King USDA Dataset", align="R")
            self.ln(4)
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def section(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(230, 240, 250)
        self.cell(0, 9, sanitize(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, sanitize(text))
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        x = self.get_x()
        self.cell(6, 5.5, "-")
        self.multi_cell(0, 5.5, sanitize(text))
        self.set_x(x)


def build_pdf() -> Path:
    pdf = GuidePDF()

    # Title page
    pdf.add_page()
    pdf.ln(24)
    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(0, 12, "Curation Reviewer Guide", align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 14)
    pdf.multi_cell(0, 8, "1947 King USDA Repellent Dataset", align="C")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0, 6,
        sanitize(
            "Plain-language instructions for reviewing chemical names and structures. "
            "No programming or chemistry software experience required."
        ),
        align="C",
    )
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Guide date: {date.today().strftime('%B %d, %Y')}", align="C")
    pdf.ln(6)
    pdf.cell(0, 8, "North Dakota State University / Insectapel Project", align="C")

    # Quick start
    pdf.add_page()
    pdf.section("1. Quick start - what you do")
    pdf.body(
        "Open the curation web app (link from your team lead). Enter your name in the sidebar. "
        "Work through Queue 1 (NEEDS_REVIEW) first - these are the highest-priority rows. "
        "For each row you will see the 1947 archive name, other names, flags, and a structure picture."
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, sanitize("Step-by-step for each row:"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    for step in [
        "Read the archive name (1947 original) on the left.",
        "Look at the structure picture on the right.",
        "Ask: does this structure match what the archive name describes?",
        "If yes -> Confirm OK. If wrong and you know the fix -> Override SMILES. "
        "If related but not exact -> PARTIAL_MATCH. If clearly wrong -> Reject.",
        "Click Apply. The row is marked Reviewed and saved - do not review it again.",
        "Use Next unreviewed to move on.",
    ]:
        pdf.bullet(step)

    pdf.section("2. Review queues (priority order)")
    pdf.body("Your team lead may assign queues. Default priority:")
    for item in [
        ("Queue 1 - NEEDS_REVIEW (~537 rows)", "SMARTS failed. Main workload. Required."),
        ("Queue 2 - CCAST CONVERT_FAILED (~127)", "No IUPAC generated. Review structure anyway."),
        ("Queue 3 - CCAST SUSPICIOUS (~293)", "Low name similarity. Optional spot-check."),
        ("Queue 4 - CCAST APPROVED (~1,044)", "SMARTS PASS + CCAST OK + Pass 1 + similarity >= 0.55. Reference only."),
        ("Queue 5 - PARTIAL_MATCH / Failed", "Known incomplete. Usually no action needed."),
    ]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, sanitize(item[0]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5.5, sanitize(item[1]))
        pdf.ln(1)

    pdf.section("3. Rules for reviewers")
    for rule in [
        "Always enter your real name before reviewing.",
        "Do not change rows already marked Reviewed by someone else.",
        "When unsure, add a note and ask your team lead rather than guessing.",
        "Trust the structure picture and archive name more than automated flags.",
        "CCAST OK does not mean SMARTS FAIL rows are correct - still review them.",
        "Similarity scores are text comparisons only - not proof of structure correctness.",
    ]:
        pdf.bullet(rule)

    # Glossary sections
    pdf.add_page()
    pdf.section("4. Glossary - terms and flags")
    pdf.body(
        "The web app shows (i) icons next to fields with short explanations. "
        "This section has the full descriptions."
    )
    pdf.ln(2)

    for key in PDF_SECTION_ORDER:
        entry = GLOSSARY[key]
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, sanitize(entry.title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5.5, sanitize(entry.long))
        pdf.ln(2)

    # Reference table
    pdf.add_page()
    pdf.section("5. Reference - column names in the app")
    cols = [
        ("Chemical", "Archive name from 1947 dataset"),
        ("Resolved_Name", "Name returned by database lookup (Pass 1/2)"),
        ("SMILES", "Structure code; drives the picture"),
        ("Status", "Pass 1/2 outcome (RESOLVED_PASS1, PARTIAL_MATCH, etc.)"),
        ("Pass3_Status", "VALIDATED_OK, NEEDS_REVIEW, CURATED_OK after you review"),
        ("Pass3_SMARTS_Result", "PASS, FAIL, or SKIP"),
        ("Pass3_SMARTS_Reason", "Why SMARTS passed or failed"),
        ("STOUT_IUPAC", "IUPAC name generated from SMILES on CCAST"),
        ("JaroWinkler_Score", "Similarity 0-1 vs archive name"),
        ("Pass3_CCAST_Flag", "OK, SUSPICIOUS, CONVERT_FAILED, LOW_SIMILARITY"),
        ("Validation_Risk", "Pass 2 risk level (HIGH / MEDIUM / LOW)"),
    ]
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(55, 7, "Field", border=1)
    pdf.cell(0, 7, "Meaning", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for field, meaning in cols:
        pdf.cell(55, 6, sanitize(field), border=1)
        pdf.cell(0, 6, sanitize(meaning), border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.section("6. Questions?")
    pdf.body(
        "Contact your team lead (Insectapel / NDSU) if a name is ambiguous, "
        "the app will not save, or you think a reviewed row needs to be reopened."
    )

    pdf.output(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"Wrote {path}")
