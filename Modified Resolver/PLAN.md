# PLAN — Chemical Name Resolution Rebuild

> Living document. Update it when a cell's output changes our approach. **Every phase is
> approval-gated: the user approves before work proceeds, and nothing is committed to GitHub without
> explicit approval.** Read `AGENT_CONTEXT.md` first for the full background and locked decisions.

**Status legend:** ✅ done · 🔄 in progress · ⏭️ next (awaiting approval) · ⏸️ blocked · 🅿️ deferred

**Last updated:** 2026-06-17 (agent review of folder + legacy `Decoding_Names` pipeline)

---

## Phase tracker

| # | Phase | Module / artifact | Status |
|---|-------|-------------------|--------|
| 0 | Schema discovery — profile the three CSVs (no API calls) | `io.py` | ✅ (notebook cell; CCAST-verified) |
| 1 | Build tidy long observation table (traits year-namespaced, raw preserved) | `io.py` | ✅ |
| 2 | Conservative normalization key + unique-name worklist | `normalize.py` | ✅ |
| 3 | Claim parser (name → ClaimSet; precision over recall) | `claims.py` | ✅ |
| 4 | Validator (name + SMILES → Verdict; regression battery green) | `validate.py` | ✅ |
| **4b** | **Extract Phases 0–4 from notebook → `chemresolve/` package on disk** | `chemresolve/*.py` | ✅ |
| 5 | Resolvers: PubChem + OPSIN + CIRpy, each hit gated by `validate()`; variant generator + OCR repair; persistent cache | `resolvers.py`, `cache.py`, `variants.py` | ✅ |
| 5a | Smoke test: 50–100 diverse names from worklist; log VERIFIED / UNVERIFIED / REJECT reasons | `scripts/smoke_resolve.py` | ✅ (local 8/12; **CCAST 20-name: 15 resolved / 1 quarantine / 4 failed; all 3 resolvers live**) |
| 6 | Run resolution per-year as PBS batch on CCAST (checkpointed, resumable). **1947 first (7,086 names) for manual verification, then 1954/1967.** | `scripts/run_resolve.py`, `jobs/resolve_1947.pbs` | 🔄 1947 ready to submit |
| 7 | Consolidate across years on InChIKey; attach traits side-by-side; keep provenance | `consolidate.py` | ⏸️ |
| 8 | Confidence tiers: connectivity + element + FG + cross-resolver agreement + OPSIN round-trip | `tiers.py` | ⏸️ |
| 9 | Extend Streamlit curation app (tier/evidence, multi-reviewer, GitHub sync) | `../pass3_curation_app.py` | 🔄 partial (1947 app exists) |
| 10 | Final model-grade export (SMILES + InChIKey + tier + evidence + provenance) | `outputs/` | ⏸️ |

---

## Where we are right now

Phases **0–4 are complete**. Code now lives in **`chemresolve/`** on disk (not only in notebook cells).

**Smoke test (local or CCAST):**
```bash
cd "Modified Resolver"
python scripts/smoke_package.py
# or individually:
python -m chemresolve.claims
python -m chemresolve.validate
```

**Immediate next step (awaiting approval):** Phase **6** — `run_resolve.py` + PBS batch script, after OPSIN/CIRpy probe on CCAST.

**Phase 5 smoke (local, PubChem only):** 7/12 resolved; mercaptal / obscure esters need CIRpy or OPSIN.

---

## Notebook inventory (open question #4 — resolved)

