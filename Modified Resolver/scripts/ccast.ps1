# =====================================================================
# ccast.ps1 - drive CCAST jobs from your Windows PC without keeping a
#             terminal window open.
#
# CCAST requires Duo 2FA on SSH, so EACH command below triggers ONE Duo
# push you must approve on your phone. That is fine: `qsub` hands the job
# to the scheduler, which runs it independently of your SSH session. So
# you submit (approve Duo once), close everything, and the job keeps
# running on CCAST. ntfy pushes your phone when it finishes. You only
# approve Duo again if you choose to check status or pull results.
#
# Usage from PowerShell (in the "Modified Resolver" folder):
#   .\scripts\ccast.ps1 submit     # qsub the 1947 job  (then you can close the PC)
#   .\scripts\ccast.ps1 status     # qstat -u you
#   .\scripts\ccast.ps1 log        # tail the run log
#   .\scripts\ccast.ps1 pull       # download outputs + log to .\outputs_ccast
#   .\scripts\ccast.ps1 sync       # upload local code changes to scratch
#   .\scripts\ccast.ps1 go         # sync + submit in ONE Duo approval
#
# Add -Cluster prime to target prime instead of thunder.
# =====================================================================

param(
    [Parameter(Position = 0)]
    [ValidateSet("submit", "status", "log", "pull", "sync", "go")]
    [string]$Action = "status",

    [ValidateSet("thunder", "prime")]
    [string]$Cluster = "thunder"
)

# ---- account settings ----------------------------------------------
# Thunder uses the Slurm scheduler. Slurm tools are at a fixed path; using
# the full path avoids any login-shell PATH/module issues over one-shot SSH.
$User       = "ayman.akash"
$Remote     = "${User}@${Cluster}.ccast.ndsu.edu"
$RemoteDir  = "/mmfs1/scratch/ayman.akash/Modified Resolver"
$JobScript  = "jobs/resolve_1947.slurm"
$LogName    = "resolve_1947_slurm.log"
$SbatchBin  = "/cm/local/apps/slurm/current/bin/sbatch"
$SqueueBin  = "/cm/local/apps/slurm/current/bin/squeue"
$SlurmConf  = "/cm/shared/apps/slurm/etc/thunder-prod/slurm.conf"
# --------------------------------------------------------------------

# The remote path has a space ("Modified Resolver"), so it must be quoted twice:
#   $QRemoteDir  - single-quoted, for commands the REMOTE shell runs (ssh)
#   $ScpDir      - double-quoted INSIDE the scp arg, so the quotes survive to the
#                  remote shell (scp's remote path is parsed by that shell)
$QRemoteDir = "'" + $RemoteDir + "'"
$ScpDir     = "${Remote}:`"${RemoteDir}/`""
$local      = Join-Path $PSScriptRoot ".."

# Slurm clients need SLURM_CONF set when called over a non-interactive SSH.
function Invoke-Remote([string]$RemoteCmd) {
    ssh $Remote "bash -lc `"export SLURM_CONF=$SlurmConf; $RemoteCmd`""
}

switch ($Action) {
    "submit" {
        Write-Host "Submitting $JobScript on $Remote ..." -ForegroundColor Cyan
        Invoke-Remote "cd $QRemoteDir && $SbatchBin $JobScript"
    }
    "status" {
        Write-Host "Queue status for $User on $Remote ..." -ForegroundColor Cyan
        Invoke-Remote "$SqueueBin -u $User"
    }
    "log" {
        Write-Host "Last 40 lines of $LogName ..." -ForegroundColor Cyan
        Invoke-Remote "cd $QRemoteDir && tail -n 40 $LogName"
    }
    "pull" {
        $dest = Join-Path $PSScriptRoot "..\outputs_ccast"
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        Write-Host "Downloading results to $dest (one Duo prompt) ..." -ForegroundColor Cyan
        # one scp call, multiple remote sources => single Duo approval
        scp "${Remote}:`"${RemoteDir}/outputs/resolved_1947.csv`"" `
            "${Remote}:`"${RemoteDir}/${LogName}`"" `
            "${Remote}:`"${RemoteDir}/cache/resolve_cache.json`"" `
            $dest
        Write-Host "Done. Files in $dest" -ForegroundColor Green
    }
    "sync" {
        # scp -r re-applies the Windows folder's read-only bit to remote dirs
        # (so chmod), and Windows files arrive with CRLF (so strip \r from the
        # shell/slurm scripts Slurm will execute).
        Write-Host "Uploading code to scratch (expect 2 Duo prompts: upload + fixups) ..." -ForegroundColor Cyan
        scp -r "$local\chemresolve" "$local\scripts" "$local\jobs" "$local\requirements.txt" $ScpDir
        Invoke-Remote "chmod -R u+rwX $QRemoteDir && find $QRemoteDir/jobs -name '*.slurm' -exec sed -i 's/\r`$//' {} +"
        Write-Host "Sync complete." -ForegroundColor Green
    }
    "go" {
        Write-Host "Uploading code, fixing perms+line-endings, then submitting (expect 3 Duo prompts) ..." -ForegroundColor Cyan
        scp -r "$local\chemresolve" "$local\scripts" "$local\jobs" "$local\requirements.txt" $ScpDir
        Invoke-Remote "chmod -R u+rwX $QRemoteDir && find $QRemoteDir/jobs -name '*.slurm' -exec sed -i 's/\r`$//' {} + && cd $QRemoteDir && $SbatchBin $JobScript"
        Write-Host "Submitted. You can close the PC; ntfy will notify your phone." -ForegroundColor Green
    }
}
