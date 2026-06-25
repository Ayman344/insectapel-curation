# Project Structure & Reorganization Notes

**Repo:** `Decoding_Names` (also the live Streamlit deployment repo for the curation app)
**Reorg commit:** `a54a4ab` — *"Organize project: group legacy 1947 pipeline, reports, and data/outputs into folders"*
**Date:** 2026-06-25

---

## 1. What the reorg did and why

The root folder had ~55 loose files mixing four unrelated concerns (the live curation app, the old 1947 Pass 1/2/3 pipeline, PDF report generators, and data/output artifacts). They were grouped into folders so the root stays clean.

**Constraints that shaped the layout:**

- **The live Streamlit curation app must keep working.** `pass3_curation_app.py` loads its data via `ROOT = Path(__file__).parent`, so the app, its helper modules, and the files it reads (`dataset_from_ccast.xlsx`, `dataset_ready_for_ccast.xlsx`, `curation_progress.csv`, `Curation_Reviewer_Guide.pdf`) **stay at the repo root**. Moving them would break the deployment.
- **Standard repo/config files stay at root** (`.gitignore`, `.env*`, `.python-version`, `requirements.txt`, `packages.txt`, `README.md`, `LICENSE`).
- **Large regenerable HTML structure renders (~160 MB) are gitignored**, not committed, to avoid permanently bloating a public deployment repo. They remain on disk locally.
- **Legacy 1947 scripts were archived as-is.** They read data by bare filename, so now that data moved into `Data & Outputs/`, those scripts' relative paths are stale. They are superseded by `Modified Resolver/` and kept for reference only — not re-run.

**Top-level result:**

```
Decoding_Names/
├── Modified Resolver/          active rebuild (validator-gated resolver + CCAST)
├── 1954 Dataset Processing/    1954 dataset work
├── 1947 Pipeline/              legacy Pass 1/2/3 code (archival)
├── Reports/                    PDF generators + generated PDFs
├── Data & Outputs/             datasets, results, caches
├── <live curation app files>   stay at root (deployment requirement)
└── <repo/config files>         stay at root
```

> **Git tracking note:** Items marked *gitignored* below exist on disk but are intentionally **not** committed (see `.gitignore`). Everything else was committed in `a54a4ab`.

---

## 2. Root — live curation app (must stay at root)

| File | What it does | Why it exists |
|------|--------------|---------------|
| `pass3_curation_app.py` | Streamlit app for human review of Pass 3 flagged rows; loads `dataset_from_ccast.xlsx`, lets reviewers approve/correct, exports `dataset_curated_final.xlsx`. Deployed at the Streamlit Cloud app. | The interactive curation UI; entry point of the deployment. |
| `curation_glossary.py` | Shared glossary (title/short/long entries) and review-queue definitions used by both the app and the reviewer PDF. | Single source of truth for plain-language explanations. |
| `curation_logic.py` | Queue masks and `CCAST_APPROVED` tier logic (e.g. SMARTS PASS + CCAST OK + Jaro-Winkler ≥ 0.55). | Decides which rows land in which review queue. |
| `curation_github.py` | Loads/saves `curation_progress.csv` via the GitHub API (or local file) so multiple reviewers' progress syncs. | Multi-reviewer persistence for the cloud app. |
| `curation_progress.csv` | Per-row review progress (who/when/action/notes). | App state; read/written by `curation_github.py`. |
| `Curation_Reviewer_Guide.pdf` | Generated reviewer handbook (from `Reports/generate_curation_guide_pdf.py`). Offered as a download in the app. | Onboarding doc for non-technical reviewers. (Explicitly un-ignored in `.gitignore`.) |
| `dataset_from_ccast.xlsx` | Pass 3 output from CCAST; the app's primary input. | App data; must be at root for cloud deploy. |
| `dataset_ready_for_ccast.xlsx` | Pre-CCAST dataset (app fallback input). | App data / pipeline handoff. |

## 3. Root — repo & config files (must stay at root)

| File | What it does |
|------|--------------|
| `.gitignore` | Ignore rules. Now also ignores `resolved_structures*.html` (large renders) plus caches/PDFs/env. |
| `.env` / `.env.example` | Secrets (e.g. ChemSpider API key) and a template. `.env` is gitignored. |
| `.python-version` | Pins Python version for Streamlit Cloud. |
| `requirements.txt` | Python deps for the deployed app (read from repo root by Streamlit Cloud). |
| `packages.txt` | System packages for Streamlit Cloud (e.g. `libxrender` for RDKit). |
| `README.md` | Repo readme. |
| `LICENSE` | License. |
| `PROJECT_STRUCTURE.md` | **This file** — the reorg + file reference. |

---

## 4. `Modified Resolver/` — active rebuild