| File | Role | Recommendation |
|------|------|----------------|
| **`Pipline-chemical_name_resolver-all_datasets.ipynb`** | **Production path.** All three datasets; Phases 0–4; PubChem connectivity test; builds observation table + worklist; `claims` + `validate` modules with regression tests. | **Keep as the dev driver.** Thin it after 4b (import `chemresolve`, don't duplicate logic). |
| **`pass1_v4_reaction_aware.ipynb`** | **Experimental / legacy branch.** 1947-only; inline PubChem+CIRpy; reaction routing (`REACTION` ~51% of rows); RDKit reaction templates; **no `validate()` gate**; had runtime errors in `_resolve_reaction`. | **Do not run as production.** Archive for ideas only (ester flip, mercaptal parsing, OCR fixes). Salvage useful *variant patterns* into Phase 5's generator — not the reaction-synthesis path without validation. |

**Do not run both notebooks on the same dataset** — they represent different architectures.

---

## Relationship to legacy `Decoding_Names/` pipeline (1947 only)

The sibling folder `../Decoding_Names/` contains the **old** Pass 1 / 2 / 3 work on **1947 only**
(~7,089 rows). Key facts for this rebuild:

| Legacy artifact | What it did | Rebuild stance |
|-----------------|-------------|----------------|
| `chemical_name_resolver.py` / `_pass2.py` | CIRpy-first; first-hit wins; truncating variants | **Superseded** — root cause documented in `AGENT_CONTEXT.md` |
| `pass3_smarts_rules.py` | SMARTS check; wrong `mercaptal → thiol` | **Superseded** by `validate.py` dithioacetal pattern |
| `pass3_ccast_validation.py` | SMILES→IUPAC neural reverse naming on GPU | **Dropped** per locked decision #5 |
| `pass3_curation_app.py` + GitHub `insectapel-curation` | Multi-reviewer Streamlit; `curation_progress.csv` sync | **Reuse in Phase 9** — extend for new tier/evidence columns, all three years |
| `dataset_from_ccast.xlsx` | 4,681 structures with old flags | **Historical reference only** — not input to the rebuild |

Old **1947 headline counts** (for comparison, not targets): ~65% "resolved" but with silent false
positives; ~537 SMARTS FAIL; strict **CCAST APPROVED** tier in the old app was only ~1,044 rows
(SMARTS PASS + CCAST OK + Pass 1 + JW≥0.55). The rebuild aims for **validator-gated** acceptance
from the start, so "resolved" means something stronger.

---

## Open questions / decisions pending

### Resolved (agent recommendation — confirm with user)

| # | Question | Recommendation |
|---|----------|----------------|
| 4 | Which notebook? | **`Pipline-…-all_datasets.ipynb` only** for production; `pass1_v4` = reference archive |
| 2 | PubChem rate limit | **≤5 req/s + exponential backoff + persistent JSON cache** (one file per resolver) |

### Still needs your approval before Phase 5

| # | Question | Agent recommendation |
|---|----------|---------------------|
| 1 | **OPSIN on CCAST** | Run a **one-cell probe** on login node: `pip install py2opsin`, `java -version`, resolve `"ethanol"`. If Java missing, bundle jar in `chemresolve/vendor/`. |
| 3 | **Amine-salt false REJECT** | **Defer fix** until smoke test (5a) — log all REJECT reasons; patch `validate.py` only if real amine-HCl names appear in the reject log. |
| 5 | **Phase 4b extraction** | Extract `io.py`, `normalize.py`, `claims.py`, `validate.py` from notebook → `chemresolve/` | ✅ Done 2026-06-17 |
| 6 | **Salvage from `pass1_v4`** | Port **variant helpers only** into `resolvers.py` — **not** unvalidated RDKit reaction assembly | Pending approval |

---

## Phase 5 design sketch (for approval)

```
for each norm_key in worklist (cache miss):
    for variant in generate_variants(name):   # kept Pass 2 transforms + repair_ocr_digits
        for resolver in [pubchem, opsin, cirpy]:   # order TBD; each independent
            smiles = resolver.lookup(variant)
            verdict = validate(name, smiles)
            if verdict == REJECT: continue      # try next variant / resolver
            if verdict in (VERIFIED, UNVERIFIED): record hit; break inner
    if no hit: quarantine with best rejected candidate + reasons
    if still no hit and not --skip-chemspider: chemspider rescue (capped)
```

**Outputs per name:** `SMILES`, `InChIKey`, `verdict`, `resolver`, `variant_used`, `reject_log`,
`opsin_roundtrip_ok` (Phase 8).

---

## Phase 8–9 tier sketch (replaces old VALIDATED_OK / CCAST flags)

| Tier | Criteria (draft) |
|------|------------------|
| **A — trusted** | `VERIFIED` + ≥2 resolvers agree on InChIKey + OPSIN round-trip OK |
| **B — plausible** | `VERIFIED` + single resolver, or `UNVERIFIED` + cross-resolver agreement |
| **C — weak** | `UNVERIFIED`, single resolver only |
| **D — quarantine** | All candidates `REJECT`, or conflicting InChIKeys |
| **E — human curated** | Reviewer confirmed in Streamlit (`Curation_Reviewed = Yes`) |

Phase 9 extends the existing app: show tier + evidence columns; **CCAST APPROVED** queue becomes
**Tier A browse** once the new pipeline produces tiers.

---

## Deferred (ML / feature-engineering stage)

- Meaning of `"-"` sentinel; rating scales; YF vs M; wash/space test types.
- Hand-fix one misaligned 1947 row (`Unnamed: 3`).
- Whether 1947 legacy curated rows seed a **gold review set** for inter-rater agreement.

---

## CCAST environment facts (Thunder) — discovered 2026-06-25

- **Scheduler is Slurm 24.11**, NOT PBS. (The `.pbs`/OpenPBS docs are stale for Thunder; `qsub`
  does not work — `sbatch`/`squeue`/`scancel` do.) Use `jobs/resolve_1947.slurm`.
- **Submit/monitor binaries:** `/cm/local/apps/slurm/current/bin/{sbatch,squeue,scancel}`.
- **Required for non-interactive SSH submit:** `export SLURM_CONF=/cm/shared/apps/slurm/etc/thunder-prod/slurm.conf`
  (Slurm module only auto-loads in interactive shells).
- **Account:** `x-ccast-prj-hpirim` (PI Harun Pirim). Partitions: `compute` (default, 7-day),
  `gpus`, `preemptible`. `#SBATCH` template from `/mmfs1/thunder/projects/ccastest/examples/job_submission/job.slurm`.
- **SSH login needs Duo 2FA** (each `ssh`/`scp` = one push). `qsub`/`sbatch` detaches the job, so
  submit-then-close works; ntfy push + email notify on finish.
- **Windows gotchas when uploading from PC:** (1) `scp -r` re-applies Windows read-only bit to remote
  dirs → `chmod -R u+rwX` after; (2) files arrive with CRLF → `sed -i 's/\r$//'` on `*.slurm` or Slurm
  rejects "DOS line breaks". `scripts/ccast.ps1 sync`/`go` now do both automatically.
- **First real batch:** job `13600` (1947, 7,086 names) submitted 2026-06-25.

## Decision log (most recent first)

- **2026-06-25 — Phase 5a verified on CCAST; Phase 6 started (per-year).** Installed deps on
  CCAST scratch (`/mmfs1/scratch/ayman.akash`). All three resolvers live (PubChem/OPSIN/CIRpy;
  Java 1.8 present). 20-name smoke: 15 resolved / 1 quarantine / 4 failed — mercaptal fixed,
  disconnected ester correctly quarantined, zero observed silent false positives. Added
  `scripts/run_resolve.py` (checkpointed, resumable, year-filterable) + `jobs/resolve_1947.pbs`
  (email + optional ntfy phone push). **Decision: run 1947 alone (7,086 names) first, hand-verify,
  then 1954/1967.** Added `scripts/ccast.ps1` to drive jobs from the PC over SSH. Wrote
  `generate_rebuild_report_pdf.py` (journal-style progress report for teammates/supervisor).
- **2026-06-17 — Phase 5 complete.** Added `variants.py`, `cache.py`, `resolvers.py`,
  `scripts/smoke_resolve.py`. PubChem gated by `validate()`; local smoke 7/12 resolved.
  OPSIN/CIRpy optional (`pip install py2opsin cirpy` on CCAST).
- **Folder organization + approval gating.** Repo layout in `AGENT_CONTEXT.md` §8; no GitHub
  commit without explicit approval.
- **UNVERIFIED-unless-corroborated** for no-FG-cue rows.
- **Validator (`validate.py`)** — 10/10 regression green; mercaptal + disconnected ester caught.
- **Claim parser (`claims.py`)** — precision fixes (ester suppresses phenol; salt cation guard).
- **Observation table** — 23,881 rows; ~23,270 unique `norm_key`.
- **Drop neural reverse-naming**; OPSIN round-trip + cross-resolver agreement instead.
- **CCAST has internet** → single PBS batch job viable.
- **Root cause confirmed** — string-presence validation, not structure-vs-name agreement.

---

## How to update this file

When a run changes the plan, add a dated decision-log line, adjust the phase table, and **present
the change for approval before acting**.
