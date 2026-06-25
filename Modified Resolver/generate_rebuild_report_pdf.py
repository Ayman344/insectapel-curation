"""
Generate a journal-style progress report for the Chemical Name Resolution REBUILD.

This is written for a teammate or supervisor who was NOT in the room. It tells the
story from the reader's point of view: what problem we found, why we rebuilt the
pipeline, how the validator-gated resolver works, and what the CCAST smoke tests
proved. It deliberately explains the reasoning step by step.

Run:  python generate_rebuild_report_pdf.py
Output: Chemical_Resolution_Rebuild_Report.pdf
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).parent
OUT = ROOT / "Chemical_Resolution_Rebuild_Report.pdf"


def sanitize(text: str) -> str:
    replacements = {
        "\u2014": "-", "\u2013": "-",
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2192": "->", "\u2190": "<-",
        "\u2026": "...", "\u2264": "<=", "\u2265": ">=",
        "\u00a0": " ", "\u00d7": "x", "\u2248": "~",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(110, 110, 110)
            self.cell(0, 8, "Chemical Name Resolution - Rebuild Progress Report", align="R")
            self.ln(4)
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def title_page(self):
        self.add_page()
        self.ln(26)
        self.set_font("Helvetica", "B", 22)
        self.multi_cell(0, 12, "Chemical Name Resolution", align="C",
                        new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 18)
        self.multi_cell(0, 10, "A Validator-Gated Rebuild", align="C",
                        new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 13)
        self.set_text_color(80, 80, 80)
        self.multi_cell(
            0, 7,
            sanitize("Turning historical USDA insect-repellent chemical names "
                     "(1947, 1954, 1967) into trustworthy molecular structures"),
            align="C", new_x="LMARGIN", new_y="NEXT",
        )
        self.ln(16)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 8, f"Report date: {date.today().strftime('%B %d, %Y')}", align="C")
        self.ln(6)
        self.cell(0, 8, "North Dakota State University / Insectapel Project", align="C")
        self.ln(14)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(90, 90, 90)
        self.multi_cell(
            0, 5.5,
            sanitize(
                "Audience note: this report is written for readers who are not "
                "cheminformatics specialists. Each section first says WHAT we did, "
                "then WHY we did it. Technical terms are defined the first time they "
                "appear."
            ),
            align="C",
        )
        self.set_text_color(0, 0, 0)

    def section(self, title: str):
        if self.get_y() > 245:
            self.add_page()
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(228, 238, 250)
        self.cell(0, 9, sanitize(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def subsection(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, sanitize(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.6, sanitize(text))
        self.ln(1.5)

    def bullet(self, text: str, label: str = "-"):
        self.set_font("Helvetica", "", 10)
        x = self.get_x()
        self.cell(7, 5.6, label)
        self.multi_cell(0, 5.6, sanitize(text))
        self.set_x(x)

    def step(self, n: int, text: str):
        self.set_font("Helvetica", "B", 10)
        x = self.get_x()
        self.cell(9, 5.6, f"{n}.")
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.6, sanitize(text))
        self.set_x(x)
        self.ln(0.5)

    def note_box(self, text: str, color=(255, 248, 220)):
        self.set_fill_color(*color)
        self.set_font("Helvetica", "I", 9.5)
        self.multi_cell(0, 5.5, sanitize(text), fill=True, border=0)
        self.ln(2)
        self.set_fill_color(255, 255, 255)

    def _row_height(self, col_widths, row, line_h=5, pad=2):
        max_lines = 1
        for i, cell in enumerate(row):
            lines = self.multi_cell(
                col_widths[i] - 2, line_h, sanitize(str(cell)),
                dry_run=True, output="LINES",
            )
            max_lines = max(max_lines, len(lines))
        return max(max_lines * line_h + pad, 7)

    def table(self, headers, rows, col_widths=None):
        if col_widths is None:
            w = (self.w - self.l_margin - self.r_margin) / len(headers)
            col_widths = [w] * len(headers)
        line_h = 5

        def draw_header():
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(218, 228, 240)
            for i, h in enumerate(headers):
                self.cell(col_widths[i], 7, sanitize(h), border=1, fill=True)
            self.ln()

        draw_header()
        self.set_font("Helvetica", "", 9)
        fill = False
        for row in rows:
            if self.get_y() > 260:
                self.add_page()
                draw_header()
                self.set_font("Helvetica", "", 9)
            row_h = self._row_height(col_widths, row, line_h)
            y0, x0 = self.get_y(), self.l_margin
            self.set_fill_color(245, 248, 252) if fill else self.set_fill_color(255, 255, 255)
            for i in range(len(row)):
                self.set_xy(x0 + sum(col_widths[:i]), y0)
                self.cell(col_widths[i], row_h, "", border=1, fill=fill)
            for i, cell in enumerate(row):
                self.set_xy(x0 + sum(col_widths[:i]) + 1, y0 + 1)
                self.multi_cell(col_widths[i] - 2, line_h, sanitize(str(cell)))
            self.set_xy(x0, y0 + row_h)
            fill = not fill
        self.ln(3)


def build():
    pdf = ReportPDF()
    pdf.title_page()
    pdf.add_page()

    # ---------------------------------------------------------------- 1
    pdf.section("1. Executive Summary")
    pdf.body(
        "This project converts roughly 23,900 historical chemical names - drawn from three "
        "USDA insect-repellent studies (1947, 1954, and 1967) - into modern, computer-readable "
        "molecular structures. A structure is written as a SMILES string: a compact line of text "
        "that a computer can read as a molecule. The long-term goal is to feed these structures "
        "into machine-learning models that predict whether a compound is a good insect repellent."
    )
    pdf.body(
        "An earlier version of this pipeline appeared successful but was quietly producing wrong "
        "answers. We diagnosed the cause, then rebuilt the core of the pipeline around a single new "
        "idea: never trust a structure unless it actually matches the chemistry the name describes. "
        "We call this a 'validator-gated' resolver. We then tested it on the CCAST high-performance "
        "computing cluster and confirmed it behaves exactly as designed."
    )
    pdf.subsection("What this document covers")
    pdf.bullet("The problem we discovered in the old pipeline, with concrete examples.")
    pdf.bullet("The reasoning behind each design decision in the rebuild.")
    pdf.bullet("How the new resolver works, step by step.")
    pdf.bullet("The results of our CCAST smoke tests (5 names, then 20 names).")
    pdf.bullet("What comes next: the first full dataset run (1947).")

    # ---------------------------------------------------------------- 2
    pdf.section("2. Background: The Data and the Goal")
    pdf.body(
        "We have three spreadsheets of chemicals that were physically tested as insect repellents "
        "decades ago. Each lists a chemical by name, along with how well it repelled insects on "
        "skin or cloth. The names were written by hand or typed long ago, so they use old-fashioned "
        "(archaic) chemistry vocabulary and contain typing/scanning errors."
    )
    pdf.table(
        ["Year", "File", "Name column", "Rows"],
        [
            ["1947", "1947-King-USDA_Dataset.csv", "Chemical", "7,089"],
            ["1954", "1954-King_dataset.csv", "Chemical", "8,201"],
            ["1967", "1967_USDA_datasetcsv.csv", "MATERIAL", "8,591"],
            ["Total", "(three files)", "-", "23,881"],
        ],
        col_widths=[18, 86, 38, 30],
    )
    pdf.body(
        "After combining the files into one tidy table and removing duplicate spellings of the "
        "same name, we have about 23,270 unique names to look up. The challenge is that a name like "
        "'Acetic acid, o-allyl-p-cresol ester' must be turned into the correct molecule - and only "
        "the correct molecule."
    )
    pdf.note_box(
        "Why correctness matters more than coverage: this data eventually trains a predictive "
        "model. One silently-wrong structure does not just lose one row - it teaches the model a "
        "false fact. A missing answer is honest; a wrong answer is poison. Every decision in this "
        "rebuild follows from that principle."
    )

    # ---------------------------------------------------------------- 3
    pdf.section("3. The Problem We Found in the Old Pipeline")
    pdf.body(
        "The old pipeline looked up each name in chemical databases and accepted the first answer "
        "that came back. It reported a high success rate. But when we inspected the actual "
        "structures, many were wrong in ways that are easy to miss. The single root cause: the old "
        "code only checked that 'some text came back', never that 'the structure the database "
        "returned actually matches the name'."
    )
    pdf.subsection("Two representative error families")
    pdf.body("Error A - Analogue / look-alike substitution.")
    pdf.bullet(
        "Name: 'Acetaldehyde dioctyl mercaptal'. This is a dithioacetal - one carbon bonded to "
        "two sulfur atoms (C-S and C-S). The correct structure is CCCCCCCCSC(C)SCCCCCCCC."
    )
    pdf.bullet(
        "The old pipeline returned an oxygen/sulfur look-alike instead. Same general shape, wrong "
        "chemistry. Nobody checked the sulfur count, so it passed."
    )
    pdf.ln(1)
    pdf.body("Error B - Disconnected mixtures.")
    pdf.bullet(
        "Name: 'Acetic acid, o-allyl-p-cresol ester'. An ester chemically bonds the acid and the "
        "alcohol into one molecule."
    )
    pdf.bullet(
        "The database returned two separate, unbonded fragments (the acid plus the phenol) - "
        "written with a '.' between them. That is a mixture of two chemicals, not the single bonded "
        "ester the name describes. The old code accepted it anyway."
    )
    pdf.subsection("Contributing bugs (the reasoning trail)")
    pdf.bullet(
        "A catch-all error handler silently swallowed every PubChem error, so all hits actually "
        "came from a fuzzy fallback resolver that happily returns near-matches.",
    )
    pdf.bullet(
        "Fallback 'retry' strategies truncated derivative names down to their parent (for example "
        "'Acetic acid, bornyl ester' became just 'Acetic acid') - changing the molecule entirely.",
    )
    pdf.bullet(
        "An old structural check used the wrong rule for mercaptals, so it failed correct "
        "structures and could not catch the wrong ones.",
    )

    # ---------------------------------------------------------------- 4
    pdf.section("4. The Core Idea of the Rebuild")
    pdf.body(
        "We added a step that the old pipeline never had: after a database returns a structure, we "
        "independently check it against the name before accepting it. We call this gating: a hit "
        "must pass the gate (the validator) or it is rejected. This is the single most important "
        "change."
    )
    pdf.subsection("Two cooperating components")
    pdf.bullet(
        "The Claim Parser (claims.py): reads a name and lists what chemistry the name PROMISES. "
        "For 'sodium benzoate' it notes a salt and a carboxylate; for a 'mercaptal' it notes a "
        "dithioacetal and the presence of sulfur. It is deliberately cautious - if a name is "
        "ambiguous, it stays silent rather than guess.",
    )
    pdf.bullet(
        "The Validator (validate.py): compares those promises against the structure the database "
        "returned. If the name promises sulfur but the structure has none, that is a hard mismatch "
        "and we reject it. If the name describes a single molecule but the structure is two "
        "disconnected fragments, we reject it.",
    )
    pdf.subsection("Three possible verdicts")
    pdf.table(
        ["Verdict", "Plain meaning", "What we do"],
        [
            ["VERIFIED", "The structure clearly matches a chemical feature the name promised.",
             "Accept with confidence."],
            ["UNVERIFIED", "Nothing contradicts the name, but there was no strong feature to confirm "
             "(e.g. 'Camphor' names no functional group).",
             "Keep, but flag for corroboration or human review."],
            ["REJECT", "A hard contradiction (missing element, wrong group, disconnected mixture).",
             "Do not accept this structure; try another."],
        ],
        col_widths=[26, 88, 58],
    )
    pdf.note_box(
        "Key reasoning: a REJECT is not data loss. It only means 'do not accept THIS structure'. "
        "The resolver keeps trying other spellings and other databases. Only if everything is "
        "rejected do we set the name aside (quarantine) for a human to look at - with the rejected "
        "candidates and the reasons attached, so the reviewer has a head start."
    )

    # ---------------------------------------------------------------- 5
    pdf.section("5. How the Resolver Works, Step by Step")
    pdf.body(
        "For each unique chemical name, the resolver runs the following loop. The design goal is "
        "to try many reasonable ways of reading the name, but to accept only structures that pass "
        "the validator gate."
    )
    pdf.step(1, "Generate sensible variants of the name. Historical names have archaic words, "
                "scanning typos (the letter 'l' read as the digit '1'), comma quirks, and "
                "'acid ... ester' phrasings. We rewrite these in safe, meaning-preserving ways. "
                "Crucially, we DROPPED the old variants that truncated names, because those changed "
                "the molecule.")
    pdf.step(2, "For each variant, ask three independent resolvers in turn: PubChem (the public NIH "
                "database), OPSIN (a name-to-structure parser that follows IUPAC naming rules), and "
                "CIRpy (a chemical identifier resolver). Each is queried independently.")
    pdf.step(3, "Whatever structure a resolver returns is immediately sent through the validator "
                "gate (Section 4). If the verdict is REJECT, we log the reason and move on to the "
                "next resolver or variant. We never accept on the basis of 'some text came back'.")
    pdf.step(4, "The first VERIFIED or UNVERIFIED structure wins. We record the structure, its "
                "InChIKey (a standard fingerprint used later to merge identical molecules across "
                "the three years), which resolver and variant succeeded, and the full reject log.")
    pdf.step(5, "If every variant and every resolver is rejected, the name is QUARANTINED for human "
                "review (we kept rejected candidates and reasons). If nothing came back at all, it "
                "is marked FAILED.")
    pdf.step(6, "Every lookup is cached to disk. Re-running the job never repeats a network call it "
                "has already made, which makes the big run resumable and fast on a second pass.")

    # ---------------------------------------------------------------- 6
    pdf.section("6. Running on CCAST (High-Performance Computing)")
    pdf.body(
        "CCAST is NDSU's shared supercomputing cluster. Instead of running the long job on a "
        "laptop, we package the code and submit it as a batch job that runs unattended on a compute "
        "node. We confirmed three things on CCAST before any real run:"
    )
    pdf.bullet("Python and the required libraries (RDKit, pandas, CIRpy, py2opsin) install cleanly "
               "in the user's account.")
    pdf.bullet("Java is available, which OPSIN needs - so all three resolvers are usable on CCAST.")
    pdf.bullet("The compute nodes have outbound internet, so PubChem and CIRpy lookups work during "
               "the job. This means the whole pipeline can run as one unattended batch job.")
    pdf.note_box(
        "We deliberately use the CCAST 'scratch' space for these runs. Scratch is fast but is NOT "
        "backed up, and idle files are deleted after 60 days. Our rule: the master copy lives on "
        "the personal PC; results are downloaded off scratch after each run.",
        color=(255, 238, 238),
    )

    # ---------------------------------------------------------------- 7
    pdf.section("7. Smoke Test Results on CCAST")
    pdf.body(
        "A 'smoke test' is a small run whose only purpose is to confirm nothing is on fire before "
        "committing to the large job. We ran two: 5 names, then 20 names. All three resolvers "
        "reported available (PubChem, OPSIN, CIRpy)."
    )
    pdf.subsection("20-name run summary (about 45 seconds)")
    pdf.table(
        ["Outcome", "Count", "Share", "Meaning"],
        [
            ["resolved", "15", "75%", "A structure was found AND passed the validator gate."],
            ["quarantine", "1", "5%", "Candidates were found but the validator rejected them all (correct behavior)."],
            ["failed", "4", "20%", "No resolver returned anything usable."],
        ],
        col_widths=[26, 18, 18, 110],
    )
    pdf.subsection("Why these results are encouraging (the reasoning)")
    pdf.bullet(
        "The hard 'mercaptal' name - the original Error A - resolved correctly to the dithioacetal "
        "(via CIRpy) and passed the validator. The exact bug that motivated the rebuild is fixed.",
    )
    pdf.bullet(
        "The 'o-allyl-p-cresol ester' name - the original Error B - was QUARANTINED, because the "
        "only candidates were disconnected mixtures and the validator correctly rejected them. The "
        "gate is doing its job rather than accepting a wrong answer.",
    )
    pdf.bullet(
        "The 4 failures were genuinely hard: a trade name in quotes ('Octab'), a badly "
        "scan-corrupted name, and a very complex ester. Failing honestly on these is the desired "
        "behavior - far better than inventing a plausible-but-wrong structure.",
    )
    pdf.bullet(
        "Simple, well-formed names (sodium benzoate, ethyl ester of abietic acid, benzaldehyde "
        "diethyl acetal) resolved via PubChem and verified cleanly.",
    )
    pdf.note_box(
        "Interpretation: a 75% validated-resolution rate on a deliberately hard, mixed sample - "
        "with zero silent false positives observed - is exactly the trade-off we wanted. The old "
        "pipeline's higher headline rate included wrong answers we could not see."
    )

    # ---------------------------------------------------------------- 8
    pdf.section("8. What Comes Next")
    pdf.body(
        "Having proven the machinery on small samples, the plan is to scale up carefully rather "
        "than all at once. The reasoning: run one full dataset first, inspect the outputs by hand, "
        "and only then process all three years. This catches any dataset-specific surprise before "
        "we spend many hours of compute."
    )
    pdf.step(1, "Run the full 1947 dataset (about 7,000 names) as a CCAST batch job. This is the "
                "immediate next step.")
    pdf.step(2, "Manually review a sample of the 1947 results - confirm VERIFIED structures look "
                "right and quarantined names are genuinely hard.")
    pdf.step(3, "Once 1947 looks good, run 1954 and 1967 the same way.")
    pdf.step(4, "Merge identical molecules across years using the InChIKey fingerprint, keeping each "
                "year's repellency measurements side by side.")
    pdf.step(5, "Assign confidence tiers and load everything into the existing curation app for "
                "expert human review.")

    pdf.subsection("Status at the time of this report")
    pdf.table(
        ["Stage", "Status"],
        [
            ["Diagnose old pipeline's false positives", "Done"],
            ["Build claim parser + validator", "Done"],
            ["Build validator-gated resolver (3 databases)", "Done"],
            ["CCAST environment + smoke tests (5 and 20 names)", "Done"],
            ["Full 1947 dataset run on CCAST", "Next"],
            ["1954 + 1967 runs", "Planned"],
            ["Cross-year merge, tiers, curation", "Planned"],
        ],
        col_widths=[120, 50],
    )

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(
        0, 5,
        sanitize(
            "Prepared for internal review (teammates and supervisor). Questions about any "
            "section are welcome - the design choices are intentionally conservative, favoring "
            "trustworthy data over a higher but unreliable success rate."
        ),
    )
    pdf.set_text_color(0, 0, 0)

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