The current, validator-gated resolver that fixes silent false positives in the old pipeline and supports the 1947/1954/1967 USDA datasets. Runs on the CCAST HPC cluster.

| Path | What it does | Why it exists |
|------|--------------|---------------|
| `chemresolve/__init__.py` | Package init for the resolver library. | Makes `chemresolve` importable. |
| `chemresolve/io.py` | Loads CSVs, profiles datasets, builds the tidy long observation table. | Data ingestion. |
| `chemresolve/normalize.py` | Conservative normalization keys + unique-name worklist. | De-duplicates names before resolving. |
| `chemresolve/variants.py` | Generates name variants/spelling alternates to retry. | Improves hit rate. |
| `chemresolve/resolvers.py` | Core resolution via PubChem, OPSIN, CIRpy, gated by validation + caching. | The heart of the resolver. |
| `chemresolve/claims.py` | Extracts chemical "claims" from a name (functional groups etc.). | Feeds the validator. |
| `chemresolve/validate.py` | Validator that confirms a returned structure matches the name's claims (the false-positive guard). | Model-grade precision. |
| `chemresolve/cache.py` | Persistent JSON cache for API calls + outcomes. | Resumable, fewer API hits. |
| `scripts/run_resolve.py` | Full, checkpointed, year-filterable resolution run. | Production runs per dataset year. |
| `scripts/smoke_resolve.py` | Small N-name smoke test of the pipeline. | Quick sanity check (used for the 5/20-name CCAST tests). |
| `scripts/smoke_package.py` | Verifies the package imports/installs correctly. | Environment check. |
| `scripts/ccast.ps1` | Windows PowerShell helper to submit/monitor/sync CCAST jobs over SSH (Slurm `sbatch`/`squeue`, sets `SLURM_CONF`, fixes CRLF + read-only perms after upload). | Unattended job submission from the PC. |
| `jobs/resolve_1947.slurm` | Slurm batch script for the full 1947 run (account `x-ccast-prj-hpirim`, partition `compute`, email + ntfy notify). | The real CCAST submission (job `13600`). |
| `jobs/resolve_1947.pbs` | Old PBS version of the 1947 job. | Deprecated — CCAST Thunder uses Slurm, not PBS. Kept for history. |
| `jobs/smoke_resolve.pbs` | PBS smoke-test script. | Deprecated alongside `.pbs` above. |
| `Pipline-chemical_name_resolver-all_datasets.ipynb` | Notebook driving resolution across all datasets. | Interactive/dev pipeline. |
| `pass1_v4_reaction_aware.ipynb` | Reaction-aware Pass 1 experiment notebook. | R&D. |
| `generate_rebuild_report_pdf.py` | Builds the journal-style PDF explaining the rebuild rationale + mechanics + CCAST smoke tests. | Teammate/supervisor communication. |
| `generate_ccast_runbook_pdf.py` | Builds the CCAST job-submission runbook PDF (errors, fixes, flowcharts). | Self-service ops guide. |
| `requirements.txt` | Deps for the resolver package on CCAST. | Reproducible install. |
| `AGENT_CONTEXT.md` | High-level project background + locked decisions. | Onboarding/context. |
| `PLAN.md` | Phase tracker, decision log, CCAST environment facts. | Project plan of record. |
| `1947-King-USDA_Dataset.csv` | 1947 USDA input (~7,086 names). | Input dataset. |
| `1954-King_dataset.csv` | 1954 USDA input. | Input dataset. |
| `1967_USDA_datasetcsv.csv` | 1967 USDA input. | Input dataset. |
| `.gitignore` | Nested ignore rules for the package (outputs, temp files). | Keeps run artifacts out of git. |
| `py2opsin_temp_input.txt` | *(gitignored)* OPSIN temp scratch file. | Transient; regenerated at runtime. |

---

## 5. `1954 Dataset Processing/` — 1954 dataset work

| File | What it does |
|------|--------------|
| `1954 chemical_name_resolver.ipynb` | Notebook resolving the 1954 dataset names to structures. |
| `1954-King_dataset.csv` | 1954 input dataset. |
| `resolved_1954-King_dataset.xlsx` | Resolved output for 1954. |
| `resolved_structures_1954-King_dataset.html` | *(gitignored)* Structure-image gallery for 1954 (large, regenerable). |

---

## 6. `1947 Pipeline/` — legacy Pass 1/2/3 (archival)

Superseded by `Modified Resolver/`. Kept for reference. Relative data paths are stale after the reorg.

