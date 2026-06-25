#!/bin/bash
# =====================================================================
# Full 1947 dataset resolution on CCAST THUNDER (Slurm scheduler).
#
# Thunder uses Slurm (NOT PBS), so this is a #SBATCH script.
# Submit from your PC (one Duo) or on the login node:
#   cd "/mmfs1/scratch/ayman.akash/Modified Resolver"
#   sbatch jobs/resolve_1947.slurm
# Monitor:  squeue -u ayman.akash
# Cancel:   scancel <jobid>
#
# RESUMABLE: every lookup is cached, so if it stops (time limit, node
# failure) just sbatch again and it continues from the cache.
#
# Phone push: NTFY_TOPIC is set below; install the "ntfy" app and
# subscribe to that topic. Email is handled by --mail-type/--mail-user.
# =====================================================================
#SBATCH --job-name=chemresolve_1947
#SBATCH --partition=compute
#SBATCH --account=x-ccast-prj-hpirim
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=12:00:00
#SBATCH --output=resolve_1947_slurm.log
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=ayman.akash@ndsu.edu

NTFY_TOPIC="ayman-ccast-7f3a9b2c"   # subscribe to this in the ntfy phone app

set -uo pipefail

echo "=== chemresolve 1947 full run (Slurm) ==="
echo "Host:  $(hostname)"
echo "Start: $(date)"
echo "Job:   ${SLURM_JOB_ID:-?}  Submit dir: ${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "${SLURM_SUBMIT_DIR:-$(pwd)}"

echo "Python: $(python3 --version 2>&1 || python --version)"
echo "Java:   $(java -version 2>&1 | head -1 || echo 'Java not found - OPSIN will be skipped')"

python3 -m pip install --user -q -r requirements.txt

echo "Resolver availability:"
python3 -c "import sys; sys.path.insert(0,'.'); from chemresolve.resolvers import resolver_availability; print(resolver_availability())"

echo ""
echo "=== Running run_resolve.py --year 1947 ==="
python3 scripts/run_resolve.py \
    --year 1947 \
    --data-dir . \
    --cache cache/resolve_cache.json \
    --out-dir outputs \
    --flush-every 100
RC=$?

echo ""
echo "Exit code: ${RC}"
echo "Done: $(date)"

# --- one-line summary for the phone notification ---
SUMMARY=$(grep -E "^DONE year=1947" resolve_1947_slurm.log | tail -1)
[ -z "${SUMMARY}" ] && SUMMARY="run_resolve finished with exit code ${RC} (no DONE line - check log)"

if [ -n "${NTFY_TOPIC}" ]; then
    curl -s \
        -H "Title: CCAST 1947 run finished" \
        -H "Priority: high" \
        -H "Tags: white_check_mark" \
        -d "${SUMMARY}" \
        "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null \
        && echo "Phone notification sent to ntfy topic." \
        || echo "ntfy notification failed (non-fatal)."
fi

echo ""
echo "Results: ${SLURM_SUBMIT_DIR}/outputs/resolved_1947.csv"
echo "Cache:   ${SLURM_SUBMIT_DIR}/cache/resolve_cache.json"
echo "Log:     ${SLURM_SUBMIT_DIR}/resolve_1947_slurm.log"
exit ${RC}
