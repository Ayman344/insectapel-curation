"""
Pass 3 CCAST validation: SMILES -> IUPAC (chemical-converters) + Jaro-Winkler.

Run on CCAST GPU Jupyter via pass3_ccast_validation.ipynb, or:
    python pass3_ccast_validation.py
    python pass3_ccast_validation.py --resume
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Set before any torch/tokenizers import (safe if already imported).
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import pandas as pd

try:
    from jellyfish import jaro_winkler_similarity
except ImportError:
    def jaro_winkler_similarity(a: str, b: str) -> float:
        import difflib
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

ROOT = Path(__file__).parent
INPUT_XLSX = ROOT / "dataset_ready_for_ccast.xlsx"
OUTPUT_XLSX = ROOT / "dataset_from_ccast.xlsx"
CHECKPOINT_CSV = ROOT / "ccast_checkpoint.csv"
DEFAULT_THRESHOLD = 0.45
MODEL_NAME = "knowledgator/SMILES2IUPAC-canonical-small"
CHECKPOINT_EVERY = 100
DEFAULT_GPU_BATCH = 40  # fresh subprocess per batch avoids poisoned CUDA


def get_device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def cuda_is_healthy() -> tuple[bool, str]:
    """Quick probe — fails if a previous run left CUDA in a bad state."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "CUDA not available"
        torch.cuda.synchronize()
        x = torch.tensor([1.0], device="cuda:0")
        del x
        torch.cuda.empty_cache()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)[:200]


def clear_cuda() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
    except Exception:
        pass


def load_converter(force_cpu: bool = False):
    if force_cpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        print("Loading on CPU (CUDA_VISIBLE_DEVICES cleared)")

    from chemicalconverters import NamesConverter

    print(f"Loading model: {MODEL_NAME} on {get_device()}")
    try:
        return NamesConverter(model_name=MODEL_NAME)
    except RuntimeError as exc:
        err = str(exc)
        if not force_cpu and ("CUDA" in err or "cuda" in err.lower()):
            print(
                "GPU model load failed (CUDA likely poisoned from an earlier crash).\n"
                "  1. Kernel -> Restart Kernel\n"
                "  2. Run All from the top (do NOT re-run old inline cells)\n"
                "  3. If it still fails, set USE_CPU = True in the notebook"
            )
            raise
        raise


def parse_iupac_output(out) -> str:
    if not out:
        return ""
    if isinstance(out, (list, tuple)):
        return str(out[0]).strip() if out else ""
    return str(out).strip()


def _is_cuda_error(msg: str) -> bool:
    m = msg.lower()
    return "cuda" in m or "indexselect" in m or "device-side assert" in m


def safe_smiles_to_iupac(converter, smiles: str) -> tuple[str, str, bool]:
    """Return (iupac, error_message, cuda_poisoned). Never reload model on CUDA errors."""
    try:
        iupac = parse_iupac_output(converter.smiles_to_iupac(smiles))
        if iupac:
            return iupac, "", False
        return "", "empty_output", False
    except Exception as exc:
        err = str(exc)[:200]
        if _is_cuda_error(err):
            return "", err, True
        clear_cuda()
        return "", err, False


def flag_similarity(score: float, threshold: float, has_iupac: bool) -> str:
    if not has_iupac:
        return "CONVERT_FAILED"
    if score >= threshold:
        return "OK"
    if score >= threshold - 0.15:
        return "SUSPICIOUS"
    return "LOW_SIMILARITY"


