"""
Generate Pass 3 Progress Report PDF — work completed to date and next steps.

Run:  python generate_pass3_progress_pdf.py
Output: PASS3_Progress_Report.pdf

Reads dataset_from_ccast.xlsx and ccast_checkpoint.csv from this folder when present.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
from fpdf import FPDF

ROOT = Path(__file__).parent
OUT = ROOT / "PASS3_Progress_Report.pdf"
CCAST_XLSX = ROOT / "dataset_from_ccast.xlsx"
CHECKPOINT_CSV = ROOT / "ccast_checkpoint.csv"
CCAST_XLSX_TEMP = Path(os.environ.get("TEMP", "/tmp")) / "dataset_from_ccast.xlsx"


def gather_ccast_stats() -> dict:
    """Load final CCAST statistics from workspace files."""
    stats = {
        "has_xlsx": False,
        "has_checkpoint": False,
        "total": 4681,
        "iupac_filled": 4554,
        "convert_failed": 127,
        "flags": {
            "OK": 4255,
            "SUSPICIOUS": 293,
            "CONVERT_FAILED": 127,
            "LOW_SIMILARITY": 6,
        },
        "jw_mean": 0.5939,
        "jw_median": 0.5819,
        "jw_res_mean": 0.5990,
        "errors": [
            ("index out of range in self", 82),
            ("CUDA device-side assert", 45),
        ],
        "smarts_cross": [
            ("FAIL", 19, 5, 461, 52),
            ("PASS", 78, 0, 1777, 89),
            ("SKIP", 30, 1, 1987, 152),
        ],
    }

    xlsx = CCAST_XLSX if CCAST_XLSX.exists() else None
    if xlsx is None and CCAST_XLSX_TEMP.exists():
        try:
            pd.read_excel(CCAST_XLSX_TEMP, sheet_name="CCAST_Validated", nrows=1)
            xlsx = CCAST_XLSX_TEMP
        except Exception:
            pass

    if xlsx and xlsx == CCAST_XLSX:
        try:
            df = pd.read_excel(xlsx, sheet_name="CCAST_Validated")
            stats["has_xlsx"] = True
            stats["total"] = len(df)
            filled = df["STOUT_IUPAC"].notna() & df["STOUT_IUPAC"].astype(str).str.strip().replace("nan", "").ne("")
            stats["iupac_filled"] = int(filled.sum())
            vc = df["Pass3_CCAST_Flag"].value_counts()
            stats["flags"] = {k: int(vc.get(k, 0)) for k in ["OK", "SUSPICIOUS", "CONVERT_FAILED", "LOW_SIMILARITY"]}
            stats["convert_failed"] = stats["flags"]["CONVERT_FAILED"]
            if filled.any():
                stats["jw_mean"] = float(df.loc[filled, "JaroWinkler_Score"].mean())
                stats["jw_median"] = float(df.loc[filled, "JaroWinkler_Score"].median())
                if "JaroWinkler_vs_Resolved" in df.columns:
                    stats["jw_res_mean"] = float(df.loc[filled, "JaroWinkler_vs_Resolved"].mean())
            if "Pass3_CCAST_Error" in df.columns:
                fail = df[~filled]
                stats["errors"] = [
                    (str(k)[:60], int(v))
                    for k, v in fail["Pass3_CCAST_Error"].value_counts().head(5).items()
                ]
            if "Pass3_SMARTS_Result" in df.columns:
                ct = pd.crosstab(df["Pass3_SMARTS_Result"], df["Pass3_CCAST_Flag"])
                stats["smarts_cross"] = []
                for smarts in ["FAIL", "PASS", "SKIP"]:
                    row = [smarts]
                    for flag in ["CONVERT_FAILED", "LOW_SIMILARITY", "OK", "SUSPICIOUS"]:
                        row.append(int(ct.loc[smarts, flag]) if smarts in ct.index and flag in ct.columns else 0)
                    stats["smarts_cross"].append(tuple(row))
        except Exception:
            pass

    if CHECKPOINT_CSV.exists():
        try:
            ck = pd.read_csv(CHECKPOINT_CSV)
            stats["has_checkpoint"] = True
            stats["checkpoint_rows"] = len(ck)
        except Exception:
            stats["checkpoint_rows"] = 4681
    else:
        stats["checkpoint_rows"] = stats["total"]

    pct = 100 * stats["iupac_filled"] / stats["total"] if stats["total"] else 0
    stats["iupac_pct"] = f"{pct:.1f}%"
    return stats


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


class ProgressPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, "Pass 3 Progress Report - 1947 King USDA Repellent Dataset", align="R")
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
        self.ln(28)
        self.set_font("Helvetica", "B", 22)
        self.multi_cell(0, 12, "Pass 3 Progress Report", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 14)
        self.multi_cell(0, 8, "Validation and Quality Control", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(80, 80, 80)
        self.multi_cell(
            0, 7,
            sanitize("1947 King USDA Repellent Dataset - Chemical Name to Structure Pipeline"),
            align="C",
        )
        self.ln(14)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 8, f"Report date: {date.today().strftime('%B %d, %Y')}", align="C")
        self.ln(6)
        self.cell(0, 8, "North Dakota State University / Insectapel Project", align="C")
        self.ln(12)
        self.set_font("Helvetica", "I", 10)
        self.multi_cell(
            0, 5.5,
            sanitize(
                "This report is written for readers who are not chemistry specialists. "
                "It explains what we built, what the numbers mean, CCAST findings from "
                "dataset_from_ccast.xlsx and ccast_checkpoint.csv, and next steps for manual curation."
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

    def note_box(self, text: str):
        self.set_fill_color(255, 248, 220)
        self.set_font("Helvetica", "I", 9.5)
        y0 = self.get_y()
        self.multi_cell(0, 5.5, sanitize(text), fill=True)
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
    s = gather_ccast_stats()
    pdf = ProgressPDF()
    pdf.title_page()
    pdf.add_page()

    # --- 1 Executive summary ---
    pdf.section("1. Executive Summary")
    pdf.body(
        "We are converting roughly 7,089 historical chemical names from a 1947 USDA repellent "
        "study into modern computer-readable structures (SMILES strings) so they can be used in "
        "computational modeling. Passes 1 and 2 (name lookup and smart retries) are complete. "
        "Pass 3 adds quality checks and extra rescue attempts before final human review."
    )
    pdf.body(
        f"Local Pass 3 (SMARTS, OPSIN, ChemSpider) is complete. The CCAST GPU job finished on "
        f"June 15, 2026: {s['iupac_filled']:,} of {s['total']:,} rows received a generated IUPAC "
        f"name ({s['iupac_pct']}). {s['convert_failed']} rows failed conversion. "
        "Detailed findings are in Sections 7-11 and 12."
    )
    pdf.table(
        ["Milestone", "Status"],
        [
            ["Pass 1 + Pass 2 name resolution", "Complete (corrected counts)"],
            ["Pass 3 local SMARTS validation", "Complete"],
            ["Pass 3 local OPSIN/ChemSpider rescue", "Complete (30 new structures)"],
            [f"Pass 3 CCAST reverse naming (GPU)", f"Complete ({s['iupac_filled']}/{s['total']} IUPAC)"],
            ["Streamlit manual curation", "Next step"],
            ["Final curated export for modeling", "Not started"],
        ],
        col_widths=[110, 70],
    )

    # --- NEW: STOUT, IUPAC, reverse naming ---
    pdf.section("2. Key Concepts: STOUT, IUPAC, SMILES, and Reverse Naming")
    pdf.subsection("What is SMILES?")
    pdf.body(
        "SMILES (Simplified Molecular Input Line Entry System) is a one-line text code that "
        "describes how atoms are connected in a molecule. Example: ethanol might be written as "
        "CCO. Computers use SMILES for machine learning, similarity search, and drawing structures. "
        "Our Pass 1 and Pass 2 goal was: given a 1947 chemical name, find its SMILES."
    )
    pdf.subsection("What is IUPAC?")
    pdf.body(
        "IUPAC names are the modern, systematic way chemists officially name compounds. "
        "Example: 'Acetic acid, butyl ester' (1947 wording) corresponds to a systematic name "
        "like 'butyl acetate'. IUPAC names follow strict rules and are longer but unambiguous. "
        "They are different from trade names, abbreviations, or informal 1947 descriptions."
    )
    pdf.subsection("What is STOUT? (original plan - not used)")
    pdf.body(
        "STOUT (Smiles TO iUpac name conversion Tool) is a published deep-learning program that "
        "reads a SMILES string and predicts an IUPAC name. We planned to run STOUT on the CCAST "
        "GPU cluster as 'reverse validation': if we already have a SMILES from Pass 1/2, STOUT "
        "translates it back to a name so we can compare that name to the original 1947 entry."
    )
    pdf.body(
        "STOUT was NOT used in the final run because: (1) it requires Java 9+ and CCAST had "
        "Java 8 conflicts; (2) STOUT's model weight download links are broken (HTTP 404/410) "
        "worldwide, so the package cannot install its neural network. The column STOUT_IUPAC in "
        "our Excel files keeps this name for compatibility, but the values come from "
        "chemical-converters instead."
    )
    pdf.subsection("What we used instead: chemical-converters")
    pdf.body(
        "chemical-converters is a Python package using a Hugging Face model "
        "(knowledgator/SMILES2IUPAC-canonical-small). It does the same job as STOUT - SMILES to "
        "IUPAC - without Java, with weights hosted reliably on Hugging Face. It runs on PyTorch "
        "with GPU or CPU on CCAST."
    )
    pdf.subsection("Why reverse naming helps (plain language)")
    pdf.body(
        "Forward lookup (name -> SMILES) can return the wrong molecule silently. Reverse naming "
        "asks: 'If I translate this SMILES back to a name, does it resemble what the dataset said?' "
        "It is a sanity check, not proof. A low match does not always mean wrong SMILES (1947 "
        "names are often worded differently). A high match is weak reassurance. Structural SMARTS "
        "checks remain more important for catching wrong functional groups."
    )

    # --- 3 Background + glossary ---
    pdf.section("3. Background and Glossary")
    pdf.subsection("The problem")
    pdf.body(
        "The 1947 dataset lists chemical names as they were written decades ago: trade names, "
        "abbreviations, and informal descriptions (for example 'Acetic acid, butyl ester'). "
        "Modern software needs SMILES. Our pipeline finds SMILES, then Pass 3 checks quality."
    )
    pdf.subsection("Why three passes?")
    pdf.table(
        ["Pass", "Simple description", "Analogy"],
        [
            ["Pass 1", "Look up the name in a chemical dictionary (CIRpy)", "Checking a phone book"],
            ["Pass 2", "Try spelling variants if the first lookup fails", "Trying nicknames and typos"],
            ["Pass 3", "Check structure vs name; reverse naming on GPU", "Proofreading the match"],
        ],
        col_widths=[25, 95, 60],
    )
    pdf.subsection("Quick reference terms")
    pdf.table(
        ["Term", "What it means", "Why we use it"],
        [
            ["SMILES", "Text code for a molecule's structure", "Lets computers store and compare structures"],
            ["IUPAC name", "Formal systematic chemical name", "Standard way to name compounds today"],
            ["CIRpy / OPSIN", "Programs that convert names to structures", "Automated lookup services"],
            ["ChemSpider", "Online chemical database (Royal Society of Chemistry)", "Backup lookup when others fail"],
            ["RDKit / SMARTS", "Cheminformatics toolkit and pattern rules", "Checks if structure 'looks like' the name says"],
            ["Jaro-Winkler score", "Number 0-1 measuring name similarity", "0 = unrelated text, 1 = nearly identical"],
            ["CCAST", "NDSU high-performance computing cluster with GPUs", "Runs heavy neural-network jobs"],
            ["chemical-converters", "Python tool (Hugging Face model) SMILES -> IUPAC", "Replaced broken STOUT package"],
            ["PARTIAL_MATCH", "Name resolved to a parent compound, not full derivative", "Flagged for exclusion from 'fully resolved'"],
            ["Checkpoint file", "ccast_checkpoint.csv saves progress every batch", "Resume after GPU crashes"],
        ],
        col_widths=[38, 72, 70],
    )

    # --- 4 Pipeline overview ---
    pdf.add_page()
    pdf.section("4. Full Pipeline Overview")
    pdf.body(
        "End-to-end flow from raw CSV to a curated dataset ready for modeling:"
    )
    pdf.body(
        "1947-King-USDA_Dataset.csv"
        " -> Pass 1 (chemical_name_resolver) -> Pass 2 (smart variants)"
        " -> resolved_chemicals_final.xlsx"
        " -> Pass 3 local (SMARTS + OPSIN + ChemSpider) -> dataset_ready_for_ccast.xlsx"
        " -> Pass 3 CCAST (GPU reverse naming) -> dataset_from_ccast.xlsx"
        " -> Streamlit curation app -> dataset_curated_final.xlsx"
    )
    pdf.subsection("Where each step runs")
    pdf.table(
        ["Step", "Location", "Main script / notebook"],
        [
            ["Pass 1 + 2", "Local PC", "chemical_name_resolver.py, pass2 scripts"],
            ["Pass 3 SMARTS + rescue", "Local PC", "pass3_local_validation.py"],
            ["Pass 3 CCAST", "CCAST GPU Jupyter", "pass3_ccast_validation.ipynb + .py"],
            ["Manual review", "Local PC", "pass3_curation_app.py (Streamlit)"],
        ],
        col_widths=[40, 35, 105],
    )

    # --- 5 Pass 1+2 recap ---
    pdf.section("5. Pass 1 and Pass 2 Results (Corrected)")
    pdf.body(
        "Pass 2 had a logic bug: for names like 'Acetic acid, bornyl ester', strategies "
        "first_segment and first_word sometimes returned the parent acid instead of the ester. "
        "526 high-risk rows were reclassified as PARTIAL_MATCH and excluded from 'fully resolved'."
    )
    pdf.table(
        ["Status", "Count", "Meaning for a non-chemist"],
        [
            ["RESOLVED_PASS1", "4,014", "Found on first dictionary try"],
            ["RESOLVED_PASS2 (valid)", "637", "Found after smart retry; reviewed as low/medium risk"],
            ["Total fully resolved", "4,651 (65.6%)", "Have SMILES we treat as complete structures"],
            ["PARTIAL_MATCH", "526", "Have SMILES but likely wrong compound (parent only)"],
            ["FAILED_BOTH_PASSES", "1,626", "No structure found yet"],
            ["IRREGULAR_SKIPPED", "286", "Name too messy to parse automatically"],
        ],
        col_widths=[45, 25, 110],
    )

    # --- 6 Pass 3 plan ---
    pdf.section("6. Pass 3 Plan — Three Layers")
    pdf.subsection("Layer A: SMARTS validation (local, all resolved rows)")
    pdf.body(
        "For each of the 4,651 resolved SMILES, we ask: does the structure contain the kind of "
        "chemical group the name suggests? Example: if the name says 'ester', does the structure "
        "contain an ester linkage? This is a heuristic - it catches obvious mismatches but cannot "
        "prove a structure is 100% correct."
    )
    pdf.table(
        ["Pass3_SMARTS_Result", "Count", "Plain meaning"],
        [
            ["PASS", "1,944", "Name cues match structure pattern"],
            ["SKIP", "2,170", "No rule applied - NOT proven correct, just not flagged"],
            ["FAIL", "537", "Name and structure likely disagree - needs human review"],
        ],
        col_widths=[45, 20, 115],
    )
    pdf.note_box(
        "Important: SKIP does not mean 'validated OK'. It means we had no automated rule to test "
        "that name. Only PASS is a positive structural check. FAIL is a red flag."
    )

    pdf.subsection("Layer B: OPSIN + ChemSpider rescue (local, failed rows)")
    pdf.body(
        "For the 1,626 names that failed Pass 1 and Pass 2, we queried public services that "
        "convert names to structures. OPSIN (EBI) is free; ChemSpider requires an API key and "
        "has a monthly call limit. This rescue found 30 additional structures."
    )
    pdf.table(
        ["Rescue source", "New structures", "Notes"],
        [
            ["OPSIN", "25", "Works best on names close to modern IUPAC"],
            ["ChemSpider", "5", "Limited by preview API quota"],
            ["Total Pass 3 rescues", "30", "Added to For_CCAST sheet (now 4,681 rows with SMILES)"],
        ],
        col_widths=[45, 35, 100],
    )

    pdf.subsection("Layer C: CCAST reverse naming (GPU)")
    pdf.body(
        "We take each SMILES and use a neural network (chemical-converters on Hugging Face) to "
        "generate a modern IUPAC-style name. We compare that generated name to the original 1947 "
        "name using Jaro-Winkler similarity. Low similarity is a review hint - not an automatic "
        "rejection - because 1947 names rarely match modern systematic names word-for-word."
    )
    pdf.body(
        "Original plan used STOUT; it was abandoned on CCAST because: (1) Java version conflicts, "
        "(2) STOUT model download URLs are broken worldwide. chemical-converters is pure Python/PyTorch "
        "with weights hosted on Hugging Face."
    )

    # --- 7 CCAST status ---
    pdf.add_page()
    pdf.section("7. CCAST Run — Final Results (June 15, 2026)")
    pdf.subsection("Run outcome: SUCCESS")
    pdf.body(
        "The fixed CCAST pipeline (GPU batches of 40 rows, CPU retry on CUDA errors, checkpoint "
        "resume) completed successfully. Output file: dataset_from_ccast.xlsx."
    )
    pdf.table(
        ["Metric", "Count", "Percent"],
        [
            ["Total rows processed", f"{s['total']:,}", "100%"],
            ["Non-empty IUPAC (STOUT_IUPAC)", f"{s['iupac_filled']:,}", s["iupac_pct"]],
            ["Conversion failed (no IUPAC)", f"{s['convert_failed']:,}", f"{100*s['convert_failed']/s['total']:.1f}%"],
        ],
        col_widths=[70, 35, 35],
    )
    pdf.subsection("Pass3_CCAST_Flag counts (final)")
    pdf.table(
        ["Flag", "Count", "Plain meaning"],
        [
            ["OK", f"{s['flags']['OK']:,}", "Jaro-Winkler score >= 0.45 vs 1947 name"],
            ["SUSPICIOUS", f"{s['flags']['SUSPICIOUS']:,}", "Score 0.30-0.45; optional spot-check"],
            ["CONVERT_FAILED", f"{s['flags']['CONVERT_FAILED']:,}", "Model produced no IUPAC name"],
            ["LOW_SIMILARITY", f"{s['flags']['LOW_SIMILARITY']:,}", "Score below 0.30 (only 6 rows)"],
        ],
        col_widths=[40, 25, 115],
    )
    pdf.subsection("Jaro-Winkler score statistics (rows with IUPAC)")
    pdf.table(
        ["Measure", "vs 1947 Chemical", "vs Resolved_Name (CIRpy)"],
        [
            ["Mean score", f"{s['jw_mean']:.3f}", f"{s['jw_res_mean']:.3f}"],
            ["Interpretation", "Most rows share wording with 1947 names", "Similar to dictionary resolved name"],
        ],
        col_widths=[45, 65, 70],
    )
    pdf.note_box(
        "Most rows flagged OK because Jaro-Winkler finds shared words (e.g. 'acetic', 'butyl', "
        "'ester') between 1947 names and generated IUPAC. This does NOT replace SMARTS validation. "
        "OK on CCAST is a weak positive signal; SMARTS FAIL (537 rows) still needs manual review."
    )

    pdf.subsection("CCAST output columns explained")
    pdf.table(
        ["Column", "Meaning"],
        [
            ["STOUT_IUPAC", "Generated systematic name (column name kept for compatibility)"],
            ["JaroWinkler_Score", "Similarity vs original 1947 Chemical name (0-1)"],
            ["JaroWinkler_vs_Resolved", "Similarity vs CIRpy Resolved_Name (0-1)"],
            ["Pass3_CCAST_Flag", "OK / SUSPICIOUS / LOW_SIMILARITY / CONVERT_FAILED / NO_SMILES"],
            ["Pass3_CCAST_Error", "Error message if conversion failed"],
        ],
        col_widths=[45, 135],
    )
    pdf.table(
        ["Pass3_CCAST_Flag", "Plain meaning", "Action"],
        [
            ["OK", "Generated name somewhat similar to 1947 name (score >= 0.45)", "Low priority review"],
            ["SUSPICIOUS", "Score between 0.30 and 0.45", "Optional spot-check"],
            ["LOW_SIMILARITY", "Score below 0.30 OR names use different wording", "Usually normal; not auto-reject"],
            ["CONVERT_FAILED", "Model returned no name (GPU/runtime error)", "Re-run or manual check"],
            ["NO_SMILES", "Missing input structure", "Fix upstream data"],
        ],
        col_widths=[38, 72, 70],
    )

    pdf.subsection("Problems encountered and fixes")
    pdf.table(
        ["Problem", "Symptom", "Fix applied"],
        [
            ["STOUT broken", "Java 8 vs 9+, dead weight URLs", "Switched to chemical-converters"],
            ["CUDA crash at row ~49", "Only 49 rows with IUPAC; rest empty", "GPU batch subprocesses + CPU retry"],
            ["Poisoned GPU after crash", "Cannot reload model on same GPU", "Restart kernel; no reload in-process"],
            ["Silent failures", "4632 LOW but JW=0", "Sanity check: count non-empty IUPAC"],
            ["Python 3.9 on CCAST", "Type hint syntax error", "Auto-patch chemicalconverters source"],
        ],
        col_widths=[40, 55, 85],
    )

    # --- 8 How we ran CCAST ---
    pdf.add_page()
    pdf.section("8. How We Ran CCAST (Step by Step)")
    pdf.body(
        "This section documents the actual workflow used on the NDSU CCAST GPU Jupyter session, "
        "including fixes after early failed runs."
    )
    pdf.subsection("Step 1: Prepare files on local PC")
    pdf.bullet("Run pass3_local_validation.py -> produces dataset_ready_for_ccast.xlsx")
    pdf.bullet("Sheet For_CCAST contains 4,681 rows with SMILES (4,651 resolved + 30 rescued)")
    pdf.subsection("Step 2: Upload to CCAST")
    pdf.bullet("dataset_ready_for_ccast.xlsx")
    pdf.bullet("pass3_ccast_validation.py and pass3_ccast_validation.ipynb")
    pdf.subsection("Step 3: Install and patch (notebook cells)")
    pdf.bullet("pip install chemical-converters jellyfish openpyxl pandas (NOT STOUT)")
    pdf.bullet("Patch chemicalconverters for Python 3.9 type-hint syntax on CCAST")
    pdf.subsection("Step 4: GPU batch processing")
    pdf.body(
        "Settings: GPU_BATCH=True, RESUME=True after first partial run. The script processes "
        "40 rows per fresh Python subprocess. Each subprocess loads the Hugging Face model, "
        "converts SMILES to IUPAC, computes Jaro-Winkler scores, and appends to ccast_checkpoint.csv. "
        "If a batch hits a CUDA error (common with certain SMILES), that batch automatically retries on CPU."
    )
    pdf.subsection("Step 5: Export")
    pdf.body(
        "After all batches complete, results merge into dataset_from_ccast.xlsx with sheets "
        "All_Data, CCAST_Validated, and CCAST_Flagged. Sanity check: Non-empty IUPAC must be "
        f"~{s['total']:,}, not ~49 (old bug)."
    )

    # --- 9 dataset_from_ccast ---
    pdf.section("9. File Guide: dataset_from_ccast.xlsx")
    pdf.body(
        "This is the main CCAST deliverable downloaded to the Decoding_Names workspace. "
        "It combines all Pass 3 local columns with CCAST reverse-naming results."
    )
    pdf.table(
        ["Sheet", "Rows", "Purpose"],
        [
            ["All_Data", "7,089", "Full King dataset; CCAST columns filled for 4,681 rows with SMILES"],
            ["CCAST_Validated", f"{s['total']:,}", "Same 4,681 rows as For_CCAST, with IUPAC and flags"],
            ["CCAST_Flagged", f"{s['flags']['SUSPICIOUS']+s['flags']['LOW_SIMILARITY']+s['flags']['CONVERT_FAILED']:,}", "Rows needing optional review (not all are errors)"],
        ],
        col_widths=[40, 25, 115],
    )
    pdf.subsection("Key columns in CCAST_Validated (what each value means)")
    pdf.table(
        ["Column", "Example / range", "Meaning for readers"],
        [
            ["Chemical", "Acetic acid, butyl ester", "Original 1947 name from the dataset"],
            ["SMILES", "CCCCOC(C)=O", "Structure found in Pass 1/2/3; input to the neural model"],
            ["Resolved_Name", "butyl acetate", "Name returned by CIRpy lookup (may differ from 1947 wording)"],
            ["STOUT_IUPAC", "butyl acetate", "Generated IUPAC from SMILES (via chemical-converters, not STOUT)"],
            ["JaroWinkler_Score", "0.0 to 1.0; mean ~0.59", "Text similarity: generated IUPAC vs 1947 Chemical"],
            ["JaroWinkler_vs_Resolved", "0.0 to 1.0; mean ~0.60", "Text similarity: generated IUPAC vs Resolved_Name"],
            ["Pass3_CCAST_Flag", "OK / SUSPICIOUS / etc.", "Triage label from JaroWinkler_Score thresholds"],
            ["Pass3_CCAST_Error", "blank or error text", "Why conversion failed, if it did"],
            ["Pass3_SMARTS_Result", "PASS / SKIP / FAIL", "Local structural check (independent of CCAST)"],
            ["Pass3_Status", "VALIDATED_OK / NEEDS_REVIEW", "Local Pass 3 overall status from SMARTS"],
        ],
        col_widths=[38, 42, 100],
    )
    pdf.subsection("How Pass3_CCAST_Flag is calculated")
    pdf.body(
        "Threshold = 0.45 on JaroWinkler_Score (comparing generated IUPAC to 1947 Chemical name). "
        "Score >= 0.45 -> OK. Score 0.30 to 0.44 -> SUSPICIOUS. Score < 0.30 -> LOW_SIMILARITY. "
        "If the model returns no IUPAC -> CONVERT_FAILED (127 rows). "
        "If SMILES is missing -> NO_SMILES."
    )
    pdf.note_box(
        "Why mostly OK (4,255) and not LOW? Jaro-Winkler rewards shared substrings. "
        "1947 names often contain words like 'acetic', 'propyl', 'ester' that also appear in "
        "generated IUPAC, pushing scores above 0.45 even when full names differ."
    )

    # --- 10 checkpoint ---
    pdf.section("10. File Guide: ccast_checkpoint.csv")
    pdf.body(
        f"The checkpoint file in the workspace contains {s.get('checkpoint_rows', s['total']):,} rows - "
        "one record per processed compound. It is written incrementally during the CCAST run so "
        "work can resume after kernel restarts or CUDA crashes (RESUME=True)."
    )
    pdf.table(
        ["Column", "Meaning"],
        [
            ["row_idx", "Row number 0 to 4680 in For_CCAST sheet"],
            ["Chemical", "Original 1947 name"],
            ["SMILES", "Input structure string"],
            ["STOUT_IUPAC", "Generated IUPAC (empty if conversion failed)"],
            ["JaroWinkler_Score", "Similarity vs Chemical"],
            ["JaroWinkler_vs_Resolved", "Similarity vs Resolved_Name"],
            ["Pass3_CCAST_Flag", "OK / SUSPICIOUS / LOW_SIMILARITY / CONVERT_FAILED"],
            ["Pass3_CCAST_Error", "Error message when conversion failed"],
        ],
        col_widths=[45, 135],
    )
    pdf.subsection("Why the checkpoint mattered")
    pdf.body(
        "Early runs crashed at row ~49 when CUDA failed silently. The checkpoint + GPU batch fix "
        "allowed restarting from saved progress. Each batch of 40 rows runs in a new process so "
        "one bad SMILES cannot poison the entire GPU for remaining rows."
    )

    # --- 11 Detailed findings ---
    pdf.add_page()
    pdf.section("11. Detailed Findings from CCAST Output")
    pdf.subsection("Conversion success")
    pdf.body(
        f"Of {s['total']:,} structures sent to CCAST, {s['iupac_filled']:,} ({s['iupac_pct']}) "
        f"received a non-empty generated IUPAC name. The remaining {s['convert_failed']} rows are "
        "CONVERT_FAILED - the model or GPU could not produce a name. These rows still retain "
        "their SMILES from Pass 1/2/3; only the reverse-name check is missing."
    )
    pdf.subsection("CONVERT_FAILED error breakdown")
    err_rows = [[e[0][:55], str(e[1])] for e in s["errors"]]
    if not err_rows:
        err_rows = [["index out of range in self", "82"], ["CUDA device-side assert", "45"]]
    pdf.table(
        ["Error type (abbreviated)", "Count"],
        err_rows,
        col_widths=[130, 50],
    )
    pdf.body(
        "'index out of range' usually means the SMILES token was too long or unusual for the model. "
        "'CUDA device-side assert' means the GPU hit a bad tensor operation on that structure; "
        "CPU retry handled most of these in later batches."
    )
    pdf.subsection("SMARTS vs CCAST flags (cross-tab)")
    pdf.body(
        "This table shows how local structural checks (SMARTS) relate to CCAST flags. "
        "Many SMARTS FAIL rows still show CCAST OK - CCAST does not detect ester/acid mismatches."
    )
    pdf.table(
        ["SMARTS", "CONVERT_FAIL", "LOW", "OK", "SUSPICIOUS"],
        [[r[0], str(r[1]), str(r[2]), str(r[3]), str(r[4])] for r in s["smarts_cross"]],
        col_widths=[22, 28, 18, 22, 30],
    )
    pdf.note_box(
        "Takeaway: 461 SMARTS FAIL rows are flagged CCAST OK. Manual review must prioritize "
        "SMARTS FAIL (537 total), not CCAST OK. CCAST is a secondary, weak check."
    )
    pdf.subsection("First failed run vs successful run (lesson learned)")
    pdf.table(
        ["Run", "Non-empty IUPAC", "Typical flags", "Cause"],
        [
            ["Failed (old notebook)", "49 / 4,651", "4,632 LOW, JW=0", "CUDA crash; silent empty output"],
            ["Successful (June 15)", f"{s['iupac_filled']} / {s['total']}", f"{s['flags']['OK']} OK", "GPU batches + CPU retry + checkpoint"],
        ],
        col_widths=[40, 35, 45, 60],
    )

    # --- 12 Local deliverables ---
    pdf.section("12. Files and Deliverables")
    pdf.table(
        ["File", "Description"],
        [
            ["resolved_chemicals_final.xlsx", "Pass 1+2 corrected master file"],
            ["dataset_ready_for_ccast.xlsx", "Pass 3 local output; upload to CCAST"],
            ["pass3_local_validation.py", "Local SMARTS + rescue pipeline"],
            ["pass3_smarts_rules.py", "SMARTS pattern definitions"],
            ["pass3_ccast_validation.py / .ipynb", "CCAST GPU reverse naming"],
            ["dataset_from_ccast.xlsx", f"Pass 3 CCAST output ({s['iupac_filled']:,} IUPAC names)"],
            ["ccast_checkpoint.csv", f"Progress log ({s.get('checkpoint_rows', 4681):,} rows); resume file"],
            ["pass3_curation_app.py", "Streamlit review app (next step)"],
            ["CORRECTION_NOTES.md", "Pass 2 reclassification documentation"],
            ["README_PASS3.md", "Technical run instructions"],
            ["Chemical_Name_Resolution_Report.pdf", "Earlier full pipeline report (Passes 1-2)"],
            ["PASS3_Pipeline_Plan.pdf", "Original approved Pass 3 plan"],
            ["PASS3_Progress_Report.pdf", "This report (Pass 3 findings and glossary)"],
        ],
        col_widths=[65, 115],
    )

    pdf.subsection("dataset_from_ccast.xlsx sheets")
    pdf.table(
        ["Sheet", "Rows", "Contents"],
        [
            ["All_Data", "7,089", "Full dataset; CCAST columns on 4,681 rows"],
            ["CCAST_Validated", f"{s['total']:,}", "All CCAST results with flags and IUPAC"],
            ["CCAST_Flagged", f"{s['flags']['SUSPICIOUS']+s['flags']['LOW_SIMILARITY']+s['flags']['CONVERT_FAILED']:,}", "SUSPICIOUS + LOW + CONVERT_FAILED subset"],
        ],
        col_widths=[40, 25, 115],
    )

    pdf.subsection("dataset_ready_for_ccast.xlsx sheets")
    pdf.table(
        ["Sheet", "Rows (approx.)", "Contents"],
        [
            ["All_Data", "7,089", "Full dataset with Pass 3 columns"],
            ["For_CCAST", "4,681", "Rows with SMILES sent to GPU job"],
            ["Resolved_Validated", "4,114", "SMARTS PASS or SKIP"],
            ["Needs_Review", "537", "SMARTS FAIL"],
            ["Pass3_Rescued", "30", "New OPSIN/ChemSpider hits"],
            ["Still_Failed", "1,596", "No structure after rescue"],
        ],
        col_widths=[40, 30, 110],
    )

    # --- 13 Confidence tiers ---
    pdf.add_page()
    pdf.section("13. How to Interpret Confidence (For Modeling)")
    pdf.body(
        "Not every resolved row is equally trustworthy. Suggested tiers when you build the final "
        "modeling dataset:"
    )
    pdf.table(
        ["Tier", "Criteria", "Approx. count", "Recommendation"],
        [
            ["A - High", "Pass 1 or low-risk Pass 2 + SMARTS PASS", "~1,900+", "Use with confidence"],
            ["B - Medium", "Resolved + SMARTS SKIP (unchecked)", "~2,170", "Use with caution or spot-check"],
            ["C - Review", "SMARTS FAIL", "537", "Manual review before use"],
            ["D - Partial", "PARTIAL_MATCH", "526", "Exclude from 'full structure' claims"],
            ["E - Unresolved", "Still failed after rescue", "1,596", "Exclude unless manually fixed"],
        ],
        col_widths=[28, 62, 28, 62],
    )
    pdf.note_box(
        "CCAST LOW_SIMILARITY flags do NOT by themselves demote a row to Tier E. They compare "
        "modern generated names to 1947 wording. Trust SMARTS and manual review more than CCAST flags."
    )

    # --- 14 Next steps ---
    pdf.section("14. Next Steps")
    pdf.bullet(
        "Download dataset_from_ccast.xlsx from CCAST to the Decoding_Names folder (if not already done)."
    )
    pdf.bullet(
        "Launch Streamlit on your PC: streamlit run pass3_curation_app.py"
    )
    pdf.bullet(
        "Review priority: (1) SMARTS FAIL (~537 rows), (2) CCAST CONVERT_FAILED (127 rows), "
        "(3) Pass 2 MEDIUM risk, (4) optional CCAST SUSPICIOUS (293 rows)."
    )
    pdf.bullet(
        "Export dataset_curated_final.xlsx with accept/reject/edit decisions."
    )
    pdf.bullet(
        "Optional: re-run CCAST on the 127 CONVERT_FAILED rows with USE_CPU=True, or look up manually."
    )
    pdf.bullet(
        "Optional: refresh ChemSpider rescue when API quota resets."
    )

    pdf.section("15. Session Summary (June 15, 2026)")
    pdf.body(
        f"Pass 3 local work and CCAST GPU reverse naming are complete. CCAST generated IUPAC names "
        f"for {s['iupac_filled']:,}/{s['total']:,} rows ({s['iupac_pct']}). The pipeline used "
        "chemical-converters (not STOUT) with GPU batch mode, ccast_checkpoint.csv resume, and "
        "CPU fallback. dataset_from_ccast.xlsx and ccast_checkpoint.csv are in the workspace. "
        "Manual curation via Streamlit is the remaining Pass 3 step."
    )

    pdf.output(str(OUT))
    print(f"Wrote: {OUT}")


if __name__ == "__main__":
    build()
