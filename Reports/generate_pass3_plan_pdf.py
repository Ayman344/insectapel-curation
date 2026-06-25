"""Generate PDF: Pass 3 Pipeline Plan for Approval."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).parent / "PASS3_Pipeline_Plan.pdf"


def sanitize(text: str) -> str:
    replacements = {
        "\u2014": "-", "\u2013": "-",
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2192": "->", "\u2190": "<-",
        "\u2026": "...", "\u2264": "<=",
        "\u2265": ">=", "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class PlanPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, "Pass 3 Pipeline Plan - 1947 King USDA Dataset", align="R")
            self.ln(4)
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def title_page(self):
        self.add_page()
        self.ln(35)
        self.set_font("Helvetica", "B", 22)
        self.multi_cell(0, 12, "Pass 3 Pipeline Plan", align="C")
        self.ln(6)
        self.set_font("Helvetica", "", 14)
        self.multi_cell(0, 8, "Validation and Advanced Resolution", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 7, "For Approval Before Implementation", align="C")
        self.ln(18)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 8, f"Date: {date.today().strftime('%B %d, %Y')}", align="C")
        self.ln(6)
        self.cell(0, 8, "North Dakota State University / Insectapel Project", align="C")
        self.ln(10)
        self.set_font("Helvetica", "I", 10)
        self.multi_cell(
            0, 5.5,
            sanitize(
                "Status: PLAN ONLY - no Pass 3 scripts have been implemented yet. "
                "Implementation begins after explicit approval."
            ),
            align="C",
        )

    def section(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(230, 240, 250)
        self.cell(0, 9, sanitize(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def subsection(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, sanitize(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

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
            self.set_fill_color(220, 230, 240)
            for i, h in enumerate(headers):
                self.cell(col_widths[i], 7, sanitize(h), border=1, fill=True)
            self.ln()

        draw_header()
        self.set_font("Helvetica", "", 9)
        fill = False
        for row in rows:
            if self.get_y() > 262:
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
    pdf = PlanPDF()
    pdf.title_page()
    pdf.add_page()

    pdf.section("1. Context")
    pdf.body(
        "Pass 1 and Pass 2 of the chemical name resolver are complete. The combined output "
        "file resolved_chemicals_final.xlsx contains approximately 4,651 fully resolved names, "
        "526 PARTIAL_MATCH rows, 1,626 failures, and 286 irregular skipped entries. Only a "
        "subset of Pass 2 has been validated. Pass 3 will provide unified, multi-layered "
        "validation and advanced rescue for both Pass 1 and Pass 2 results, plus remaining failures."
    )

    pdf.section("2. Hardware Constraints")
    pdf.table(
        ["Environment", "Specs", "Pass 3 role"],
        [
            ["Local PC", "40 GB RAM, i7, integrated graphics", "SMARTS validation, OPSIN, ChemSpider, Streamlit"],
            ["CCAST cluster", "GPU nodes via SLURM", "STOUT reverse validation (SMILES to IUPAC)"],
        ],
        col_widths=[35, 65, 80],
    )

    pdf.section("3. CCAST: Agent vs User Responsibilities")
    pdf.table(
        ["Task", "Agent can do?", "Who does it"],
        [
            ["Write pass3 scripts, SLURM, Streamlit, README", "Yes", "Agent"],
            ["Run local validation on PC", "Yes (after approval)", "Agent"],
            ["Open CCAST tab / log into cluster", "No", "User"],
            ["Submit SLURM jobs on CCAST", "No", "User"],
            ["Upload/download files to CCAST", "No directly", "User (scp/OnDemand)"],
            ["Run code in CCAST Jupyter notebook", "Partially", "User runs provided cells/script"],
        ],
        col_widths=[70, 35, 75],
    )
    pdf.body(
        "Practical summary: local work can be largely automated by the agent after approval. "
        "CCAST requires the user to transfer files and launch jobs (typically 5-10 minutes per run). "
        "The agent will provide SLURM scripts and/or a CCAST notebook equivalent."
    )

    pdf.section("4. End-to-End Architecture")
    pdf.body(
        "resolved_chemicals_final.xlsx -> pass3_local_validation.py (Local PC) -> "
        "dataset_ready_for_ccast.xlsx -> pass3_ccast_validation.py (CCAST GPU via SLURM) -> "
        "dataset_from_ccast.xlsx -> pass3_curation_app.py (Streamlit on PC) -> Final curated export"
    )

    pdf.section("5. Current Data Baseline")
    pdf.table(
        ["Status", "Approx. count", "Pass 3 treatment"],
        [
            ["RESOLVED_PASS1", "4,014", "SMARTS validate all"],
            ["RESOLVED_PASS2", "637", "SMARTS validate all"],
            ["PARTIAL_MATCH", "526", "Optional review; not fully resolved"],
            ["FAILED_BOTH_PASSES", "1,626", "OPSIN + ChemSpider rescue"],
            ["IRREGULAR_SKIPPED", "286", "Skip or manual queue"],
        ],
        col_widths=[55, 35, 90],
    )
    pdf.body("Fully resolved to validate: ~4,651 rows. Rescue candidates: ~1,626 rows.")

    pdf.section("6. Deliverable 1: pass3_local_validation.py (Local PC)")
    pdf.subsection("Purpose")
    pdf.body(
        "Validate ALL resolved rows (Pass 1 and Pass 2) using RDKit SMARTS heuristics. "
        "Flag mismatches for manual review. Attempt OPSIN and ChemSpider rescue on unresolved rows."
    )
    pdf.subsection("Inputs and outputs")
    pdf.bullet("Input: resolved_chemicals_final.xlsx (sheet All_Data)")
    pdf.bullet("Output: dataset_ready_for_ccast.xlsx")
    pdf.body("Output sheets: All_Data, Resolved_Validated, Needs_Review, Pass3_Rescued, Still_Failed, Rescue_Log")

    pdf.subsection("Layer A - RDKit SMARTS validation")
    pdf.table(
        ["Name signal", "SMARTS check (conceptual)"],
        [
            ["ester, acetate, -ate (careful)", "Ester linkage [#6][#8][#6]"],
            ["acid (not acid salt)", "Carboxylic [CX3](=O)[OX2H1] or variant"],
            ["salt, sodium, potassium", "Ionic / metal (heuristic)"],
            ["amine, ammonium", "Basic nitrogen patterns"],
            ["alcohol, -ol suffix", "[OX2H]"],
            ["ketone", "Carbonyl between carbons"],
            ["ether", "Ether oxygen linkage"],
        ],
        col_widths=[55, 125],
    )
    pdf.body(
        "On FAIL: set Pass3_Status = NEEDS_REVIEW. SMARTS complements but does not replace "
        "STOUT/CCAST reverse validation. Many wrong-ester cases will still pass class-level checks."
    )

    pdf.subsection("Layer B - OPSIN rescue")
    pdf.bullet("Library: pyopsin")
    pdf.bullet("Target: FAILED_BOTH_PASSES rows")
    pdf.bullet("Disk cache: pass3_opsin_cache.json with rate limiting and resume")

    pdf.subsection("Layer C - ChemSpider rescue")
    pdf.bullet("Requires CHEMSPIDER_API_KEY environment variable (never committed to git)")
    pdf.bullet("Runs after OPSIN failures; cache: pass3_chemspider_cache.json")

    pdf.subsection("Proposed new columns")
    pdf.body(
        "Pass3_Status, Pass3_SMARTS_Result, Pass3_SMARTS_Reason, Pass3_Review_Tier, "
        "Pass3_Rescue_Source, Pass3_Rescue_SMILES, Pass3_Notes"
    )

    pdf.section("7. Deliverable 2: pass3_ccast_validation.py + ccast_pass3.slurm")
    pdf.subsection("Purpose")
    pdf.body(
        "Reverse validation on CCAST GPU: translate resolved SMILES to systematic IUPAC names "
        "using STOUT (STOUT-pypi), then compute Jaro-Winkler similarity vs original 1947 name."
    )
    pdf.subsection("Inputs and outputs")
    pdf.bullet("Input: dataset_ready_for_ccast.xlsx")
    pdf.bullet("Output: dataset_from_ccast.xlsx")
    pdf.bullet("New columns: STOUT_IUPAC, JaroWinkler_Score, Pass3_CCAST_Flag (OK / SUSPICIOUS / LOW_SIMILARITY)")

    pdf.subsection("SLURM script (ccast_pass3.slurm)")
    pdf.bullet("Request 1 GPU, 16-32 GB RAM, 2-4 hour walltime")
    pdf.bullet("Install: STOUT-pypi, pandas, openpyxl, jellyfish, rdkit-pypi")
    pdf.bullet("Default flag threshold: Jaro-Winkler < 0.45 -> suspicious (tunable)")

    pdf.body(
        "STOUT caveat: generated IUPAC names may not match 1947 vernacular. Use flags for "
        "review priority, not automatic rejection."
    )

    pdf.section("8. Deliverable 3: pass3_curation_app.py (Streamlit, Local)")
    pdf.subsection("Purpose")
    pdf.body("Human-in-the-loop UI for flagged rows after CCAST validation.")
    pdf.bullet("Load dataset_from_ccast.xlsx")
    pdf.bullet("Filter: NEEDS_REVIEW, SUSPICIOUS, LOW_SIMILARITY, PARTIAL_MATCH, Still_Failed")
    pdf.bullet("Display: original name, resolved name, STOUT IUPAC, RDKit structure image")
    pdf.bullet("Actions: Confirm (CURATED_OK), Partial match, Reject, Override SMILES")
    pdf.bullet("Export: dataset_curated_final.xlsx")

    pdf.section("9. Deliverable 4: README_PASS3.md")
    pdf.bullet("Prerequisites and pip install lists (local vs CCAST)")
    pdf.bullet("ChemSpider API key setup")
    pdf.bullet("Local run instructions")
    pdf.bullet("File transfer to CCAST (scp, OnDemand, notebook upload)")
    pdf.bullet("sbatch ccast_pass3.slurm and monitoring (squeue, logs)")
    pdf.bullet("Download results and run Streamlit curation app")
    pdf.bullet("Expected runtimes, caching, troubleshooting")

    pdf.section("10. Proposed Implementation Order (After Approval)")
    pdf.table(
        ["Phase", "Deliverable", "Where", "User involvement"],
        [
            ["1", "pass3_smarts_rules.py + local SMARTS validation", "Local", "Minimal"],
            ["2", "Add OPSIN rescue + cache", "Local", "Minimal"],
            ["3", "Add ChemSpider rescue", "Local", "API key required"],
            ["4", "pass3_ccast_validation.py + ccast_pass3.slurm", "CCAST", "Upload + sbatch"],
            ["5", "pass3_curation_app.py", "Local", "Open Streamlit in browser"],
            ["6", "README_PASS3.md + PDF report update", "Docs", "None"],
        ],
        col_widths=[18, 75, 28, 59],
    )
    pdf.body("Stop and review after each phase before proceeding.")

    pdf.section("11. Dependencies (Preview)")
    pdf.subsection("Local")
    pdf.body("pandas, openpyxl, rdkit-pypi, pyopsin, requests, python-dotenv, jellyfish, streamlit")
    pdf.subsection("CCAST")
    pdf.body("pandas, openpyxl, STOUT-pypi, rdkit-pypi, jellyfish, torch (GPU via SLURM)")
    pdf.subsection("Secrets")
    pdf.body("CHEMSPIDER_API_KEY - register at chemspider.com")

    pdf.section("12. Risks and Mitigations")
    pdf.table(
        ["Risk", "Mitigation"],
        [
            ["ChemSpider rate limits", "Cache + resume; optional --skip-chemspider flag"],
            ["OPSIN fails on archaic names", "Log failures; do not block pipeline"],
            ["STOUT low scores on old names", "Flag only; do not auto-demote"],
            ["SMARTS false positives", "Tiered rules + SKIP when ambiguous"],
            ["Long local API run", "Checkpoint every N rows; safe to interrupt"],
        ],
        col_widths=[55, 125],
    )

    pdf.section("13. Approval Checklist")
    pdf.body("Please confirm the following before implementation begins:")
    pdf.bullet("Approve this plan (or specify changes)")
    pdf.bullet("ChemSpider: do you have an API key, or defer Phase 3?")
    pdf.bullet("CCAST: GPU partition name and module load commands (if known)")
    pdf.bullet("Jaro-Winkler threshold: default < 0.45 for suspicious?")
    pdf.bullet("Include MEDIUM-risk Pass 2 rows in SMARTS validation? (Recommended: yes)")

    pdf.section("14. Bottom Line")
    pdf.body(
        "This document is a plan for approval only. No Pass 3 code exists yet. After you "
        "approve this PDF/plan, implementation will proceed phase by phase starting with "
        "SMARTS validation on the local PC. CCAST steps require brief user action for file "
        "transfer and job submission; all scripts and notebooks will be provided."
    )

    pdf.output(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"PDF written to: {path}")
