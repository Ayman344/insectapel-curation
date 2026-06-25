"""
Generate a personal CCAST Job-Submission RUNBOOK (journal style).

This is Ayman's self-service guide: how we first ran a job in the CCAST OnDemand
shell, every error we hit and exactly how we fixed it, the results we saw, and
the full from-your-PC submission procedure -- with two flowcharts. Filenames are
placeholders (your_script.py, your_job.slurm, <project>) so it works for ANY
future job; CCAST-specific values (host, account, paths) are real.

Run:  python generate_ccast_runbook_pdf.py
Output: CCAST_Job_Submission_Runbook.pdf
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).parent
OUT = ROOT / "CCAST_Job_Submission_Runbook.pdf"

STEP = (224, 236, 250)      # light blue
DECISION = (255, 243, 205)  # amber
ERR = (250, 224, 224)       # red
DONE = (215, 244, 222)      # green


def sanitize(text: str) -> str:
    repl = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2192": "->", "\u2190": "<-",
        "\u2026": "...", "\u2264": "<=", "\u2265": ">=", "\u00a0": " ",
        "\u00d7": "x", "\u2248": "~", "\u2713": "[ok]", "\u2717": "[x]",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class Runbook(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=16)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(110, 110, 110)
            self.cell(0, 8, "CCAST Job Submission Runbook", align="R")
            self.ln(4)
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    # ---- text helpers ----
    def title_page(self):
        self.add_page()
        self.ln(30)
        self.set_font("Helvetica", "B", 24)
        self.multi_cell(0, 12, "CCAST Job Submission", align="C",
                        new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 18)
        self.multi_cell(0, 10, "A Personal Runbook", align="C",
                        new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(80, 80, 80)
        self.multi_cell(
            0, 6,
            sanitize("From the first OnDemand shell test to an unattended Slurm batch "
                     "job submitted from my own PC -- with every error, fix, result, "
                     "and a flowchart to follow next time."),
            align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(16)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 8, f"Written: {date.today().strftime('%B %d, %Y')}", align="C")
        self.ln(6)
        self.cell(0, 8, "CCAST Thunder cluster (Slurm) - NDSU / Insectapel", align="C")
        self.ln(14)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(90, 90, 90)
        self.multi_cell(
            0, 5.5,
            sanitize("How to use this: Section 1 = running a quick test in the CCAST "
                     "OnDemand web shell. Section 2 = submitting a real batch job from "
                     "my PC. Section 3 = error dictionary. Section 4 = copy-paste cheat "
                     "sheet. The two flowcharts (end of Sec 1 and Sec 2) are the things "
                     "to follow when I do this alone."),
            align="C")
        self.set_text_color(0, 0, 0)

    def h1(self, t):
        if self.get_y() > 240:
            self.add_page()
        self.ln(2)
        self.set_font("Helvetica", "B", 14)
        self.set_fill_color(225, 236, 250)
        self.cell(0, 9, sanitize(t), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def h2(self, t):
        if self.get_y() > 252:
            self.add_page()
        self.set_font("Helvetica", "B", 11.5)
        self.cell(0, 7, sanitize(t), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def p(self, t):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, sanitize(t))
        self.ln(1.2)

    def bullet(self, t, lab="-"):
        self.set_font("Helvetica", "", 10)
        x = self.get_x()
        self.cell(6, 5.4, lab)
        self.multi_cell(0, 5.4, sanitize(t))
        self.set_x(x)

    def step(self, n, t):
        self.set_font("Helvetica", "B", 10)
        x = self.get_x()
        self.cell(8, 5.4, f"{n}.")
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.4, sanitize(t))
        self.set_x(x)

    def code(self, text):
        self.set_font("Courier", "", 7.7)
        self.set_fill_color(244, 244, 244)
        for line in text.split("\n"):
            self.multi_cell(0, 4.6, sanitize(line) if line.strip() else " ",
                            fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.ln(1.5)

    def note(self, text, color=(255, 248, 220)):
        self.set_fill_color(*color)
        self.set_font("Helvetica", "I", 9.5)
        self.multi_cell(0, 5.3, sanitize(text), fill=True)
        self.ln(2)

    def errbox(self, msg, cause, fix):
        """A red-tinted box: verbatim error, cause, fix."""
        if self.get_y() > 232:
            self.add_page()
        self.set_font("Courier", "B", 8)
        self.set_fill_color(250, 226, 226)
        self.multi_cell(0, 4.6, sanitize(msg), fill=True, border=0,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9.5)
        self.set_fill_color(252, 240, 240)
        self.multi_cell(0, 5, sanitize("Why: " + cause), fill=True,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_fill_color(236, 248, 238)
        self.multi_cell(0, 5, sanitize("Fix: " + fix), fill=True,
                        new_x="LMARGIN", new_y="NEXT")
        self.ln(2.5)

    # ---- flowchart helpers ----
    def _flow_box(self, text, kind=STEP, bold=False):
        w = 158
        x = (self.w - w) / 2
        self.set_font("Helvetica", "B" if bold else "", 9)
        lines = self.multi_cell(w - 8, 4.8, sanitize(text), dry_run=True, output="LINES")
        th = len(lines) * 4.8
        h = max(11, th + 5)
        if self.get_y() + h + 9 > self.h - self.b_margin:
            self.add_page()
        y = self.get_y()
        self.set_fill_color(*kind)
        self.set_draw_color(70, 70, 70)
        self.rect(x, y, w, h, "DF")
        self.set_xy(x + 4, y + (h - th) / 2)
        self.multi_cell(w - 8, 4.8, sanitize(text), align="C",
                        new_x="LMARGIN", new_y="TOP")
        self.set_draw_color(0, 0, 0)
        self.set_y(y + h)

    def _flow_arrow(self, label=""):
        cx = self.w / 2
        y = self.get_y()
        self.set_draw_color(90, 90, 90)
        self.line(cx, y + 0.5, cx, y + 7.2)
        self.line(cx, y + 7.8, cx - 2, y + 4.8)
        self.line(cx, y + 7.8, cx + 2, y + 4.8)
        self.set_draw_color(0, 0, 0)
        if label:
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(110, 110, 110)
            self.text(cx + 4, y + 5.5, sanitize(label))
            self.set_text_color(0, 0, 0)
        self.set_y(y + 8.5)

    def flow(self, steps):
        for i, item in enumerate(steps):
            if len(item) == 3:
                text, kind, bold = item
            else:
                text, kind = item
                bold = False
            self._flow_box(text, kind, bold)
            if i < len(steps) - 1:
                self._flow_arrow()

    def legend(self):
        self.set_font("Helvetica", "", 8)
        items = [("Step", STEP), ("Decision", DECISION), ("If error", ERR), ("Start/Done", DONE)]
        x = self.get_x()
        for label, col in items:
            self.set_fill_color(*col)
            self.cell(5, 4, "", border=1, fill=True)
            self.cell(24, 4, " " + label)
        self.ln(7)


def build():
    d = Runbook()
    d.title_page()
    d.add_page()

    # ============================================================ 0
    d.h1("0. Orientation: the two shells and the golden rules")
    d.p("Throughout this work there are TWO different command lines. Knowing which one you are "
        "typing into prevents most mistakes.")
    d.bullet("OnDemand shell: a Linux terminal that runs ON CCAST, opened in the web browser "
             "(ondemand.ccast.ndsu.edu -> Clusters -> Thunder Shell). Its prompt looks like "
             "[ayman.akash@login0002 ~]$ . You are already on CCAST.")
    d.bullet("PC shell: PowerShell on my own Windows laptop. Its prompt looks like "
             "PS C:\\Users\\ayman\\...> . You are on my PC, NOT on CCAST.")
    d.ln(1)
    d.h2("Golden rules (memorize these)")
    d.bullet("`ssh user@host` with NO command = TELEPORT into CCAST. The prompt changes to "
             "[user@login0002 ~]$. Type `exit` to come back to the PC.")
    d.bullet("`ssh user@host \"some command\"` (command in quotes) = run that command on CCAST and "
             "return to the PC immediately. Use this to submit/monitor without logging in.")
    d.bullet("`scp localfile user@host:/path/` = copy a file from PC to CCAST. Runs from the PC.")
    d.bullet("CCAST requires Duo 2FA: every ssh/scp connection sends ONE push to my phone to approve.")
    d.bullet("A submitted batch job runs on the cluster on its own. I can close the PC; it keeps going.")
    d.note("Most of the confusing errors below came from forgetting rule #1 (running PC commands "
           "while accidentally still logged into CCAST) or from Windows file quirks (read-only "
           "folders and CRLF line endings). The fixes are simple once you recognize them.")

    # ============================================================ 1
    d.h1("1. First run in the CCAST OnDemand Shell")
    d.p("Goal of this stage: prove the code and all chemistry libraries work on CCAST with a tiny "
        "test, before committing to a long job. We used the OnDemand web shell (already on CCAST, "
        "so no Duo per command).")

    d.h2("1.0 The steps we ran")
    d.step(1, "Uploaded the project (a .zip made on my PC) to scratch using OnDemand -> Files, then "
              "unzipped it. Scratch path base: /mmfs1/scratch/ayman.akash/")
    d.code('cd /mmfs1/scratch/ayman.akash\n'
           'unzip "<project>.zip"\n'
           'cd "<project>"')
    d.step(2, "Checked the environment is sane:")
    d.code('python3 --version        # -> Python 3.9.21\n'
           'java -version            # -> openjdk 1.8.0_472  (OPSIN needs Java)\n'
           'curl -s "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/ethanol/property/CanonicalSMILES/TXT"\n'
           '                         # -> CCO   (confirms internet works on CCAST)')
    d.step(3, "Installed Python packages into my account (no admin needed):")
    d.code('python3 -m pip install --user -r requirements.txt')
    d.step(4, "Ran a 5-name smoke test:")
    d.code('python3 your_script.py --limit 5')

    d.h2("1.1 Problems / log messages we saw, and the results")
    d.p("Nothing fatal happened here, but two kinds of messages look alarming and are NOT:")
    d.errbox(
        "...py2opsin/py2opsin.py:146: RuntimeWarning: OPSIN raised the following\n"
        "error(s) while parsing: ... is unparsable ...",
        "OPSIN (the IUPAC name parser) cannot read some old/archaic chemical names. It prints a "
        "Python RuntimeWarning, not an error. The program keeps going and tries the other resolvers.",
        "Ignore it. It is expected for messy historical names. A name only truly 'fails' if ALL "
        "resolvers and variants are exhausted.")
    d.errbox(
        "Using legacy 'setup.py install' for cirpy, since package 'wheel' is not installed.",
        "Just pip telling you one package installed the older way.",
        "Ignore it -- the install still finished with 'Successfully installed ...'.")
    d.p("Result of the 5-name test:")
    d.code('Resolver availability: {pubchem: True, opsin: True, cirpy: True}\n'
           'Summary: {resolved: 4, quarantine: 1}')
    d.bullet("resolved = a structure was found AND passed the validator (good).")
    d.bullet("quarantine = candidates were found but the validator rejected them all (also good -- "
             "it refused a wrong structure instead of accepting it).")

    d.h2("1.2 Rerun with more names, and the next plan")
    d.p("Confident it worked, we scaled the test to 20 names:")
    d.code('python3 your_script.py --limit 20')
    d.p("Output (about 45 seconds):")
    d.code('Summary: {resolved: 15, quarantine: 1, failed: 4}')
    d.bullet("15 resolved (75%) -- including the hard 'mercaptal' name that the OLD pipeline got "
             "wrong; now correct and validated.")
    d.bullet("1 quarantine -- a disconnected-mixture ester the validator correctly refused.")
    d.bullet("4 failed -- genuinely hard: a trade name in quotes, scan-corrupted text, a very "
             "complex ester. Failing honestly is better than a wrong answer.")
    d.p("Next plan from here: run the FULL first dataset (~7,000 names) as a real batch job through "
        "the scheduler, instead of typing it live -- which moves us to Section 2.")

    d.h2("1.3 Flowchart A -- OnDemand shell quick test")
    d.legend()
    d.flow([
        ("START: open OnDemand -> Clusters -> Thunder Shell", DONE, True),
        ("Upload <project>.zip via OnDemand -> Files (into /mmfs1/scratch/ayman.akash)", STEP),
        ("cd /mmfs1/scratch/ayman.akash ; unzip \"<project>.zip\" ; cd \"<project>\"", STEP),
        ("Check: python3 --version ; java -version ; curl <pubchem test> -> expect CCO", STEP),
        ("python3 -m pip install --user -r requirements.txt", STEP),
        ("python3 your_script.py --limit 5", STEP),
        ("Look at Summary line. Results sensible? (resolved/quarantine/failed)", DECISION, True),
        ("YES: rerun bigger -> python3 your_script.py --limit 20", STEP),
        ("Happy with quality? -> go to Flowchart B (batch submit)", DONE, True),
    ])
    d.note("If 'NO' at the decision (errors, all failed, wrong availability): read the message. "
           "ModuleNotFoundError -> rerun the pip install line. 'java not found' -> OPSIN will be "
           "off but PubChem/CIRpy still work. Network/curl fails -> stop and report it.")

    # ============================================================ 2
    d.add_page()
    d.h1("2. Submitting a batch job from my own PC shell")
    d.p("Goal: from PowerShell on my laptop, upload the code, submit a long job to the scheduler, "
        "then close the laptop and get a phone notification when it finishes. This is where most "
        "errors happened -- each is documented so you recognize and fix it instantly.")

    d.h2("2.0 One-time prerequisites")
    d.bullet("Windows already has ssh/scp (OpenSSH). Check: `ssh -V`.")
    d.bullet("Phone notification: install the free 'ntfy' app and Subscribe to topic "
             "ayman-ccast-7f3a9b2c (the job script posts there when done). Email also arrives via "
             "the script's mail settings.")
    d.bullet("Know your key CCAST values (Section 4 lists them all).")

    d.h2("2.1 The errors we hit, in order, with fixes")
    d.p("This is the heart of the runbook. If you see one of these again, here is exactly what it "
        "means and what to type.")

    d.errbox(
        "Connection closed   (after scp/qsub seemed to do nothing)",
        "I had run `ssh user@host` by itself first, which logged me INTO CCAST. Then I ran scp / "
        "the submit command while still on CCAST, so they tried to act on files that only exist on "
        "my PC.",
        "Recognize the prompt: [user@login0002 ~]$ means you are ON CCAST -- type `exit` first. "
        "scp and `ssh host \"cmd\"` must be run from the PC prompt (PS C:\\...>).")

    d.errbox(
        "scp.exe: dest open \"/.../jobs/your_job.slurm\": Permission denied\n"
        "scp.exe: failed to upload directory ...",
        "The project was zipped on Windows; Windows marks folders read-only inside the zip, so on "
        "CCAST the folders had no write bit (dr-x------). You can OVERWRITE existing files but "
        "cannot CREATE new ones in a read-only folder.",
        "Make your folders writable (you own them, so this always works):\n"
        "ssh user@host 'bash -lc \"chmod -R u+rwX \\'/mmfs1/scratch/ayman.akash/<project>\\'\"'")

    d.errbox(
        "rm: cannot remove '/.../<project>/...': Permission denied   (for many files)",
        "Same root cause. In Linux, deleting a file needs WRITE permission on its FOLDER, and the "
        "Windows-zip folders were read-only. (Owning the file is not enough.)",
        "Same chmod -R u+rwX fixes it. Tip: prefer uploading folders with `scp -r` directly "
        "instead of zipping on Windows -- scp creates writable folders. Even better, avoid the "
        "whole problem by not re-zipping; copy the folder tree with scp -r.")

    d.errbox(
        "bash: line 1: qsub: command not found   (also after bash -lc)",
        "Two issues stacked: (a) scheduler tools are not on PATH for a non-interactive ssh; and, "
        "more importantly, (b) Thunder does NOT use PBS at all. `qsub` does not exist here.",
        "Thunder uses SLURM. Use `sbatch` (submit), `squeue` (status), `scancel` (cancel). See the "
        "discovery commands and the real paths in Section 4.")

    d.errbox(
        "qstat: cannot connect to server (errno=0)\n"
        "pbsconf error: pbs conf variables not found: PBS_HOME PBS_EXEC PBS_SERVER",
        "Leftover PBS client binaries exist on disk but there is no PBS server -- because the "
        "scheduler is Slurm. `module list` confirmed: slurm/thunder-prod/24.11 is loaded.",
        "Stop using any PBS/qsub/qstat command. Switch entirely to Slurm.")

    d.errbox(
        "sbatch: command not found / Slurm can't find its config (non-interactive ssh)",
        "Over a one-shot ssh, the Slurm module is not auto-loaded, so neither the sbatch PATH nor "
        "the SLURM_CONF variable are set.",
        "Call sbatch by full path AND export the config first:\n"
        "export SLURM_CONF=/cm/shared/apps/slurm/etc/thunder-prod/slurm.conf\n"
        "/cm/local/apps/slurm/current/bin/sbatch your_job.slurm")

    d.errbox(
        "sbatch: error: ... Invalid account or account/partition combination   (if it appears)",
        "Slurm requires charging the job to a project account.",
        "Add to the script: #SBATCH --account=x-ccast-prj-hpirim  and #SBATCH --partition=compute. "
        "Find your accounts with: id   (look for x-ccast-prj-...).")

    d.errbox(
        "scp.exe: dest open \"/.../jobs/your_job.slurm\": Permission denied   (AGAIN, after it worked once)",
        "Every `scp -r <folder>` re-applies the Windows folder's read-only bit to the remote "
        "folder, re-locking it. So a folder you fixed earlier becomes read-only again after the "
        "next recursive upload.",
        "Either upload a SINGLE file (scp file host:/path/ does NOT change folder perms), or run "
        "chmod -R u+rwX again after any `scp -r`. (The ccast.ps1 helper now auto-chmods.)")

    d.errbox(
        "sbatch: error: Batch script contains DOS line breaks (\\r\\n)\n"
        "instead of expected UNIX line breaks (\\n).",
        "The .slurm script was created/edited on Windows, which ends lines with CR+LF. Slurm "
        "requires Unix LF line endings.",
        "Strip the carriage returns on CCAST, then submit:\n"
        "sed -i 's/\\r$//' your_job.slurm\n"
        "(The ccast.ps1 helper now runs this automatically on *.slurm after upload.)")

    d.note("Harmless noise you may also see when submitting over ssh: a long list of "
           "`declare -x ...` lines (the module system initializing). It is not an error -- just "
           "scroll to the 'Submitted batch job <N>' line.", color=(240, 240, 250))

    d.h2("2.2 The result: success")
    d.p("After the fixes, the submit command returned:")
    d.code('Submitted batch job 13600')
    d.p("That number is the Slurm job ID. The job then ran unattended on a compute node; the phone "
        "got the ntfy push when it finished. That is the whole goal achieved.")

    d.h2("2.3 The clean procedure (what to actually do next time)")
    d.p("Once the .slurm script exists and your code is on CCAST, a normal submission is just:")
    d.code('# from PowerShell, in your project folder on the PC\n'
           '# (1) upload the job script (single file = no perms problem)\n'
           'scp jobs\\your_job.slurm \'ayman.akash@thunder.ccast.ndsu.edu:"/mmfs1/scratch/ayman.akash/<project>/jobs/"\'\n'
           '\n'
           '# (2) fix line endings + submit, in one connection\n'
           'ssh ayman.akash@thunder.ccast.ndsu.edu \'bash -lc "export SLURM_CONF=/cm/shared/apps/slurm/etc/thunder-prod/slurm.conf; cd \'\'/mmfs1/scratch/ayman.akash/<project>\'\' && sed -i \'\'s/\\r$//\'\' jobs/your_job.slurm && /cm/local/apps/slurm/current/bin/sbatch jobs/your_job.slurm"\'')
    d.note("Or just use the helper script: .\\scripts\\ccast.ps1 go  (uploads, fixes perms + line "
           "endings, and submits). .\\scripts\\ccast.ps1 status / log / pull for the rest.")

    d.h2("2.4 Flowchart B -- submit a batch job from the PC")
    d.legend()
    d.flow([
        ("START: open PowerShell in the project folder on the PC (prompt PS C:\\...>)", DONE, True),
        ("First time only: ssh user@host -> approve Duo -> type 'exit' to test login", STEP),
        ("Upload the job script: scp jobs\\your_job.slurm  user@host:\"/.../<project>/jobs/\"", STEP),
        ("Permission denied? -> ssh ... chmod -R u+rwX \"/.../<project>\"  then re-upload", ERR),
        ("Submit (one connection): ssh ... 'bash -lc \"export SLURM_CONF=...; cd <dir> && sed -i s/CR// job && sbatch job\"'", STEP),
        ("Did it print 'Submitted batch job <N>' ?", DECISION, True),
        ("NO: read error -> look it up in Section 3 (qsub/Slurm, DOS breaks, account) -> fix -> resubmit", ERR),
        ("YES: close the PC. Job runs on the cluster by itself.", DONE, True),
        ("Wait for ntfy push / email. (Optional) check: ssh ... 'bash -lc \"... squeue -u user\"'", STEP),
        ("When job leaves squeue -> download: scp user@host:\"/.../outputs/your_output\" .", DONE, True),
    ])

    # ============================================================ 3
    d.add_page()
    d.h1("3. Error dictionary (look up any message)")
    d.set_font("Helvetica", "", 9)
    rows = [
        ("Connection closed; commands do nothing",
         "You are logged into CCAST; ran a PC command there",
         "Type exit; run scp / ssh \"cmd\" from PS C:\\...>"),
        ("scp ... Permission denied (new file)",
         "Windows zip made remote folder read-only",
         "ssh ... chmod -R u+rwX \"<project dir>\""),
        ("rm ... Permission denied",
         "Folder not writable (need write on the folder)",
         "Same chmod -R u+rwX"),
        ("Permission denied AGAIN after scp -r",
         "scp -r re-locked the folder",
         "Upload single files, or chmod again after scp -r"),
        ("qsub: command not found",
         "Thunder uses Slurm, not PBS",
         "Use sbatch / squeue / scancel"),
        ("qstat: cannot connect to server",
         "No PBS server (Slurm cluster)",
         "Use squeue instead of qstat"),
        ("Slurm can't find config over ssh",
         "Module not auto-loaded non-interactively",
         "export SLURM_CONF=...thunder-prod/slurm.conf"),
        ("Invalid account / partition",
         "Missing Slurm account",
         "#SBATCH --account=x-ccast-prj-hpirim ; --partition=compute"),
        ("Batch script contains DOS line breaks",
         "Windows CRLF endings in .slurm",
         "sed -i 's/\\r$//' your_job.slurm"),
        ("RuntimeWarning: OPSIN ... unparsable",
         "Old name OPSIN can't parse (not an error)",
         "Ignore; other resolvers still try"),
        ("declare -x ... wall of text",
         "Module system init noise",
         "Ignore; find the 'Submitted batch job' line"),
    ]
    # simple 3-col table inline
    headers = ["Message you see", "What it means", "What to type / do"]
    cw = [62, 58, 60]
    d.set_font("Helvetica", "B", 8.5)
    d.set_fill_color(220, 230, 242)
    for i, h in enumerate(headers):
        d.cell(cw[i], 7, sanitize(h), border=1, fill=True)
    d.ln()
    d.set_font("Helvetica", "", 8.2)
    fill = False
    for r in rows:
        # compute height
        hh = 6
        lines = [d.multi_cell(cw[i] - 2, 4, sanitize(r[i]), dry_run=True, output="LINES") for i in range(3)]
        hh = max(6, max(len(x) for x in lines) * 4 + 2)
        if d.get_y() + hh > d.h - d.b_margin:
            d.add_page()
            d.set_font("Helvetica", "B", 8.5)
            d.set_fill_color(220, 230, 242)
            for i, h in enumerate(headers):
                d.cell(cw[i], 7, sanitize(h), border=1, fill=True)
            d.ln()
            d.set_font("Helvetica", "", 8.2)
        y0, x0 = d.get_y(), d.l_margin
        d.set_fill_color(245, 248, 252) if fill else d.set_fill_color(255, 255, 255)
        for i in range(3):
            d.set_xy(x0 + sum(cw[:i]), y0)
            d.cell(cw[i], hh, "", border=1, fill=True)
        for i in range(3):
            d.set_xy(x0 + sum(cw[:i]) + 1, y0 + 1)
            d.multi_cell(cw[i] - 2, 4, sanitize(r[i]))
        d.set_xy(x0, y0 + hh)
        fill = not fill
    d.ln(3)

    # ============================================================ 4
    d.add_page()
    d.h1("4. Cheat sheet (copy-paste, fill the placeholders)")
    d.h2("4.1 My CCAST constants")
    d.code('Host           : thunder.ccast.ndsu.edu   (or prime.ccast.ndsu.edu)\n'
           'User           : ayman.akash\n'
           'Scratch base   : /mmfs1/scratch/ayman.akash\n'
           'Project dir    : /mmfs1/scratch/ayman.akash/<project>\n'
           'Slurm account  : x-ccast-prj-hpirim\n'
           'Partition      : compute      (7-day limit; default)\n'
           'SLURM_CONF     : /cm/shared/apps/slurm/etc/thunder-prod/slurm.conf\n'
           'sbatch / squeue: /cm/local/apps/slurm/current/bin/{sbatch,squeue,scancel}\n'
           'Phone (ntfy)   : topic ayman-ccast-7f3a9b2c')

    d.h2("4.2 A minimal Slurm script template (your_job.slurm)")
    d.code('#!/bin/bash\n'
           '#SBATCH --job-name=myjob\n'
           '#SBATCH --partition=compute\n'
           '#SBATCH --account=x-ccast-prj-hpirim\n'
           '#SBATCH --nodes=1\n'
           '#SBATCH --ntasks=1\n'
           '#SBATCH --cpus-per-task=1\n'
           '#SBATCH --mem=4G\n'
           '#SBATCH --time=12:00:00\n'
           '#SBATCH --output=myjob.log\n'
           '#SBATCH --mail-type=END,FAIL\n'
           '#SBATCH --mail-user=ayman.akash@ndsu.edu\n'
           '\n'
           'cd "$SLURM_SUBMIT_DIR"\n'
           'python3 -m pip install --user -q -r requirements.txt\n'
           'python3 your_script.py            # your actual command\n'
           '# optional phone push at the end:\n'
           'curl -s -d "myjob done" https://ntfy.sh/ayman-ccast-7f3a9b2c')

    d.h2("4.3 Commands (run from PowerShell on the PC)")
    d.code('# upload one file (safe; no perms problem)\n'
           'scp jobs\\your_job.slurm \'ayman.akash@thunder.ccast.ndsu.edu:"/mmfs1/scratch/ayman.akash/<project>/jobs/"\'\n'
           '\n'
           '# upload a whole folder, then fix perms (folders go read-only otherwise)\n'
           'scp -r <folder> \'ayman.akash@thunder.ccast.ndsu.edu:"/mmfs1/scratch/ayman.akash/<project>/"\'\n'
           'ssh ayman.akash@thunder.ccast.ndsu.edu \'bash -lc "chmod -R u+rwX \'\'/mmfs1/scratch/ayman.akash/<project>\'\'"\'\n'
           '\n'
           '# submit (fix line endings + sbatch in one go)\n'
           'ssh ayman.akash@thunder.ccast.ndsu.edu \'bash -lc "export SLURM_CONF=/cm/shared/apps/slurm/etc/thunder-prod/slurm.conf; cd \'\'/mmfs1/scratch/ayman.akash/<project>\'\' && sed -i \'\'s/\\r$//\'\' jobs/your_job.slurm && /cm/local/apps/slurm/current/bin/sbatch jobs/your_job.slurm"\'\n'
           '\n'
           '# check status\n'
           'ssh ayman.akash@thunder.ccast.ndsu.edu \'bash -lc "export SLURM_CONF=/cm/shared/apps/slurm/etc/thunder-prod/slurm.conf; /cm/local/apps/slurm/current/bin/squeue -u ayman.akash"\'\n'
           '\n'
           '# read the log\n'
           'ssh ayman.akash@thunder.ccast.ndsu.edu \'bash -lc "tail -n 30 \'\'/mmfs1/scratch/ayman.akash/<project>/myjob.log\'\'"\'\n'
           '\n'
           '# download results when done\n'
           'scp \'ayman.akash@thunder.ccast.ndsu.edu:"/mmfs1/scratch/ayman.akash/<project>/outputs/your_output"\' .')

    d.h2("4.4 Or use the helper")
    d.code('.\\scripts\\ccast.ps1 go       # upload + fix perms + fix line endings + submit\n'
           '.\\scripts\\ccast.ps1 status   # squeue\n'
           '.\\scripts\\ccast.ps1 log      # tail the log\n'
           '.\\scripts\\ccast.ps1 pull     # download outputs to .\\outputs_ccast')

    # ============================================================ context
    d.h1("Context (why this document exists)")
    d.p("This runbook captures a single afternoon's work converting a small chemistry pipeline into "
        "an unattended supercomputer job, and -- more usefully -- everything that went wrong along "
        "the way. The technical goal was modest: run a name-to-structure resolver over a 7,000-name "
        "dataset on CCAST and be notified on my phone when it finished. The real lessons, though, "
        "were operational. CCAST's Thunder cluster runs the Slurm scheduler (not PBS, despite older "
        "documentation and the .pbs examples), so submission uses sbatch and needs the SLURM_CONF "
        "variable and the project account x-ccast-prj-hpirim. Driving the cluster from a Windows PC "
        "adds two recurring traps: zipping or recursively copying from Windows makes remote folders "
        "read-only (breaking new-file uploads and deletions until chmod -R u+rwX), and Windows CRLF "
        "line endings make Slurm reject a script until sed strips the carriage returns. Finally, "
        "because login requires Duo two-factor, the workflow is intentionally 'submit then walk "
        "away': the scheduler keeps the job running after I disconnect, and an ntfy push plus email "
        "tell me when it is done. With the flowcharts and the error dictionary here, I can repeat "
        "this for any future job -- swap in a new your_script.py and your_job.slurm -- without "
        "asking anyone for help.")

    d.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