def load_checkpoint(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    ck = pd.read_csv(path)
    if "row_idx" not in ck.columns:
        return {}
    out: dict[int, dict] = {}
    for _, row in ck.iterrows():
        out[int(row["row_idx"])] = row.to_dict()
    return out


def save_checkpoint(path: Path, records: list[dict]) -> None:
    pd.DataFrame(records).to_csv(path, index=False)


def merge_into_all_data(input_path: Path, df: pd.DataFrame, ncol: str) -> pd.DataFrame | None:
    try:
        all_data = pd.read_excel(input_path, sheet_name="All_Data")
        merge_cols = [
            "STOUT_IUPAC",
            "JaroWinkler_Score",
            "JaroWinkler_vs_Resolved",
            "Pass3_CCAST_Flag",
            "Pass3_CCAST_Error",
        ]
        key = ncol if ncol in all_data.columns else "Chemical"
        present = [c for c in merge_cols if c in df.columns]
        ccast_part = df[[key] + present].drop_duplicates(subset=[key])
        all_data = all_data.merge(ccast_part, on=key, how="left", suffixes=("", "_ccast"))
        for c in present:
            ccast_col = f"{c}_ccast"
            if ccast_col in all_data.columns:
                all_data[c] = all_data[c].fillna(all_data[ccast_col])
                all_data.drop(columns=[ccast_col], inplace=True)
        return all_data
    except Exception as exc:
        print(f"Note: could not merge into All_Data: {exc}")
        return None


def export_results(
    output_path: Path,
    df: pd.DataFrame,
    all_data: pd.DataFrame | None,
) -> None:
    flagged = df["Pass3_CCAST_Flag"].isin(
        ["SUSPICIOUS", "LOW_SIMILARITY", "CONVERT_FAILED"]
    ).sum()
    with pd.ExcelWriter(output_path, engine="openpyxl") as w:
        if all_data is not None:
            all_data.to_excel(w, sheet_name="All_Data", index=False)
        df.to_excel(w, sheet_name="CCAST_Validated", index=False)
        df[df["Pass3_CCAST_Flag"].isin(
            ["SUSPICIOUS", "LOW_SIMILARITY", "CONVERT_FAILED"]
        )].to_excel(w, sheet_name="CCAST_Flagged", index=False)

    filled = (
        df["STOUT_IUPAC"].notna()
        & df["STOUT_IUPAC"].astype(str).str.strip().replace("nan", "").ne("")
    ).sum()
    print(f"Exported: {output_path}")
    print(f"  IUPAC produced: {filled}/{len(df)}")
    print(f"  Flagged: {flagged}/{len(df)}")


def run(
    input_path: Path,
    output_path: Path,
    threshold: float = DEFAULT_THRESHOLD,
    limit: int | None = None,
    resume: bool = False,
    checkpoint_path: Path = CHECKPOINT_CSV,
    checkpoint_every: int = CHECKPOINT_EVERY,
    force_cpu: bool = False,
    row_start: int | None = None,
    row_end: int | None = None,
    export_final: bool = True,
) -> pd.DataFrame:
    if force_cpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    elif not resume and row_start is None:
        ok, msg = cuda_is_healthy()
        if not ok:
            raise RuntimeError(
                f"CUDA is not healthy ({msg}).\n"
                "Kernel -> Restart Kernel, then Run All from the top.\n"
                "Do not re-run old inline notebook cells from a previous session.\n"
                "Or set USE_CPU = True for a slow but reliable CPU run."
            )

    device = get_device()
    print(f"Device: {device}")

    holder = {"converter": load_converter(force_cpu=force_cpu)}

    df = pd.read_excel(input_path, sheet_name="For_CCAST")
    if limit:
        df = df.head(limit)
    total = len(df)
    start = row_start or 0
    end = row_end if row_end is not None else total
    if row_start is not None or row_end is not None:
        print(f"Processing rows {start}-{end - 1} of {total}")
    else:
        print(f"Processing {total} rows with SMILES for reverse naming")

    ncol = "Chemical" if "Chemical" in df.columns else "_name"
    checkpoint = load_checkpoint(checkpoint_path) if resume or row_start is not None else {}
    if checkpoint:
        print(f"  Checkpoint loaded: {len(checkpoint)} rows already done")

    records: list[dict] = list(checkpoint.values()) if checkpoint else []
    records_by_idx = {int(r["row_idx"]): r for r in records}

    for pos, (i, row) in enumerate(df.iterrows()):
        if pos < start:
            continue
        if pos >= end:
            break
        if pos in records_by_idx:
            continue

        smi = str(row.get("SMILES", "") or "")
        orig = str(row.get(ncol, "") or "")
        resolved = str(row.get("Resolved_Name", "") or "")

        if not smi or smi == "nan":
            iupac, err = "", "no_smiles"
            cuda_poisoned = False
            score = score_r = 0.0
            flag = "NO_SMILES"
        else:
            iupac, err, cuda_poisoned = safe_smiles_to_iupac(holder["converter"], smi)
            score = jaro_winkler_similarity(orig.lower(), iupac.lower()) if iupac else 0.0
            score_r = (
                jaro_winkler_similarity(resolved.lower(), iupac.lower())
                if iupac and resolved and resolved != "nan"
                else 0.0
            )
            flag = flag_similarity(score, threshold, bool(iupac))

        rec = {
            "row_idx": pos,
            "Chemical": orig,
            "SMILES": smi,
            "STOUT_IUPAC": iupac,
            "JaroWinkler_Score": round(score, 4),
            "JaroWinkler_vs_Resolved": round(score_r, 4),
            "Pass3_CCAST_Flag": flag,
            "Pass3_CCAST_Error": err,
        }
        records_by_idx[pos] = rec

        if cuda_poisoned:
            print(f"  CUDA error at row {pos} — stopping batch (will retry on CPU)")
            break

        done_in_batch = pos - start + 1
        if done_in_batch % 50 == 0:
            ok = sum(1 for r in records_by_idx.values() if r.get("STOUT_IUPAC"))
            print(f"  [{pos + 1}/{total}] IUPAC ok so far: {ok}")

    records = [records_by_idx[i] for i in sorted(records_by_idx)]
    save_checkpoint(checkpoint_path, records)

    if not export_final:
        print(f"  batch checkpoint saved ({len(records)} rows total)")
        return _build_result_frame(df, records_by_idx)

    df = _build_result_frame(df, records_by_idx)

    all_data = merge_into_all_data(input_path, df, ncol)
    export_results(output_path, df, all_data)
    return df


def _build_result_frame(df: pd.DataFrame, records_by_idx: dict[int, dict]) -> pd.DataFrame:
    out = df.copy()
    for col, key in [
        ("STOUT_IUPAC", "STOUT_IUPAC"),
        ("JaroWinkler_Score", "JaroWinkler_Score"),
        ("JaroWinkler_vs_Resolved", "JaroWinkler_vs_Resolved"),
        ("Pass3_CCAST_Flag", "Pass3_CCAST_Flag"),
        ("Pass3_CCAST_Error", "Pass3_CCAST_Error"),
    ]:
        out[col] = [records_by_idx.get(i, {}).get(key, "") for i in range(len(df))]
    return out


def _batch_rows_done(checkpoint_path: Path, start: int, end: int) -> bool:
    ck = load_checkpoint(checkpoint_path)
    return all(i in ck for i in range(start, end))


def _run_batch_subprocess(
    script: Path,
    input_path: Path,
    output_path: Path,
    checkpoint_path: Path,
    start: int,
    end: int,
    use_cpu: bool,
) -> int:
    cmd = [
        sys.executable,
        str(script),
        "--input", str(input_path),
        "--output", str(output_path),
        "--checkpoint", str(checkpoint_path),
        "--row-start", str(start),
        "--row-end", str(end),
        "--no-export",
    ]
    if use_cpu:
        cmd.append("--cpu")
    result = subprocess.run(cmd)
    return result.returncode


def run_gpu_batched(
    input_path: Path,
    output_path: Path,
    threshold: float = DEFAULT_THRESHOLD,
    batch_size: int = DEFAULT_GPU_BATCH,
    checkpoint_path: Path = CHECKPOINT_CSV,
    force_cpu: bool = False,
    resume: bool = False,
) -> pd.DataFrame:
    """Run each batch in a fresh subprocess; retry failed batches on CPU."""
    df = pd.read_excel(input_path, sheet_name="For_CCAST")
    total = len(df)
    script = Path(__file__).resolve()

    if not resume and checkpoint_path.exists():
        checkpoint_path.unlink()

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        if _batch_rows_done(checkpoint_path, start, end):
            print(f"\n=== rows {start}-{end - 1} already in checkpoint — skip ===")
            continue

        print(f"\n=== GPU batch rows {start}-{end - 1} / {total - 1} ===")
        rc = _run_batch_subprocess(
            script, input_path, output_path, checkpoint_path, start, end, use_cpu=force_cpu
        )
        if rc != 0 or not _batch_rows_done(checkpoint_path, start, end):
            if force_cpu:
                print(f"  Batch {start}-{end - 1} failed even on CPU (exit {rc})")
                continue
            print(f"  GPU batch incomplete (exit {rc}) — retrying rows {start}-{end - 1} on CPU")
            _run_batch_subprocess(
                script, input_path, output_path, checkpoint_path, start, end, use_cpu=True
            )

    return run(
        input_path,
        output_path,
        threshold=threshold,
        resume=True,
        checkpoint_path=checkpoint_path,
        force_cpu=False,
        export_final=True,
    )


def _partial_frame(df, stout_names, scores, scores_res, flags, errors) -> pd.DataFrame:
    out = df.iloc[: len(stout_names)].copy()
    out["STOUT_IUPAC"] = stout_names
    out["JaroWinkler_Score"] = scores
    out["JaroWinkler_vs_Resolved"] = scores_res
    out["Pass3_CCAST_Flag"] = flags
    out["Pass3_CCAST_Error"] = errors
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=INPUT_XLSX)
    p.add_argument("--output", type=Path, default=OUTPUT_XLSX)
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--resume", action="store_true", help="Resume from ccast_checkpoint.csv")
    p.add_argument("--checkpoint", type=Path, default=CHECKPOINT_CSV)
    p.add_argument("--cpu", action="store_true", help="Force CPU (use if CUDA is poisoned)")
    p.add_argument("--row-start", type=int, default=None, help="Worker: first row index")
    p.add_argument("--row-end", type=int, default=None, help="Worker: end row index (exclusive)")
    p.add_argument("--no-export", action="store_true", help="Worker: checkpoint only, no Excel")
    p.add_argument(
        "--gpu-batch",
        type=int,
        default=None,
        metavar="N",
        help=f"Run GPU in subprocess batches of N rows (default {DEFAULT_GPU_BATCH} when set without N)",
    )
    args = p.parse_args()

    if args.gpu_batch is not None:
        batch = args.gpu_batch if args.gpu_batch > 0 else DEFAULT_GPU_BATCH
        run_gpu_batched(
            args.input,
            args.output,
            args.threshold,
            batch_size=batch,
            checkpoint_path=args.checkpoint,
            force_cpu=args.cpu,
            resume=args.resume,
        )
    else:
        run(
            args.input,
            args.output,
            args.threshold,
            args.limit,
            resume=args.resume,
            checkpoint_path=args.checkpoint,
            force_cpu=args.cpu,
            row_start=args.row_start,
            row_end=args.row_end,
            export_final=not args.no_export,
        )


if __name__ == "__main__":
    main()
