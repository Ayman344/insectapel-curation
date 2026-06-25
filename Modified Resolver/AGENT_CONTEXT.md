# AGENT CONTEXT & INSTRUCTIONS — Chemical Name Resolution Rebuild

> **Read this before doing anything.** You already have context on the old Pass 1 / Pass 2 / Pass 3
> pipeline. This document captures everything decided *after* those passes — the rebuild that fixes
> their systemic flaw. A companion file, `PLAN.md`, tracks phases and open questions and is the
> document the user approves against. **Do not commit anything to GitHub without explicit approval.**

---

## 1. What this project is

We are converting historical USDA insect-repellent chemical names into modern, validated SMILES
structures. Three datasets from different years feed one unified pipeline:

| Year | File | Name column | Rows |
|------|------|-------------|------|
| 1947 | `1947-King-USDA_Dataset.csv` | `Chemical` | 7,089 |
| 1954 | `1954-King_dataset.csv` | `Chemical` | 8,201 |
| 1967 | `1967_USDA_datasetcsv.csv` | `MATERIAL` | 8,591 |

**Total occurrences:** 23,881. **Downstream use:** ML feature extraction / QSAR to predict whether a
compound is a good insect repellent (far future, not now). This sets the quality bar — see §3.

---

## 2. The core problem we are fixing

The old pipeline reported many compounds as "resolved" but produced **silent false positives** —
structures that are chemically wrong but look like successes. Two representative error families:

- **Error A — analogue / truncation.** `Acetaldehyde dioctyl mercaptal` (a dithioacetal,
  `CCCCCCCSC(C)SCCCCCCCC`) came back as `CCCCCCCOCSCCCCCCCC`, an oxygen/thio ether analog. The name's
  functional group was never verified against the returned structure.
- **Error B — disconnected mixtures.** `Acetic acid, o-allyl-p-cresol ester` came back as
  `CC(O)=O.Cc1ccc(O)c(CC=C)c1` — two disconnected fragments (acid + phenol), not the bonded ester.

**These two are only examples.** The real datasets contain many more variants of these families
(e.g. `ester with X` phrasing, mixed acetals, salts, OCR corruption like `l` for digit `1` in
`2-cyclopenten-l-one`). The fix must generalize, not special-case two names.

**Single root cause (confirmed):** resolution was validated by *"a non-empty string came back"*,
never by *"the returned structure matches the chemistry the name asserts."* Contributing bugs found
in the old code:

- The resolver returned the first variant that produced any SMILES, with **zero structural check**.
- A broad `except Exception: break` **silently swallowed every PubChem error** → all 4,014 Pass 1
  hits came from CIRpy's fuzzy NCI resolver (the analog/mixture source). PubChem never participated.
- Pass 2 fallback strategies `first_segment` / `first_word` / `split_and_*` **truncated derivative
  names to parent compounds** (e.g. `Acetic acid, bornyl ester` → `Acetic acid`).
- The old `pass3_smarts_rules.py` mapped `mercaptal → expects thiol [SX2H]`, which is **wrong
  chemistry** — a dithioacetal has C–S–C thioethers, no S–H thiol — so it false-FAILed correct
  structures and could not distinguish the right S,S-acetal from the wrong O,S analog.

The old `ARCHAIC_DICT` was *fine* (`mercaptal → dithioacetal` is correct). The dictionary was never
the bug; the missing validation layer was.

---

## 3. Locked decisions (do not relitigate without the user)

1. **Merge key is structure, not name.** Cross-year unification happens on **InChIKey after
   resolution**, never on name strings (string overlap is tiny: 558 keys in ≥2 datasets, 0 in all 3;
   1967's phrasing diverges from 1947/1954). Pre-resolution name dedup is a minor API-cost saving
   only.
2. **Tidy long observation table.** One row per (source_year, source_row_id, original_name, …traits).
   Traits are **kept separate and year-namespaced** (`y1947_…`, `y1954_…`, `y1967_…`), never merged
   or reinterpreted at load time.
3. **Merge-on-structure, traits-kept-separate.** When two years resolve to the same InChIKey, they
   become one compound with each year's traits side by side. Provenance (every raw string + year +
   row) is preserved untouched.
4. **Precision bar = model-grade, not nomenclature-grade.** Each accepted structure must be
   *connected* (unless a genuine salt/mixture), *element- and functional-group-consistent* with its
   name, and *deduped*. It does **not** need a perfect modern IUPAC name. A silently-wrong structure
   is worse than a missing one — it poisons every ML feature for that row.
5. **No CCAST GPU / neural reverse-naming.** STOUT / chemical-converters is dropped. Reverse
   validation is done with **OPSIN round-trip** + **cross-resolver InChIKey agreement** — stronger,
   deterministic, faster, no GPU/file-transfer friction.
