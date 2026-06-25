"""Generate PDF report summarizing chemical name resolution findings."""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd
from fpdf import FPDF

from pass2_validation import ROOT_FALLBACK_STRATEGIES, classify_rescue_risk

ROOT = Path(__file__).parent
FINAL_LOCAL = ROOT / "resolved_chemicals_final.xlsx"
PASS3_LOCAL = ROOT / "dataset_ready_for_ccast.xlsx"
FINAL_TEMP = Path(os.environ.get("TEMP", "/tmp")) / "resolved_chemicals_final.xlsx"
OUT_PDF = ROOT / "Chemical_Name_Resolution_Report.pdf"


def sanitize(text: str) -> str:
    """Make text safe for Helvetica / Latin-1 PDF fonts."""
    replacements = {
        "\u2014": "-",  # em dash
        "\u2013": "-",  # en dash
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2026": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def load_final_excel() -> Path:
    if FINAL_LOCAL.exists():
        try:
            pd.read_excel(FINAL_LOCAL, sheet_name="Pass2_Rescued", nrows=1)
            return FINAL_LOCAL
        except PermissionError:
            pass
    if not FINAL_TEMP.exists():
        raise FileNotFoundError(
            "resolved_chemicals_final.xlsx is locked or missing. "
            "Close Excel or copy the file to TEMP."
        )
    return FINAL_TEMP


def gather_stats() -> dict:
    path = load_final_excel()
    all_data = pd.read_excel(path, sheet_name="All_Data")
    p2 = pd.read_excel(path, sheet_name="Pass2_Rescued")
    strat_report = pd.read_excel(path, sheet_name="Strategy_Report")

    try:
        partial = pd.read_excel(path, sheet_name="Partial_Match")
        corrected = True
    except ValueError:
        partial = pd.DataFrame()
        corrected = False

    name_col = "Chemical" if "Chemical" in all_data.columns else "_name"
    total = len(all_data)
    pass1 = int((all_data["Status"] == "RESOLVED_PASS1").sum())
    pass2 = len(p2)
    partial_n = int((all_data["Status"] == "PARTIAL_MATCH").sum())
    still_failed = int((all_data["Status"] == "FAILED_BOTH_PASSES").sum())
    irregular = int((all_data["Status"] == "IRREGULAR_SKIPPED").sum())
    fully_resolved = int(all_data["Status"].isin(["RESOLVED_PASS1", "RESOLVED_PASS2"]).sum())

    nominal_pass2 = pass2 + partial_n
    nominal_resolved = pass1 + nominal_pass2

    # Historical validation on all Pass 2 attempts (valid + partial)
    p2_all = pd.concat([p2, partial], ignore_index=True) if corrected else p2
    fs = p2_all[p2_all["Resolution_Strategy"] == "first_segment"]
    fw = p2_all[p2_all["Resolution_Strategy"] == "first_word"]

    fs_risks = [classify_rescue_risk(row)[0] for _, row in fs.iterrows()]
    fw_risks = [classify_rescue_risk(row)[0] for _, row in fw.iterrows()]
    fs_high_n = sum(1 for r in fs_risks if r == "HIGH")
    fs_medium_n = sum(1 for r in fs_risks if r == "MEDIUM")
    fs_low_n = sum(1 for r in fs_risks if r == "LOW")
    fw_high_n = sum(1 for r in fw_risks if r == "HIGH")
    fw_medium_n = sum(1 for r in fw_risks if r == "MEDIUM")

    high_reasons = []
    if corrected and not partial.empty and "Validation_Reason" in partial.columns:
        high_reasons = Counter(partial["Validation_Reason"].dropna()).most_common()
    elif not fs.empty:
        fs_tmp = fs.copy()
        fs_tmp["Validation_Risk"] = fs_risks
        fs_tmp["Validation_Reason"] = [classify_rescue_risk(row)[1] for _, row in fs.iterrows()]
        high_reasons = Counter(
            fs_tmp.loc[fs_tmp["Validation_Risk"] == "HIGH", "Validation_Reason"]
        ).most_common()

    samples_high = []
    sample_src = partial if corrected and not partial.empty else fs
    for _, row in sample_src.head(8).iterrows():
        samples_high.append(
            (
                str(row.get(name_col, ""))[:72],
                str(row.get("Resolved_Name", ""))[:40],
            )
        )

    # Breakdown of valid Pass 2 rescues (637) by strategy and risk tier
    p2_risks = []
    for _, row in p2.iterrows():
        strategy_name = str(row.get("Resolution_Strategy", ""))
        if strategy_name in ROOT_FALLBACK_STRATEGIES:
            risk, _ = classify_rescue_risk(row)
        else:
            risk = "N/A"
        p2_risks.append(risk)

    p2_scored = p2.copy()
    p2_scored["Risk_Tier"] = p2_risks
    p2_na = sum(1 for r in p2_risks if r == "N/A")
    p2_medium_valid = sum(1 for r in p2_risks if r == "MEDIUM")
    p2_low_valid = sum(1 for r in p2_risks if r == "LOW")
    p2_fallback_valid = p2_medium_valid + p2_low_valid

    crosstab_rows = []
    for strategy_name in sorted(p2_scored["Resolution_Strategy"].unique(), key=str):
        sub = p2_scored[p2_scored["Resolution_Strategy"] == strategy_name]
        med = int((sub["Risk_Tier"] == "MEDIUM").sum())
        low = int((sub["Risk_Tier"] == "LOW").sum())
        na = int((sub["Risk_Tier"] == "N/A").sum())
        crosstab_rows.append([strategy_name, str(med), str(low), str(na), str(len(sub))])

    tier_a = pass1 + p2_na
    tier_b = p2_fallback_valid
    conservative_resolved = fully_resolved - p2_medium_valid

    medium_samples = []
    low_samples = []
    fb_valid = p2_scored[p2_scored["Resolution_Strategy"].isin(ROOT_FALLBACK_STRATEGIES)]
    for _, row in fb_valid[fb_valid["Risk_Tier"] == "MEDIUM"].head(6).iterrows():
        medium_samples.append(
            (str(row.get(name_col, ""))[:60], str(row.get("Resolved_Name", ""))[:35])
        )
    for _, row in fb_valid[fb_valid["Risk_Tier"] == "LOW"].head(4).iterrows():
        low_samples.append(
            (str(row.get(name_col, ""))[:60], str(row.get("Resolved_Name", ""))[:35])
        )

    # Pass 3 SMARTS validation stats (if local Pass 3 has run)
    p3_pass = p3_skip = p3_fail = p3_review = p3_validated = 0
    p3_ran = False
    if PASS3_LOCAL.exists():
        try:
            p3_df = pd.read_excel(PASS3_LOCAL, sheet_name="All_Data")
            mask = p3_df["Status"].isin({"RESOLVED_PASS1", "RESOLVED_PASS2", "RESOLVED_PASS3"})
            if "Pass3_SMARTS_Result" in p3_df.columns:
                p3_ran = True
                sub = p3_df.loc[mask]
                p3_pass = int((sub["Pass3_SMARTS_Result"] == "PASS").sum())
                p3_skip = int((sub["Pass3_SMARTS_Result"] == "SKIP").sum())
                p3_fail = int((sub["Pass3_SMARTS_Result"] == "FAIL").sum())
                p3_review = int((sub["Pass3_Status"] == "NEEDS_REVIEW").sum())
                p3_validated = int((sub["Pass3_Status"] == "VALIDATED_OK").sum())
        except Exception:
            pass

    return {
        "report_date": date.today().strftime("%B %d, %Y"),
        "corrected": corrected,
        "total": total,
        "pass1": pass1,
        "pass2": pass2,
        "partial_match": partial_n,
        "still_failed": still_failed,
        "irregular": irregular,
        "fully_resolved": fully_resolved,
        "fully_resolved_pct": fully_resolved / total * 100 if total else 0,
        "nominal_resolved": nominal_resolved,
        "nominal_pct": nominal_resolved / total * 100 if total else 0,
        "reclassified": partial_n,
        "fs_total": len(fs),
        "fs_high": fs_high_n,
        "fs_medium": fs_medium_n,
        "fs_low": fs_low_n,
        "fw_total": len(fw),
        "fw_high": fw_high_n,
        "fw_medium": fw_medium_n,
        "high_reasons": high_reasons,
        "strategies": list(zip(strat_report["Strategy"], strat_report["Rescues"])),
        "samples_high": samples_high,
        "data_source": str(path.name),
        # Valid Pass 2 breakdown (section 11+)
        "p2_na": p2_na,
        "p2_medium_valid": p2_medium_valid,
        "p2_low_valid": p2_low_valid,
        "p2_fallback_valid": p2_fallback_valid,
        "crosstab_rows": crosstab_rows,
        "tier_a": tier_a,
        "tier_b": tier_b,
        "tier_c": partial_n,
        "tier_d": still_failed,
        "conservative_resolved": conservative_resolved,
        "conservative_pct": conservative_resolved / total * 100 if total else 0,
        "medium_samples": medium_samples,
        "low_samples": low_samples,
        "nominal_pass2_before": nominal_pass2,
        "p3_ran": p3_ran,
        "p3_pass": p3_pass,
        "p3_skip": p3_skip,
        "p3_fail": p3_fail,
        "p3_review": p3_review,
        "p3_validated": p3_validated,
    }


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, "Chemical Name Resolution Report - 1947 King USDA Dataset", align="R")
            self.ln(4)
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def title_page(self, report_date: str):
        self.add_page()
        self.ln(40)
        self.set_font("Helvetica", "B", 22)
        self.multi_cell(0, 12, "Chemical Name Resolution Report", align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 14)
        self.multi_cell(0, 8, "1947 King USDA Repellent Dataset", align="C")
        self.ln(6)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 7, "Automated SMILES lookup via PubChem / CIRpy\nPass 1, Pass 2, and quality validation", align="C")
        self.ln(20)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 8, f"Report date: {report_date}", align="C")
        self.ln(6)
        self.cell(0, 8, "North Dakota State University / Insectapel Project", align="C")

    def section(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_fill_color(230, 240, 250)
        self.cell(0, 10, title, ln=True, fill=True)
        self.ln(2)

    def subsection(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, title, ln=True)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, sanitize(text))
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        x = self.get_x()
        self.cell(6, 5.5, "-")
        self.multi_cell(0, 5.5, sanitize(text))
        self.set_x(x)

    def _row_height(self, col_widths: list[float], row: list, line_h: float = 5, pad: float = 2) -> float:
        max_lines = 1
        for i, cell in enumerate(row):
            lines = self.multi_cell(
                col_widths[i] - 2,
                line_h,
                sanitize(str(cell)),
                split_only=True,
            )
            max_lines = max(max_lines, len(lines))
        return max(max_lines * line_h + pad, 7)

    def table(self, headers: list[str], rows: list[list], col_widths: list[float] | None = None):
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
            if self.get_y() > 260:
                self.add_page()
                draw_header()
                self.set_font("Helvetica", "", 9)

            row_h = self._row_height(col_widths, row, line_h=line_h)
            y0 = self.get_y()
            x0 = self.l_margin

            if fill:
                self.set_fill_color(245, 248, 252)
            else:
                self.set_fill_color(255, 255, 255)

            # Draw cell boxes (background + border only)
            for i in range(len(row)):
                self.set_xy(x0 + sum(col_widths[:i]), y0)
                self.cell(col_widths[i], row_h, "", border=1, fill=fill)

            # Draw text once per cell
            for i, cell in enumerate(row):
                self.set_xy(x0 + sum(col_widths[:i]) + 1, y0 + 1)
                self.multi_cell(col_widths[i] - 2, line_h, sanitize(str(cell)))

            self.set_xy(x0, y0 + row_h)
            fill = not fill

        self.ln(3)