| File | What it does | Why it exists |
|------|--------------|---------------|
| `chemical_name_resolver.ipynb` / `.py` | **Pass 1**: classify names (regular/semi/irregular), resolve via PubChem/CIRpy, generate structures, export. | Original resolver. |
| `chemical_name_resolver_pass2.ipynb` / `.py` | **Pass 2 (smart retry)**: acid↔ester flips, archaic-term dictionary, prefix cleanup, partial-root + fuzzy search on Pass 1 failures, cached/resumable. | Rescue failed names. |
| `pass2_validation.py` | Shared Pass 2 regex patterns + root-fallback risk guards. | Imported by several Pass 2/3 scripts. |
| `validate_first_segment.py` | Flags risky `first_segment` rescues as likely false positives → `first_segment_validation.xlsx`. | QA of Pass 2 rescues. |
| `apply_pass2_corrections.py` | Reclassifies high-risk rescues to PARTIAL_MATCH, re-exports `resolved_chemicals_final.xlsx`, regenerates HTML + PDF. | Apply QA corrections. |
| `breakdown_pass2_valid.py` | Breaks down valid Pass 2 rescues by strategy × risk tier → `pass2_valid_breakdown.xlsx`. | Reporting. |
| `pass3_smarts_rules.py` | RDKit SMARTS heuristics: does a SMILES plausibly match the name's cues? | Pass 3 structure validation. |
| `pass3_local_validation.py` | **Pass 3 (local)**: SMARTS-validate resolved rows; OPSIN + ChemSpider rescue of failures; export `dataset_ready_for_ccast.xlsx`. | Pre-CCAST validation. |
| `pass3_ccast_validation.ipynb` / `.py` | **Pass 3 (CCAST)**: SMILES→IUPAC (chemical-converters) + Jaro-Winkler scoring on the GPU cluster → `dataset_from_ccast.xlsx`. | Reverse-naming check on HPC. |
| `analyze_ccast_output.py` | Analyzes `dataset_from_ccast.xlsx` (diffs name vs. reverse-named). | Post-CCAST analysis. |
| `structure_html.py` | Renders HTML structure galleries from resolved SMILES. | Visual QA output. |
| `CORRECTION_NOTES.md` | Notes from the Pass 2 correction pass. | Audit trail. |
| `README_PASS3.md` | Step-by-step Pass 3 instructions (local → CCAST → curation app). | Pipeline docs. |

---

## 7. `Reports/` — PDF generators + outputs

| File | What it does | Tracked? |
|------|--------------|----------|
| `generate_pdf_report.py` | Builds the chemical-name-resolution findings report (reads resolved workbooks). | committed |
| `generate_pass3_plan_pdf.py` | Builds `PASS3_Pipeline_Plan.pdf` (plan-for-approval). | committed |
| `generate_pass3_progress_pdf.py` | Builds `PASS3_Progress_Report.pdf` (progress + next steps; reads `dataset_from_ccast.xlsx`, `ccast_checkpoint.csv`). | committed |
| `generate_curation_guide_pdf.py` | Builds `Curation_Reviewer_Guide.pdf` from the shared glossary. | committed |
| `Chemical_Name_Resolution_Report.pdf` | Generated findings report. | *(gitignored — `*.pdf`)* |
| `PASS3_Pipeline_Plan.pdf` | Generated plan PDF. | *(gitignored — `*.pdf`)* |
| `PASS3_Progress_Report.pdf` | Generated progress PDF. | *(gitignored — `*.pdf`)* |

> Note: generators in this folder reference data files by name; after the reorg they expect data that now lives in `Data & Outputs/` or at root. Update their paths before re-running.

---

## 8. `Data & Outputs/` — datasets, results, caches

| File | What it does | Tracked? |
|------|--------------|----------|
| `1947-King-USDA_Dataset.csv` | 1947 USDA source dataset (legacy copy). | committed |
| `resolved_chemicals.xlsx` | Pass 1 resolved output. | committed |
| `resolved_chemicals_final.xlsx` | Pass 1+2 corrected final workbook. | committed |
| `first_segment_validation.xlsx` | First-segment rescue QA output. | committed |
| `pass2_valid_breakdown.xlsx` | Pass 2 rescue strategy × risk breakdown. | committed |
| `resolved_structures.html`, `resolved_structures1.html`, `resolved_structures_corrected.html`, `resolved_structures_pass1+pass2.html` | Structure-image galleries (4 large files). | *(gitignored — `resolved_structures*.html`)* |
| `ccast_checkpoint.csv` | CCAST run checkpoint. | *(gitignored)* |
| `pass3_opsin_cache.json`, `pass3_chemspider_cache.json` | Cached OPSIN / ChemSpider lookups. | *(gitignored)* |

---

## 9. Deleted in the reorg

| Item | Why removed |
|------|-------------|
| `__pycache__/` | Regenerable Python bytecode. |
| `Modified Resolver.zip` | Redundant — the unzipped `Modified Resolver/` folder is the source of truth. |