6. **Package + thin notebooks.** Real logic lives in importable `.py` modules; notebooks only import
   and inspect. This kills the "described in the notebook but never implemented" drift.
7. **UNVERIFIED-unless-corroborated.** When a name has no functional-group cue (e.g. `Camphor`), the
   row passes connectivity, is marked `UNVERIFIED`, and waits for resolver-agreement or human review
   before being trusted. Never silently `OK`.
8. **Keep the good Pass 2 transformations, drop the truncating ones.** Keep: `acid_ester_flip` (with
   a *correct* acid-root→acylate map, not the "aceticate" bug), `archaic_sub`, `strip_parens`,
   `prefix_norm`, `comma_to_space`, `multi_ester_flip`, `of_rearrange`, `strip_stereo`. **Drop:**
   `first_segment`, `first_word`, `split_and_first`, `split_and_second`.
9. **ChemSpider = last-resort rescue only.** Tried after PubChem/OPSIN/CIRpy, every hit validated,
   cached (≤1 call per name ever), hard monthly cap, `--skip-chemspider` switch. **The API key is
   never pasted in chat and never committed** — use an environment variable / Streamlit secret and
   gitignore it.
10. **CCAST compute nodes have outbound internet** (confirmed: PubChem returned `STATUS 200, BODY
    CCO`). So the whole pipeline — resolution included — can run as **one unattended PBS batch job**.
    No need to split network vs. offline stages.

---

## 4. Data facts discovered (from the live profiling cells)

- **Name column differs:** `Chemical` (1947, 1954) vs `MATERIAL` (1967). Map per file.
- **Trait columns differ across all three** and are kept separate:
  - 1947: `Repellent_skin_YF`, `Repellent_cloth_YF`
  - 1954: `Repellency_skin_YF`, `Repellency_skin_M`, `Repellency_clothes_YF`, `Repellency_clothes_M`
  - 1967: `Repellent_cloth_YF`, `Repellent_skin_YF`, `Repellent_wash_YF`, `Repellent_space_YF`
- **Missing-value sentinels differ:** 1947 uses blank/`NaN`; 1954 and 1967 use `"-"`. Rating
  vocabulary differs too (1947 mostly `"1"`/blank; 1954 `"1"`/`"-"`; 1967 includes `"2"`). **Do not
  interpret these now** — preserve raw; meaning (untested vs. ineffective, scale, direction, "YF" vs
  "M" species, "wash"/"space" test types) is a feature-engineering question for the ML stage.
- **`Unnamed: 3` in 1947** held exactly one stray value `'1'` → one misaligned row (unquoted comma).
  Column dropped; the single row can be hand-fixed later if it matters.
- **String overlap is small** (558 keys in ≥2 datasets, 0 in all 3 by exact string). Real overlap is
  structural and appears only post-resolution on InChIKey.

---

## 5. Modules already built and tested (source of truth)

These exist as files and pass their embedded regression batteries. **Do not rewrite from memory —
read the actual files.**

### `claims.py` — the claim parser
Turns a name into a `ClaimSet` describing what chemistry the name *asserts*. It is a lightweight
**claim extractor, not a name parser** (that's the resolvers' job). Philosophy: **precision over
recall** — a false claim makes the validator reject a *correct* structure, so when ambiguous, it
stays silent.

- `extract_claims(name) -> ClaimSet(connectivity, functional_groups, elements, notes)`
  - `connectivity`: `single` (default, the universal guardrail) | `salt` | `mixture`
  - `functional_groups`: e.g. `ester`, `dithioacetal`, `acetal`, `amide`, `amine`, `nitro`,
    `alcohol`, `phenol`, `ketone`, `carboxylic_acid`, `carboxylate`
  - `elements`: presence set (`S`, `N`, `Cl`, `Br`, `F`, `I`, `P`, `Si`, `O`)
- Key precision rules baked in: an **ester suppresses free alcohol/phenol claims** (the partner OH is
  consumed); **salt cation words (`ammonium`, `sodium`, …) do not generate organic FG claims**.
- `repair_ocr_digits(name)` — a **variant helper, not a claim** (e.g. `cyclopenten-l-one` →
  `cyclopenten-1-one`). Belongs to the resolver/variant step.

### `validate.py` — the validator
Takes a name + returned SMILES → a `Verdict`. This is the load-bearing fix.

- `validate(name, smiles, claims=None) -> Verdict(status, reasons, checks)`
- Status: `VERIFIED` (an FG SMARTS confirmed) | `UNVERIFIED` (passed all applicable checks, no strong
  FG cue) | `REJECT` (hard mismatch) | `PARSE_ERROR`.