def build_report(stats: dict) -> Path:
    pdf = ReportPDF()
    pdf.title_page(stats["report_date"])
    pdf.add_page()

    # Executive summary
    pdf.section("1. Executive Summary")
    pdf.body(
        "This report documents automated resolution of historical chemical names from the "
        "1947 King USDA repellent dataset into machine-readable SMILES structures. "
        "A two-pass lookup pipeline was run on CCAST, followed by quality validation "
        "and correction of Pass 2 false-positive rescues."
    )
    adj_label = "Corrected (full)" if stats["corrected"] else "Estimated (pre-correction)"
    pdf.table(
        ["Metric", "Before correction", adj_label],
        [
            ["Total dataset names", str(stats["total"]), str(stats["total"])],
            ["Fully resolved", f"{stats['nominal_resolved']} ({stats['nominal_pct']:.1f}%)",
             f"{stats['fully_resolved']} ({stats['fully_resolved_pct']:.1f}%)"],
            ["PARTIAL_MATCH (parent compound)", "0", str(stats["partial_match"])],
            ["Still failed lookup", str(stats["still_failed"]), str(stats["still_failed"])],
            ["Irregular (skipped)", str(stats["irregular"]), str(stats["irregular"])],
        ],
        col_widths=[70, 55, 55],
    )
    if stats["corrected"]:
        pdf.body(
            f"Corrections applied: {stats['reclassified']} HIGH-risk Pass 2 rescues "
            f"(first_segment / first_word) were reclassified as PARTIAL_MATCH and excluded "
            f"from the resolved set and structure gallery. Pass 2 logic was updated to "
            f"prevent these fallbacks on derivative names in future runs."
        )
    else:
        pdf.body(
            "Key finding: Nearly half of Pass 2 rescues used the first_segment strategy, which "
            "often resolves a parent acid or base compound instead of the intended ester, salt, "
            "or derivative. Run apply_pass2_corrections.py to apply fixes."
        )

    # Background
    pdf.section("2. Background and Objective")
    pdf.body(
        "The 1947 King USDA dataset contains approximately 7,089 chemical names collected "
        "for insect repellent research. Many names use archaic 1940s nomenclature, trade "
        "names, or descriptive comma-separated phrases (e.g., 'Acetic acid, bornyl ester'). "
        "The goal is to convert each resolvable name into a SMILES string for cheminformatics "
        "and structure-based analysis."
    )
    pdf.subsection("Data source")
    pdf.bullet("Input: 1947-King-USDA_Dataset.csv (Mol_Lib folder)")
    pdf.bullet("Primary tools: PubChemPy, CIRpy (Chemical Identifier Resolver)")
    pdf.bullet("Outputs: resolved_chemicals_final.xlsx, structure HTML galleries")

    # Methodology
    pdf.section("3. Methodology")
    pdf.subsection("Pass 1 - Direct lookup")
    pdf.body(
        "Each name was classified as REGULAR, SEMI_REGULAR, or IRREGULAR. IRREGULAR entries "
        "(286 names with non-standard formatting) were skipped. Resolvable names were queried "
        "against PubChem and CIRpy. All 4,014 successful Pass 1 hits came from CIRpy."
    )
    pdf.subsection("Pass 2 - Smart variant retry")
    pdf.body(
        "The 2,789 Pass 1 failures were retried using generated name variants: acid-ester flip, "
        "archaic term substitution, prefix normalization (n-, iso-, dl-, etc.), comma-to-space "
        "conversion, stereochemistry stripping, and fallback strategies (first_segment, first_word). "
        "A disk cache (pass2_cache.json) avoided redundant API calls. Runtime on CCAST: ~95 minutes."
    )
    pdf.subsection("Quality validation")
    pdf.body(
        "Pass 2 first_segment and first_word rescues were reviewed with pattern-based heuristics. "
        "Names where the comma suffix indicates an ester, salt, diester, or other derivative "
        "were flagged HIGH risk when only the text before the first comma was resolved."
    )

    # Pass 1 results
    pdf.section("4. Pass 1 Results")
    pdf.table(
        ["Category", "Count", "Share of total"],
        [
            ["REGULAR names", "6,762", "95.4%"],
            ["SEMI_REGULAR names", "41", "0.6%"],
            ["IRREGULAR (skipped)", "286", "4.0%"],
            ["Resolvable attempted", "6,803", "96.0%"],
            ["Resolved (SMILES found)", "4,014", "59.0% of attempted"],
            ["Failed lookup", "2,789", "41.0% of attempted"],
        ],
        col_widths=[80, 40, 50],
    )

    # Pass 2 results
    pdf.section("5. Pass 2 Results")
    pass2_pct = stats["pass2"] / 2789 * 100 if stats["pass2"] else 0
    pdf.table(
        ["Metric", "Value"],
        [
            ["Input (Pass 1 failures)", "2,789"],
            ["Pass 2 rescues (valid, after correction)", f"{stats['pass2']} ({pass2_pct:.1f}% of failures)"],
            ["Reclassified to PARTIAL_MATCH", str(stats["partial_match"])],
            ["Still failed after Pass 2", str(stats["still_failed"])],
            ["Fully resolved (Pass 1 + valid Pass 2)",
             f"{stats['fully_resolved']} / {stats['total']} ({stats['fully_resolved_pct']:.1f}%)"],
            ["Resolution source", "CIRpy (all Pass 2 hits)"],
        ],
        col_widths=[90, 90],
    )

    pdf.subsection("Pass 2 strategy breakdown (valid rescues)")
    strat_rows = [
        [s, str(n), f"{n / stats['pass2'] * 100:.1f}%"] if stats["pass2"] else [s, str(n), "0%"]
        for s, n in stats["strategies"]
    ]
    pdf.table(["Strategy", "Rescues", "% of Pass 2"], strat_rows, col_widths=[90, 35, 35])

    # Quality validation
    pdf.section("6. Quality Validation - first_segment Strategy")
    pdf.body(
        "The first_segment strategy takes text before the first comma and looks up that substring. "
        "For derivative names this frequently returns the parent compound rather than the full molecule."
    )
    pdf.table(
        ["Risk level", "Count", "Percent"],
        [
            ["HIGH (reclassified to PARTIAL_MATCH)", str(stats["fs_high"]),
             f"{stats['fs_high']/stats['fs_total']*100:.1f}%" if stats["fs_total"] else "0%"],
            ["MEDIUM (needs review)", str(stats["fs_medium"]),
             f"{stats['fs_medium']/stats['fs_total']*100:.1f}%" if stats["fs_total"] else "0%"],
            ["LOW (likely correct)", str(stats["fs_low"]),
             f"{stats['fs_low']/stats['fs_total']*100:.1f}%" if stats["fs_total"] else "0%"],
            ["Total first_segment attempts", str(stats["fs_total"]), "100%"],
        ],
        col_widths=[70, 35, 35],
    )

    pdf.subsection("HIGH-risk reason breakdown")
    reason_rows = [[sanitize(r[:65]), str(n)] for r, n in stats["high_reasons"]]
    pdf.table(["Reason", "Count"], reason_rows, col_widths=[130, 30])

    pdf.subsection("first_word strategy (related concern)")
    pdf.table(
        ["Risk level", "Count"],
        [
            ["HIGH", str(stats["fw_high"])],
            ["MEDIUM", str(stats["fw_medium"])],
            ["LOW", str(stats["fw_total"] - stats["fw_high"] - stats["fw_medium"])],
            ["Total first_word rescues", str(stats["fw_total"])],
        ],
        col_widths=[90, 40],
    )

    pdf.subsection("Corrected resolution summary")
    pdf.table(
        ["Estimate", "Value"],
        [
            ["HIGH-risk rescues reclassified", str(stats["fs_high"] + stats["fw_high"])],
            ["Valid Pass 2 rescues remaining", str(stats["pass2"])],
            ["Fully resolved total",
             f"{stats['fully_resolved']} / {stats['total']} ({stats['fully_resolved_pct']:.1f}%)"],
            ["PARTIAL_MATCH (audit only)", str(stats["partial_match"])],
        ],
        col_widths=[110, 70],
    )

    # Examples
    pdf.section("7. Examples of Likely False Positives")
    pdf.body(
        "The following Pass 2 first_segment rescues illustrate the problem: the database "
        "returned a valid structure, but for the wrong chemical."
    )
    ex_rows = [[orig, resolved] for orig, resolved in stats["samples_high"]]
    pdf.table(["Original name", "Resolved as"], ex_rows, col_widths=[110, 70])

    # Remaining failures
    pdf.section("8. Why Names Still Fail")
    pdf.bullet("Archaic or non-IUPAC 1947 naming not in modern databases")
    pdf.bullet("Typos and OCR-like errors (e.g., propiomic, lso-butyric)")
    pdf.bullet("Complex salts, hydrogenated mixtures, and condensate residues")
    pdf.bullet("Obscure acetolactic and polymeric ester descriptions")
    pdf.bullet("286 IRREGULAR names intentionally excluded from lookup")
    pdf.bullet("Pass 2 notebook describes fuzzy PubChem search but code uses exact name match only")
    pdf.ln(2)

    # Recommendations
    pdf.section("9. Corrections Applied and Next Steps")
    if stats["corrected"]:
        pdf.subsection("Corrections completed")
        pdf.bullet(
            f"Reclassified {stats['partial_match']} HIGH-risk rescues as PARTIAL_MATCH "
            f"in resolved_chemicals_final.xlsx."
        )
        pdf.bullet(
            "Updated generate_smart_variants() to skip first_segment / first_word on derivative names."
        )
        pdf.bullet("Regenerated resolved_structures_corrected.html (PARTIAL_MATCH excluded).")
    else:
        pdf.subsection("Immediate actions")
        pdf.bullet("Run apply_pass2_corrections.py to apply reclassification and re-export.")

    pdf.subsection("Pass 3 enhancements")
    pdf.bullet("OPSIN name-to-structure parser for systematic names")
    pdf.bullet("PubChem fuzzy / similarity search (as originally planned)")
    pdf.bullet("Expanded archaic and typo correction dictionary")
    pdf.bullet("Dedicated salt and mixture handling rules")
    pdf.bullet("Manual review queue for Still_Failed and MEDIUM-risk rows")

    # Files
    pdf.section("10. Project Deliverables")
    pdf.table(
        ["File", "Description"],
        [
            ["resolved_chemicals.xlsx", "Pass 1 output"],
            ["resolved_chemicals_final.xlsx", "Combined output (corrected sheets)"],
            ["resolved_structures_corrected.html", "Structure gallery (fully resolved only)"],
            ["CORRECTION_NOTES.md", "Correction log and status counts"],
            ["first_segment_validation.xlsx", "Validation risk classifications"],
            ["pass2_validation.py", "Shared validation and fallback guards"],
            ["apply_pass2_corrections.py", "Reclassification and export pipeline"],
            ["chemical_name_resolver_pass2.ipynb", "Pass 2 pipeline (CCAST run)"],
            ["validate_first_segment.py", "Validation script"],
            ["pass2_valid_breakdown.xlsx", "Valid Pass 2 strategy x risk tier breakdown"],
            ["breakdown_pass2_valid.py", "Generates pass2_valid_breakdown.xlsx"],
            ["Chemical_Name_Resolution_Report.pdf", "This report"],
        ],
        col_widths=[75, 105],
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.body(f"Data loaded from: {stats['data_source']}")

    # ==================================================================
    # APPENDIX SECTIONS (additions - original sections 1-10 preserved above)
    # ==================================================================

    pdf.add_page()
    pdf.section("11. Honest Assessment: What Went Wrong From the Beginning")
    pdf.body(
        "This section provides full context for readers who need to understand both the "
        "value and the limitations of this dataset. The pipeline was built and run "
        "successfully, but it was not a validated chemical curation project from the start."
    )
    pdf.subsection("The original plan")
    pdf.bullet(
        "Pass 1: Look up each historical name directly in PubChem and CIRpy."
    )
    pdf.bullet(
        "Pass 2: For failures, generate smarter name variants (acid-ester flip, archaic "
        "terms, prefix cleanup, comma handling) and retry."
    )
    pdf.bullet(
        "Export SMILES and structure galleries for downstream cheminformatics."
    )
    pdf.subsection("What went wrong")
    pdf.bullet(
        "No validation layer was built into Pass 1. A SMILES returned by CIRpy was "
        "accepted as correct without cross-checking against the full original name."
    )
    pdf.bullet(
        "Pass 2 included aggressive fallback strategies (first_segment, first_word) that "
        "truncate derivative names to parent compounds. Example: 'Acetic acid, bornyl ester' "
        "was resolved as 'Acetic acid' - a valid structure, but the wrong molecule."
    )
    pdf.bullet(
        "These fallbacks rescued 724 of 1,163 Pass 2 hits (62%). Nearly all HIGH-risk "
        "cases (526) were parent-compound mismatches, not genuine rescues."
    )
    pdf.bullet(
        "The Pass 2 notebook described fuzzy PubChem search, but the code only performed "
        "exact name lookups. This feature was never implemented."
    )
    pdf.bullet(
        "Initial reporting claimed 5,177 resolved structures (73.0%). That number "
        "overstated true success because false-positive Pass 2 rescues were counted as fully resolved."
    )
    pdf.subsection("What we did to fix it")
    pdf.bullet(
        "Ran heuristic validation on first_segment and first_word rescues using pattern "
        "rules (acid+ester, acid+salt, derivative comma suffix, carbonate, etc.)."
    )
    pdf.bullet(
        f"Reclassified {stats['partial_match']} HIGH-risk rows as PARTIAL_MATCH - kept for "
        "audit but excluded from All_Resolved and the structure HTML gallery."
    )
    pdf.bullet(
        "Updated generate_smart_variants() to suppress root fallbacks on derivative names "
        "in future runs."
    )
    pdf.bullet(
        "Re-exported corrected Excel, regenerated HTML, and produced this expanded report."
    )
    pdf.body(
        "Important: These corrections address one class of known error. They do not constitute "
        "full chemical validation of every remaining structure."
    )

    pdf.section("12. Is Pass 1 Validated?")
    pdf.table(
        ["Aspect", "Status"],
        [
            ["Pipeline ran on all resolvable names", "Yes"],
            ["SMILES obtained (4,014 via CIRpy)", "Yes"],
            ["PubChem hits in Pass 1", "0"],
            ["Independent correctness verification", "No"],
            ["Manual or expert chemical review", "No"],
            ["False-positive analysis performed", "No"],
        ],
        col_widths=[110, 70],
    )
    pdf.body(
        "Pass 1 is operationally complete but scientifically unvalidated. Direct lookups "
        "are more trustworthy than Pass 2 fallbacks, but we still assume the database returned "
        "the correct compound for archaic 1947 names, with no check for synonym collisions, "
        "wrong isomers, or salt-vs-acid confusion."
    )

    pdf.section("13. Is Pass 2 Validated?")
    pdf.body(
        f"Pass 2 originally rescued 1,163 names. After correction, {stats['pass2']} remain "
        f"fully resolved and {stats['partial_match']} are PARTIAL_MATCH. Pass 2 is NOT fully "
        "validated - only one category of obvious error was filtered."
    )
    pdf.table(
        ["Pass 2 subgroup", "Count", "Validated?"],
        [
            ["first_segment / first_word - HIGH (demoted)", str(stats["partial_match"]), "Yes - flagged and removed"],
            ["first_segment / first_word - MEDIUM (still valid)", str(stats["p2_medium_valid"]), "Heuristic only - uncertain"],
            ["first_segment / first_word - LOW (still valid)", str(stats["p2_low_valid"]), "Heuristic only - not chemically verified"],
            ["Other strategies (acid_ester_flip, prefix_norm, etc.)", str(stats["p2_na"]), "Not risk-scored at all"],
            ["Total valid Pass 2 remaining", str(stats["pass2"]), "Partially checked only"],
        ],
        col_widths=[85, 30, 65],
    )
    pdf.body(
        "Of the 637 valid Pass 2 rescues, only 198 (31.1%) were scored by heuristics at all. "
        f"The other 439 ({stats['p2_na']/stats['pass2']*100:.1f}% of valid Pass 2) use strategies "
        "such as acid_ester_flip and prefix normalization that were never independently verified row by row."
    )

    pdf.section("14. Valid Pass 2 Breakdown: Strategy x Risk Tier")
    pdf.body(
        f"The table below describes all {stats['pass2']} rows in the Pass2_Rescued sheet. "
        "N/A means the strategy was not run through root-fallback risk rules. "
        "MEDIUM and LOW apply only to first_segment and first_word rows still counted as valid."
    )
    pdf.table(
        ["Risk tier", "Count", "% of valid Pass 2"],
        [
            ["N/A (other strategies, unreviewed)", str(stats["p2_na"]),
             f"{stats['p2_na']/stats['pass2']*100:.1f}%"],
            ["MEDIUM (uncertain, still valid)", str(stats["p2_medium_valid"]),
             f"{stats['p2_medium_valid']/stats['pass2']*100:.1f}%"],
            ["LOW (heuristic OK, still valid)", str(stats["p2_low_valid"]),
             f"{stats['p2_low_valid']/stats['pass2']*100:.1f}%"],
            ["HIGH (in valid set)", "0", "0% - all demoted to PARTIAL_MATCH"],
            ["Total", str(stats["pass2"]), "100%"],
        ],
        col_widths=[85, 35, 60],
    )
    pdf.subsection("Strategy x risk tier crosstab")
    pdf.table(
        ["Strategy", "MEDIUM", "LOW", "N/A", "Total"],
        stats["crosstab_rows"],
        col_widths=[72, 22, 22, 22, 22],
    )

    pdf.section("15. What Is Right vs What Is Wrong")
    pdf.subsection("What is right (strengths)")
    pdf.bullet(
        "The two-pass architecture (direct lookup, then smart retry) is a sound approach "
        "for historical chemical names."
    )
    pdf.bullet(
        "Pass 1 direct CIRpy lookups (4,014) are reasonable first-pass results for a dataset "
        "of this age and nomenclature."
    )
    pdf.bullet(
        "Pass 2 strategies like acid_ester_flip and prefix normalization address real naming "
        "patterns in the 1947 dataset."
    )
    pdf.bullet(
        "The correction workflow identified and removed 526 known parent-compound false positives."
    )
    pdf.bullet(
        "PARTIAL_MATCH status preserves audit trail without polluting the resolved structure set."
    )
    pdf.bullet(
        "Disk caching, CCAST batch execution, and reproducible export scripts are solid engineering."
    )
    pdf.subsection("What is wrong (limitations)")
    pdf.bullet(
        "The initial 73.0% success rate was misleading; true fully-validated success is lower."
    )
    pdf.bullet(
        f"{stats['p2_medium_valid']} MEDIUM-risk fallback rescues remain in the resolved set "
        "and are likely wrong in many cases (e.g. resolving 'Benzaldehyde ... acetal' as Benzaldehyde)."
    )
    pdf.bullet(
        f"{stats['p2_na']} Pass 2 rescues using other strategies have never been checked "
        "for name-structure consistency."
    )
    pdf.bullet(
        "No automated check verifies that a SMILES contains functional groups implied by the "
        "name (ester linkage, salt, etc.)."
    )
    pdf.bullet(
        "1,626 names still have no structure; 286 IRREGULAR names were skipped entirely."
    )
    pdf.bullet(
        "Fuzzy PubChem search described in the notebook was never implemented."
    )

    pdf.subsection("Examples still marked valid but suspicious")
    pdf.body("MEDIUM-risk (truncated to parent compound):")
    for orig, resolved in stats["medium_samples"]:
        pdf.bullet(f"{orig} -> {resolved}")
    pdf.body("LOW-risk (heuristic passed, may still be incorrect):")
    for orig, resolved in stats["low_samples"]:
        pdf.bullet(f"{orig} -> {resolved}")

    pdf.section("16. Confidence Tiers for Honest Reporting")
    pdf.body(
        "For publication or downstream modeling, report these tiers separately rather than "
        "a single resolved percentage."
    )
    pdf.table(
        ["Tier", "Definition", "Count", "% of 7,089"],
        [
            ["A - Confident", "Pass 1 direct + Pass 2 non-fallback strategies",
             str(stats["tier_a"]), f"{stats['tier_a']/stats['total']*100:.1f}%"],
            ["B - Uncertain", "Pass 2 first_segment/first_word still valid (LOW+MEDIUM)",
             str(stats["tier_b"]), f"{stats['tier_b']/stats['total']*100:.1f}%"],
            ["C - Rejected", "PARTIAL_MATCH (known parent-compound mismatch)",
             str(stats["tier_c"]), f"{stats['tier_c']/stats['total']*100:.1f}%"],
            ["D - Failed", "No SMILES after both passes",
             str(stats["tier_d"]), f"{stats['tier_d']/stats['total']*100:.1f}%"],
            ["(skipped)", "IRREGULAR - not attempted",
             str(stats["irregular"]), f"{stats['irregular']/stats['total']*100:.1f}%"],
        ],
        col_widths=[28, 72, 28, 32],
    )
    pdf.subsection("Resolution rate scenarios")
    pdf.table(
        ["Scenario", "Count", "Rate"],
        [
            ["Nominal (before any correction)", str(stats["nominal_resolved"]),
             f"{stats['nominal_pct']:.1f}%"],
            ["Current corrected (HIGH removed)", str(stats["fully_resolved"]),
             f"{stats['fully_resolved_pct']:.1f}%"],
            ["Conservative (also remove MEDIUM fallback)",
             str(stats["conservative_resolved"]), f"{stats['conservative_pct']:.1f}%"],
            ["Tier A only (most defensible)", str(stats["tier_a"]),
             f"{stats['tier_a']/stats['total']*100:.1f}%"],
        ],
        col_widths=[75, 35, 40],
    )
    pdf.body(
        f"The current headline figure of {stats['fully_resolved']} fully resolved ({stats['fully_resolved_pct']:.1f}%) "
        f"is an optimistic upper bound. The most defensible single number for confirmed structures "
        f"is Tier A at {stats['tier_a']} ({stats['tier_a']/stats['total']*100:.1f}%), though even "
        "Tier A lacks row-by-row chemical verification."
    )

    pdf.section("17. Recommended Next Steps")
    pdf.subsection("Immediate (local, no new API runs)")
    pdf.bullet(
        "Demote MEDIUM-risk first_segment / first_word rows to PARTIAL_MATCH (~112 more), "
        f"reducing fully resolved to ~{stats['conservative_resolved']} ({stats['conservative_pct']:.1f}%)."
    )
    pdf.bullet(
        "Review LOW-risk fallback rows; many may still resolve parent compounds."
    )
    pdf.bullet(
        "Use pass2_valid_breakdown.xlsx for per-row Risk_Tier and Risk_Reason review."
    )
    pdf.subsection("Automated validation layers")
    pdf.bullet(
        "Name-structure consistency scoring: does the resolved name resemble the original?"
    )
    pdf.bullet(
        "Derivative-aware rules: if the name contains 'ester', does the SMILES contain an ester linkage?"
    )
    pdf.bullet(
        "PubChem CID cross-check: compare CIRpy SMILES against PubChem for the same name."
    )
    pdf.bullet(
        "InChIKey deduplication: flag when many different names map to identical structures."
    )
    pdf.subsection("Pass 3 for remaining failures (1,626 names)")
    pdf.bullet("OPSIN parser for systematic and IUPAC-like names.")
    pdf.bullet("PubChem fuzzy / similarity search (as originally planned in the notebook).")
    pdf.bullet("Expanded archaic term and typo correction dictionary.")
    pdf.bullet("Dedicated salt, mixture, and condensate handling rules.")
    pdf.subsection("Gold-standard calibration")
    pdf.bullet(
        "Stratified manual review: sample 50 Pass 1 hits, 50 acid_ester_flip rescues, "
        "50 fallback rescues, and 50 PARTIAL_MATCH rows."
    )
    pdf.bullet(
        "Use expert review results to tune heuristics and estimate true error rate."
    )
    pdf.subsection("Bottom line")
    pdf.body(
        "The Pass 1 + Pass 2 pipeline RAN successfully and produced a useful working draft "
        "structure library. It is NOT fully validated. The dataset is suitable for exploratory "
        "cheminformatics if Tier A/B/C/D statuses are respected. Do not treat all 4,651 "
        "SMILES as confirmed correct structures for the named 1947 compounds without "
        "additional quality control."
    )

    # ------------------------------------------------------------------
    # Section 18: Pass 3 SMARTS codes (separate glossary - reader reference)
    # ------------------------------------------------------------------
    pdf.add_page()
    pdf.section("18. Pass 3 SMARTS Validation Codes (Reference)")
    pdf.body(
        "Pass 3 Layer A (pass3_local_validation.py) runs RDKit SMARTS checks on every "
        "fully resolved row (RESOLVED_PASS1 and RESOLVED_PASS2, 4,651 names). "
        "This is NOT the same as Pass 1/2 database lookup success or failure. "
        "It asks: given words in the 1947 name, does the SMILES contain the expected "
        "functional groups?"
    )

    if stats.get("p3_ran"):
        pdf.subsection("Latest Pass 3 SMARTS counts")
        pdf.table(
            ["Pass3_SMARTS_Result", "Count", "Pass3_Status assigned"],
            [
                ["PASS", str(stats["p3_pass"]), "VALIDATED_OK"],
                ["SKIP (no rule)", str(stats["p3_skip"]), "VALIDATED_OK (see below)"],
                ["FAIL", str(stats["p3_fail"]), "NEEDS_REVIEW"],
                ["Total VALIDATED_OK", str(stats["p3_validated"]), ""],
                ["Total NEEDS_REVIEW", str(stats["p3_review"]), ""],
            ],
            col_widths=[45, 30, 105],
        )

    pdf.subsection("PASS - pattern match")
    pdf.body(
        "The name contains a detectable chemical cue (e.g. ester, acid, amine) AND the "
        "SMILES contains the matching RDKit SMARTS substructure. Example: name includes "
        "'acetate' and SMILES contains an ester linkage. Assigned Pass3_Status = VALIDATED_OK. "
        "This is automated consistency checking, not expert confirmation."
    )

    pdf.subsection("SKIP (no rule) - NOT validated, but not failed")
    pdf.body(
        "IMPORTANT: SKIP does NOT mean the structure was chemically validated. It means "
        "the automated rules found no strong functional-group keyword in the name to test. "
        "Example: simple names like 'Morpholine' or 'Camphor' with no ester/acid/amine cue "
        "in our rule set. The script cannot check what it cannot phrase as a SMARTS rule, "
        "so it assigns Pass3_Status = VALIDATED_OK by default (optimistic pass-through). "
        "These 2,170 rows are UNCHECKED by SMARTS, not proven correct. They still need "
        "CCAST STOUT review or manual curation for high-confidence work."
    )

    pdf.subsection("FAIL - SMARTS mismatch (what failed?)")
    pdf.body(
        "FAIL does NOT mean the database lookup failed again. The compound already had a "
        "SMILES from Pass 1 or Pass 2. FAIL means: the name text and the structure disagree "
        "at the functional-group level. Example: name says '... diester' or '... acetate' "
        "but the SMILES has no ester bond; or name says '... acid' but SMILES has no "
        "carboxylic acid group. Assigned Pass3_Status = NEEDS_REVIEW. These are likely "
        "wrong-compound assignments and should be reviewed in the Streamlit curation app."
    )

    pdf.subsection("PARSE_ERROR")
    pdf.body(
        "RDKit could not parse the SMILES string, or SMILES was missing. Also assigned "
        "NEEDS_REVIEW."
    )

    pdf.subsection("Where ChemSpider and CCAST fit")
    pdf.bullet(
        "OPSIN + ChemSpider rescue: runs on LOCAL PC only (pass3_local_validation.py) for "
        "FAILED_BOTH_PASSES rows. ChemSpider uses API key from local .env file."
    )
    pdf.bullet(
        "CCAST GPU notebook: STOUT reverse naming only. Upload dataset_ready_for_ccast.xlsx. "
        "No ChemSpider API key needed on CCAST."
    )
    pdf.bullet(
        "SKIP rows are why CCAST STOUT + manual curation remain necessary: absence of a "
        "SMARTS rule is not proof of correctness."
    )

    pdf.output(str(OUT_PDF))
    return OUT_PDF


def main():
    if not FINAL_TEMP.exists() and FINAL_LOCAL.exists():
        try:
            import shutil
            shutil.copy2(FINAL_LOCAL, FINAL_TEMP)
        except PermissionError:
            print("Warning: Excel file locked; using cached temp copy if available.", file=sys.stderr)

    stats = gather_stats()
    out = build_report(stats)
    print(f"PDF report written to: {out}")
    print(f"  Fully resolved:     {stats['fully_resolved']} ({stats['fully_resolved_pct']:.1f}%)")
    print(f"  PARTIAL_MATCH:      {stats['partial_match']}")


if __name__ == "__main__":
    main()