- Hard checks: **connectivity** (single-expected but >1 fragment → REJECT; salts/mixtures exempt),
  **element presence**, **functional-group SMARTS** (includes the corrected dithioacetal pattern
  `[CX4]([SX2][#6])[SX2][#6]`).
- **A `REJECT` is not data loss.** In the resolver it means "don't accept *this* structure"; keep
  trying other variants, and if all fail, quarantine the name for review with the best rejected
  candidate attached.

**Regression cases that MUST stay green** (the canary): mercaptal correct→VERIFIED / wrong
analog→REJECT; ester correct→VERIFIED / disconnected mixture→REJECT; sodium benzoate & sodium acetate
salts→VERIFIED (not falsely rejected); Camphor→UNVERIFIED.

### What this validation layer does NOT catch
Wrong isomer, wrong regiochemistry, or an analog with the *same* functional group. Those rely on
cross-resolver agreement + OPSIN round-trip + human review. This layer makes the *obvious* errors
impossible, not all errors.

---

## 6. Known soft spots / things to watch (not yet fixed)

- **Amine salts:** a name like `…amine hydrochloride` claims `amine`, but the DB may return the
  protonated form `[NH3+]…[Cl-]`, which the neutral-amine SMARTS won't match → possible false
  REJECT. Fix when it surfaces (broaden the amine pattern to include ammonium, or skip the amine FG
  check when `connectivity == salt`).
- Element/FG checks are **hard REJECT** on mismatch. This is intentional (conservative), justified by
  the claim parser being deliberately low-recall. Revisit only if real data shows over-claiming.
- The one misaligned 1947 row (`Unnamed: 3`) is unfixed and harmless for now.

---

## 7. How to work on this project (operating agreement)

1. **Cell-by-cell loop.** Write one module/cell plus a small test cell. The user runs it on CCAST and
   pastes the output. You read the *actual* output and adapt the next cell to it. **Do not presume
   results** — if confused, ask.
2. **Persist modules with `%%writefile`.** In the notebook, a cell whose first line is
   `%%writefile claims.py` (etc.) saves the body to disk so every notebook and the batch job import
   the same file. Test with `!python claims.py` (fresh process, no stale in-memory version). The
   `ALL REGRESSION TESTS PASS` line is the canary.
3. **Keep the folder clean for GitHub** (see §8). Create folders as needed. Don't leave scratch files
   scattered.
4. **NEVER commit to GitHub without explicit user approval.** Each plan step is approved in `PLAN.md`
   first. If the user has not said "approved," do not commit.
5. **For larger computations**, hand the user a ready-to-run `.ipynb` or `.py` for CCAST (they run it
   there, on a login node for dev or via PBS batch for long jobs, and paste results back). When the
   production run arrives, provide the PBS job script with a step-by-step; the user does not yet know
   `qsub` — teach, don't assume.
6. **Secrets never in chat or repo.** Environment variables / Streamlit secrets only; gitignore them.
7. **Precision over recall** in anything that can reject a structure. A wrongly-rejected correct
   structure is the failure mode we most want to avoid after silent false positives.

---

## 8. Proposed repository layout (organize toward this)

```
chemresolve-project/
├── README.md
├── AGENT_CONTEXT.md            # this file
├── PLAN.md                     # phase tracker; user approves against it
├── .gitignore                  # secrets, caches, large outputs
├── chemresolve/                # the importable package (source of truth)
│   ├── __init__.py
│   ├── io.py                   # load + profile the three CSVs
│   ├── normalize.py            # conservative norm_key + worklist
│   ├── claims.py               # DONE — claim parser
│   ├── validate.py             # DONE — structure-vs-name validator
│   ├── resolvers.py            # NEXT — PubChem + OPSIN + CIRpy, each gated by validate()
│   ├── cache.py                # persistent structure-aware cache
│   ├── consolidate.py          # InChIKey merge across years
│   └── tiers.py                # confidence tiers from aggregated signals
├── notebooks/                  # thin: import chemresolve, inspect, print
│   └── (dev notebooks; CCAST OnDemand)
├── scripts/
│   └── run_resolve.py          # single entrypoint for the unattended PBS run
├── jobs/
│   └── resolve.pbs             # PBS batch script for CCAST (provided when we reach it)
├── tests/                      # pytest; collects the __main__ batteries we already wrote
├── data/                       # raw CSVs (gitignore if large/sensitive)
├── cache/                      # API caches (gitignored)
└── outputs/                    # generated xlsx / structure library (gitignored)
```

> There are reportedly **two `.ipynb` files already in the working folder**. Inventory them first
> (`ls *.ipynb`, then summarize each), report what they are, and ask the user which to keep before
> reorganizing — do not delete or overwrite them. See the open item in `PLAN.md`.
