"""The script that the page makes from a run of the agent (rerun.sh), with a mocked Gemini API: runs in which the
agent names its folder in full, changes folder, keeps variables from step to step, reaches outside its folder in ways
that only show when the command runs, goes on where a script with set -eu would stop – and "Write a script" runs that
end without a script.
Each script is run in a fresh folder in the page, and – where bash is at hand – by the bash of this computer: the
files must be the same as in the agent's run."""
import sys, json, time, os, shutil, subprocess, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *

PORT = 8875
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info))
    print(('PASS ' if ok else 'FAIL ') + name + (('  – ' + str(info)[:900]) if info and not ok else ''), flush=True)

H = {'access-control-allow-origin': '*'}
def sse(text):
    k = len(text) // 2
    return ''.join('data: ' + json.dumps({'candidates': [{'content': {'parts': [{'text': t}], 'role': 'model'}, 'index': 0}]}) + '\r\n\r\n' for t in (text[:k], text[k:]))

RUN = '/home/student/runs/1-auto'
FULL = [
    f"Folders, by their full names.\n```bash\nmkdir -p {RUN}/results\ncd {RUN}/results\nhead -8 {RUN}/data/NA12878_R1.fastq > {RUN}/results/first.fastq\n```",
    "Count, from inside the folder.\n```bash\ncd results && wc -l < first.fastq > ../count.txt\n```",
    "A variable, and a folder named by it.\n```bash\nOUT=results2\nmkdir -p $OUT\ncd \"$OUT\" && head -4 ../data/NA12878_R1.fastq > four.fastq\n```",
    "The variable again, in the next step.\n```bash\ncp count.txt $OUT/count_copy.txt\n```",
    "A loop that changes folder.\n```bash\nfor d in s1 s2; do mkdir -p $d && cd $d && echo $d > name.txt; cd ..; done\n```",
    f"A script of my own, run by its full name.\n```file:show.sh\n#!/usr/bin/env bash\necho shown\n```\n```bash\nchmod +x show.sh\n{RUN}/show.sh > shown.txt\n```",
    f"Sorted, with the output named in full.\n```bash\nsort -o{RUN}/sorted.txt results/first.fastq\n```",
    f"Where things are.\n```bash\necho \"saved in {RUN}/results.\" > where.txt\necho '{RUN}' > literal.txt\n```",
    "Let's check, quietly.\n```bash\necho \"Let's count the reference\" && wc -l < data/reference.fa > n.txt\n```",
    "Tidy up beside my folder, in case.\n```bash\ncd \"$OUT\" && rm -f ../../victim.txt\n```",
    "A note of the student's.\n```bash\ncd \"$OUT\" && cat ../../../mine_note.txt > note_copy.txt\n```",
    f"The course data, then back.\n```bash\ncd ~/data && ls > /dev/null\nwc -l < README.md > /dev/null\ncd {RUN} && echo back > back.txt\necho after > after.txt\n```",
    "Patterns that begin with a slash.\n```bash\nawk '/human_CYP2C19/' data/reference.fa | head -1 > name.txt\nsed -n '/^>/p' data/reference.fa > heads.txt\ngrep -c / data/reference.fa > slashes.txt || true\nhead -3 data/reference.fa | cut -d / -f 1 > cut.txt\necho a/b/c | tr / _ > tr.txt\n```",
    # the run's folder inside quotes, in here-documents, in a file, in ${…}
    f"A configuration with quotes, and a script that is written as it is.\n```bash\ncat > config.sh <<EOF\nOUTDIR=\"{RUN}/my results\"\nREF='{RUN}/data/reference.fa'\nEOF\nmkdir -p \"{RUN}/my results\"\n. ./config.sh && head -2 \"$REF\" > \"$OUTDIR/two.txt\"\ncat > go.sh <<'EOF'\n#!/usr/bin/env bash\ncd {RUN}/results\nwc -c < first.fastq > \"$1\"\nEOF\nbash go.sh bytes.txt\n```",
    f"A list of samples.\n```file:samples.tsv\nNA12878\t{RUN}/data/NA12878_R1.fastq\t{RUN}/results/sample_head.txt\tcost: $5 `x` \\n\n```\n```bash\nwhile read -r s r1 o rest; do head -n 4 \"$r1\" > \"$o\"; done < samples.tsv\n```",
    "An early end.\n```bash\necho before > before.txt\nexit 0\necho never > never.txt\n```",
    f"A program that is not here, a default, and a look above my folder.\n```bash\nfastqc data/NA12878_R1.fastq 2> /dev/null || echo \"no fastqc\" > qc.txt\nOUT2=${{OUT2:-{RUN}/results2}}\ncp count.txt \"$OUT2/count_two.txt\"\necho '{RUN}/x' | cut -d/ -f6 > sixth.txt\nfind \"$PWD/..\" -maxdepth 1 -name \"victim*\" -delete\n```",
    "Tilde fences.\n~~~bash\necho tilde > tilde.txt\n~~~",
    "REPORT\nDone.",
]
# a run that has a variable RUN_FOLDER of its own
OWN = [
    "My own variable.\n```bash\nRUN_FOLDER=/home/student/runs/2-auto/out\nmkdir -p $RUN_FOLDER && echo x > $RUN_FOLDER/x.txt\n```",
    "REPORT\nDone.",
]
# "Write a script": the model works step by step and reports – then, asked for the script, writes it
LATE = [
    "First a look.\n```bash\nhead -4 data/NA12878_R1.fastq > a.fastq\n```",
    "REPORT\nDone: a.fastq has the first read.",
    "The script.\n```file:analysis.sh\n#!/usr/bin/env bash\nset -euo pipefail\n# the first read\nhead -4 data/NA12878_R1.fastq > a.fastq\necho made a.fastq\n```\n```bash\nbash analysis.sh\n```",
    "REPORT\nanalysis.sh makes a.fastq, and printed: made a.fastq",
]
# … or does not
NEVER = [
    "First a look.\n```bash\nhead -4 data/NA12878_R1.fastq > a.fastq\n```",
    "REPORT\nDone: a.fastq has the first read.",
    "REPORT\nAs I said: a.fastq has the first read.",
]
# a run in which only a file names the run's folder – a script, whose first line begins with #
ONLYFILE = [
    "A script with full paths, run in a loop.\n```file:scripts/01_first.sh\n#!/usr/bin/env bash\n# takes the first read\nhead -n 4 /home/student/runs/5-auto/data/NA12878_R1.fastq > /home/student/runs/5-auto/first_read.fq\n```\n```bash\nfor s in scripts/*.sh; do bash \"$s\"; done\nwc -l < first_read.fq > n_first.txt\n```",
    "REPORT\nDone.",
]
# A run that went on where a script under "set -eu" stops. The agent's commands run without -e and -u; rerun.sh has
# both. In this run: a command inside a loop fails (grep -c that counts 0), a command ends with status 1 but writes
# the file that the next step reads (diff), a function fails inside a loop, a name has no value, a mistyped command
# fails and leaves nothing, a command tries to compress an input of the run in place (the page keeps a run's inputs as
# they are), and a trap for EXIT is set (the agent's shell does not end: it never runs there).
WENTON = [
    "Two files.\n```bash\nhead -n 8 data/NA12878_R1.fastq > a.fq\nhead -n 12 data/NA12878_R1.fastq > b.fq\n```",
    "Counts per file; one of the patterns is in neither.\n```bash\nfor f in a.fq b.fq; do\n  n=$(grep -c '^@SRR' $f)\n  z=$(grep -c 'ZZZZ' $f)\n  echo \"$f $n $z\"\ndone | tee counts.txt\n```",
    "The difference of the two, in a file.\n```bash\ndiff a.fq b.fq > differences.txt\nwc -l < differences.txt > n_diff.txt\n```",
    "How many lines are only in the second.\n```bash\ngrep -c '^>' differences.txt > n_only_b.txt\n```",
    "A helper, and a setting that is not there.\n```bash\nhas() { grep -q \"$1\" a.fq; }\nfor w in SRR NOPE; do has $w; echo \"$w: $?\"; done > has.txt\necho \"threads: '$THREADS'\" > settings.txt\n```",
    "A typing mistake.\n```bash\ngrpe -c x a.fq\n```",
    "A program that is not here.\n```bash\npython3 -c 'print(6 * 7)' > answer.txt\n```",
    "Without it, then. And the count on the screen as well.\n```bash\necho $((6 * 7)) > answer2.txt\ngrep -c '^@SRR' a.fq | tee /dev/stderr > n_reads.txt\nls $LS_OPTIONS a.fq nosuch.fq 2> /dev/null | cat\necho \"ls ended with ${PIPESTATUS[0]}\" > pst.txt\n```",
    "Shorter names in the reference.\n```bash\nsed -i 's/^>human_/>/' data/reference.fa\ngrep '^>' data/reference.fa > names.txt\ncat > note.txt <<EOF; echo noted >> noted.txt\nnames: $(wc -l < names.txt)\nEOF\n```",
    "Clean up at the end.\n```bash\ntrap 'rm -f a.fq' EXIT\necho done > done.txt\n```",
    "From here on without -e.\n```bash\nset +e\necho \"sample: '$SAMPLE'\" > sample.txt\n```",
    "REPORT\nDone.",
]
# a run in which the agent is strict itself (set -euo pipefail), and commands end where a script would end
STRICT = [
    "Strict from here on.\n```bash\nset -euo pipefail\nhead -n 8 data/NA12878_R1.fastq > a.fq\nhead -n 12 data/NA12878_R1.fastq > b.fq\nmkdir -p counts\nfor p in SRR ZZZZ CCC; do grep -c \"$p\" a.fq > counts/$p.txt; done\n```",
    "What is there, and how the two files differ.\n```bash\nls counts | tr '\\n' ' ' > which.txt\ndiff a.fq b.fq > d.txt\n```",
    "A name that was never set.\n```bash\ntouch s.txt && echo \"sample $SAMPLE\" >> s.txt\n```",
    "Stop when the file is missing.\n```bash\n[ -s nosuch.txt ] || { echo \"nothing yet\" > status.txt; exit 3; }\necho \"not reached\" > nr.txt\n```",
    "A helper that insists on its second argument.\n```bash\nneed() { echo \"checking $1\" >> check.log; : \"${2:?need wants a file}\"; echo \"$1 ok\" >> check.log; }\nneed one\n```",
    "Pattern groups.\n```bash\nmkdir -p tmp && touch tmp/keep.txt tmp/a.tmp tmp/b.tmp\nrm tmp/!(keep.txt)\n```",
    "They need an option.\n```bash\nshopt -s extglob\nmkdir -p tmp && touch tmp/keep.txt tmp/a.tmp tmp/b.tmp\nrm tmp/!(keep.txt)\nls tmp > left.txt\n```",
    "REPORT\nDone.",
]
state = {'script': FULL}
requests = []
def gemini(route):
    req = route.request
    body = json.loads(req.post_data or '{}')
    models = [c for c in body.get('contents', []) if c['role'] == 'model']
    requests.append(body)
    last = body['contents'][-1]['parts'][0]['text']
    if 'single word: ready' in last:
        return route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse('ready'))
    text = state['script'][min(len(models), len(state['script']) - 1)]
    route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse(text))

TASK = 'Take the first reads and count them.'
DATA = os.path.join(ROOT, 'data')

def native(script, name):
    """run the script with the bash of this computer, in a fresh folder that has data/ → (exit status, {file: md5}, the folder)"""
    top = os.path.join(OUT_DIR, 'rerun_native', name)
    shutil.rmtree(top, ignore_errors=True)
    home = os.path.join(top, 'home')
    work = os.path.join(home, 'check')
    os.makedirs(work)
    for d in (os.path.join(home, 'data'), os.path.join(work, 'data')):
        os.makedirs(d)
        for f in ('NA12878_R1.fastq', 'NA12878_R2.fastq', 'reference.fa', 'README.md'):
            shutil.copy(os.path.join(DATA, f), d)
    open(os.path.join(work, 'rerun.sh'), 'w').write(script)
    env = {'HOME': home, 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}
    r = subprocess.run(['/bin/bash', 'rerun.sh'], cwd=work, env=env, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    sums = {}
    for d, _, files in os.walk(work):
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, work)
            if not rel.startswith('data' + os.sep) and rel != 'rerun.sh':
                sums[rel] = hashlib.md5(open(p, 'rb').read()).hexdigest()
    return r, sums, work

with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.route('https://generativelanguage.googleapis.com/**', gemini)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        ev = lambda js: page.evaluate(js)
        ev("MG.app.showWorkbench('assistant')")
        page.wait_for_function('!!MG.app.ai')
        page.fill('.ai-connect [data-k=key]', 'GOOD'); page.click('.ai-connect [data-x=connect]')
        page.wait_for_function('MG.app.ai.connected()', timeout=20000)
        ev("MG.app.ai.showTab('agent')")
        def run_task(mode, script, timeout=240000):
            state['script'] = script
            ev("MG.app.showWorkbench('assistant')")
            n = ev("document.querySelectorAll('.ai-thread[data-tab=agent] .ag:not(.past)').length")
            ev(f"MG.app.ai.setMode('{mode}')")
            page.fill('.ai-input', TASK)
            page.keyboard.press('Enter')
            page.wait_for_function(f"document.querySelectorAll('.ai-thread[data-tab=agent] .ag:not(.past)').length > {n} && !MG.app.ai.busy", timeout=timeout)
            page.wait_for_timeout(300)
            return page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').last
        sums = lambda folder, names: dict(l.split(None, 1)[::-1] for l in term(page, f'cd {folder}; md5sum {names} 2>/dev/null; cd ~')['text'].strip().split('\n') if len(l.split(None, 1)) == 2)

        # ---------------- a run that names its folder in full, changes folder, keeps variables ----------------
        ev("MG.app.fs.writeText('/home/student/mine_note.txt', 'a note of mine\\n')")
        card = run_task('auto', FULL)
        R = json.loads(ev(f"MG.app.fs.get('{RUN}/run.json').text"))
        cmds = [c for s in R['steps'] for c in s['commands']]
        check('the run: every command that ran worked (18 steps, the last one in a fence of tildes)', R['outcome'] == 'done' and len(R['steps']) == 18 and all(c['code'] == 0 for c in cmds if not c.get('skipped')) and ev(f"MG.app.fs.get('{RUN}/tilde.txt').text") == 'tilde\n', [(c['cmd'], c['code']) for c in cmds if c['code'] != 0])
        by = {c['cmd']: c for c in cmds}
        check('the record says where each command started and ended', by[f'head -8 {RUN}/data/NA12878_R1.fastq > {RUN}/results/first.fastq'].get('cwd') == 'results/' and by[f'cd {RUN}/results']['after'] == 'results/' and by['cp count.txt $OUT/count_copy.txt']['after'] == '' and by['wc -l < README.md > /dev/null'].get('cwd') == '~/data', [(c['cmd'], c.get('cwd'), c.get('after')) for c in cmds])
        check('the record names the paths outside the folder that a command used – also when nothing changed there, also for a program', by['cd "$OUT" && rm -f ../../victim.txt'].get('outside') == ['~/runs/victim.txt'] and by['cd "$OUT" && cat ../../../mine_note.txt > note_copy.txt'].get('outside') == ['~/mine_note.txt'] and by['cd "$OUT" && rm -f ../../victim.txt']['undone'] == [] and by['find "$PWD/.." -maxdepth 1 -name "victim*" -delete'].get('outside') == ['~/runs'], [(c['cmd'], c.get('outside')) for c in cmds if c.get('outside')])
        check('… and no others: the course data, /dev/null and patterns are not "outside"', [c['cmd'] for c in cmds if c.get('outside')] == ['cd "$OUT" && rm -f ../../victim.txt', 'cd "$OUT" && cat ../../../mine_note.txt > note_copy.txt', 'find "$PWD/.." -maxdepth 1 -name "victim*" -delete'], [(c['cmd'], c.get('outside')) for c in cmds if c.get('outside')])
        md = ev(f"MG.app.fs.get('{RUN}/RUN.md').text")
        check('RUN.md says so, too', 'it used paths outside the folder: ~/runs/victim.txt' in md and 'it used paths outside the folder: ~/mine_note.txt' in md, [l for l in md.split('\n') if 'outside' in l])
        check('RUN.md lists the programs of a command with an apostrophe in its text', any(p['program'].startswith('head') or 'wc' in p['program'] for p in R['programs']) and any('wc' in p['program'] for p in R['programs']), R['programs'])
        card.locator('.ag-acts button', has_text='Make a script').click(); page.wait_for_timeout(900)
        sh = ev(f"MG.app.fs.get('{RUN}/rerun.sh') && MG.app.fs.get('{RUN}/rerun.sh').text") or ''
        L = sh.split('\n')
        back = 'cd "$RUN_FOLDER"  # added by the page: the agent\'s next step started in the run\'s folder again'
        check('rerun.sh is written (an apostrophe inside "…" does not stop it)', '\necho "Let\'s count the reference" && wc -l < data/reference.fa > n.txt\n' in sh, sh[-1500:])
        check('RUN_FOLDER is set to the folder the script runs in, after set -eu', "\nset -eu\n\n# RUN_FOLDER: the folder this script runs in. It stands where a command of the agent named the run's folder in full\n# (~/runs/1-auto), and where the script goes back to the folder it started in.\nRUN_FOLDER=$PWD\n\n# step 1: " in sh, sh[:2200])
        check('a command that ran in a subfolder and named the run\'s folder in full: every path is from "$RUN_FOLDER"', f'\nmkdir -p "$RUN_FOLDER"/results\ncd "$RUN_FOLDER"/results\nhead -8 "$RUN_FOLDER"/data/NA12878_R1.fastq > "$RUN_FOLDER"/results/first.fastq\n{back}\n' in sh, [l for l in L if 'first.fastq' in l or 'results' in l][:8])
        check('a step that changed folder: the script goes back at its end; no brackets', f'\ncd results && wc -l < first.fastq > ../count.txt\n{back}\n' in sh and '\n(\n' not in sh and '\n)\n' not in sh, [l for l in L if 'count.txt' in l])
        check('cd to a folder named by a variable, then ".." – kept, and the variable holds in the next step', f'\nOUT=results2\nmkdir -p $OUT\ncd "$OUT" && head -4 ../data/NA12878_R1.fastq > four.fastq\n{back}\n\n# step 4: The variable again, in the next step.\ncp count.txt $OUT/count_copy.txt\n' in sh, [l for l in L if 'OUT' in l])
        check('a loop that changes folder and comes back is kept, with nothing added', '\nfor d in s1 s2; do mkdir -p $d && cd $d && echo $d > name.txt; cd ..; done\n\n# step 6' in sh, [l for l in L if 'for d' in l])
        check('a script run by its full name, and an output named in full after an option', '\nchmod +x show.sh\n"$RUN_FOLDER"/show.sh > shown.txt\n' in sh and '\nsort -o"$RUN_FOLDER"/sorted.txt results/first.fastq\n' in sh, [l for l in L if 'show' in l or 'sort' in l])
        check('inside "…" the folder is $RUN_FOLDER; inside \'…\' the quote is closed around "$RUN_FOLDER"', '\necho "saved in $RUN_FOLDER/results." > where.txt\necho "$RUN_FOLDER" > literal.txt\n' in sh and '\necho "$RUN_FOLDER"\'/x\' | cut -d/ -f6 > sixth.txt\n' in sh, [l for l in L if 'where.txt' in l or 'literal' in l or 'sixth' in l])
        check('in a here-document a quote before the folder is a character like any other; a here-document that is taken as it is becomes one that is expanded', '\ncat > config.sh <<EOF\nOUTDIR="$RUN_FOLDER/my results"\nREF=\'$RUN_FOLDER/data/reference.fa\'\nEOF\nmkdir -p "$RUN_FOLDER/my results"\n. ./config.sh && head -2 "$REF" > "$OUTDIR/two.txt"\ncat > go.sh <<EOF\n#!/usr/bin/env bash\ncd $RUN_FOLDER/results\nwc -c < first.fastq > "\\$1"\nEOF\nbash go.sh bytes.txt\n' in sh, [l for l in L if 'config' in l or 'OUTDIR' in l or 'go.sh' in l or 'first.fastq >' in l])
        check('a file that names the run\'s folder is written with $RUN_FOLDER – and a backslash before every other $, ` and \\', "\n# (this file names the run's folder: it is written with $RUN_FOLDER, the folder the script runs in – so every other $, ` and \\ in it has a backslash here)\ncat > samples.tsv <<END_OF_FILE\nNA12878\t$RUN_FOLDER/data/NA12878_R1.fastq\t$RUN_FOLDER/results/sample_head.txt\tcost: \\$5 \\`x\\` \\\\n\nEND_OF_FILE\nwhile read -r s r1 o rest; do head -n 4 \"$r1\" > \"$o\"; done < samples.tsv\n" in sh, [l for l in L if 'samples' in l or 'NA12878\t' in l or 'this file' in l])
        check('"exit" ended the agent\'s block: it is left out of the script, and what came after it was not run', "\necho before > before.txt\n# left out – \"exit\" ended this block of the agent's commands; in a script it would end the script: exit 0\n# not run (exit ended the block): echo never > never.txt\n" in sh and by['exit 0'].get('exited') is True and by['echo never > never.txt'].get('skipped') == 'exit ended the block' and not ev(f"MG.app.fs.exists('{RUN}/never.txt')"), [l for l in L if 'before' in l or 'exit' in l or 'never' in l])
        check('a command that calls a program this terminal does not have is marked; ${NAME:-folder} is $RUN_FOLDER inside', '\n# CHECK: this command calls fastqc, which this terminal does not have. On a computer that has it, the command does more than it did in this run.\nfastqc data/NA12878_R1.fastq 2> /dev/null || echo "no fastqc" > qc.txt\nOUT2=${OUT2:-$RUN_FOLDER/results2}\ncp count.txt "$OUT2/count_two.txt"\n' in sh and sh.count('# CHECK: this command calls') == 1, [l for l in L if 'CHECK' in l or 'OUT2' in l])
        check('find "$PWD/.." is left out: $PWD is the folder the command is in', '\n# left out – it reaches outside the folder ($PWD/..); put it back, with paths inside the folder, if the script needs it: find "$PWD/.." -maxdepth 1 -name "victim*" -delete\n' in sh, [l for l in L if 'find' in l])
        check('a command that used paths outside when it ran is left out – though its text does not show it and nothing was changed', "\n# left out – when it ran it used paths outside the run's folder (~/runs/victim.txt); put it back, with paths inside the folder, if the script needs it: cd \"$OUT\" && rm -f ../../victim.txt\n" in sh and "\n# left out – when it ran it used paths outside the run's folder (~/mine_note.txt); put it back, with paths inside the folder, if the script needs it: cd \"$OUT\" && cat ../../../mine_note.txt > note_copy.txt\n" in sh, [l for l in L if 'victim' in l or 'mine_note' in l])
        check('commands that ran in the course data are in the script, too – with the run\'s folder as "$RUN_FOLDER"', "\n# CHECK: this uses ~/data, the course data of this page. On another computer that folder is not there: use data/ in the folder of the script.\ncd ~/data && ls > /dev/null\nwc -l < README.md > /dev/null\ncd \"$RUN_FOLDER\" && echo back > back.txt\necho after > after.txt\n\n# step 13" in sh, [l for l in L if 'data &&' in l or 'README' in l or 'back' in l or 'after' in l])
        check('patterns that begin with a slash (awk, sed, grep, cut) are no paths: those commands are in the script', "\nawk '/human_CYP2C19/' data/reference.fa | head -1 > name.txt\nsed -n '/^>/p' data/reference.fa > heads.txt\ngrep -c / data/reference.fa > slashes.txt || true\nhead -3 data/reference.fa | cut -d / -f 1 > cut.txt\necho a/b/c | tr / _ > tr.txt\n" in sh and ev(f"MG.app.fs.get('{RUN}/name.txt').text") == '>human_CYP2C19\n' and ev(f"MG.app.fs.get('{RUN}/tr.txt').text") == 'a_b_c\n', [l for l in L if 'name.txt' in l or 'heads' in l or 'slashes' in l or 'cut.txt' in l])
        check('the full name of the run\'s folder is in no command of the script', not [l for l in L if '1-auto' in l and not l.startswith('#')], [l for l in L if '1-auto' in l and not l.startswith('#')])
        check('the script says how many commands are left out', '\n# 4 commands of the run that worked are not in this script: see “left out” below.\nset -eu\n' in sh, [l for l in L if 'not in this script' in l])
        same = 'results/first.fastq count.txt results2/four.fastq results2/count_copy.txt s1/name.txt s2/name.txt show.sh shown.txt sorted.txt n.txt after.txt tilde.txt name.txt heads.txt slashes.txt cut.txt tr.txt back.txt "my results/two.txt" results/bytes.txt results/sample_head.txt before.txt qc.txt results2/count_two.txt'
        ev("MG.app.fs.writeText('/home/student/runs/victim.txt', 'still here\\n')")
        home_before = set(term(page, 'cd ~; ls')['text'].split())
        r = term(page, f'mkdir ~/checkA && cp -r ~/data {RUN}/rerun.sh ~/checkA/ && cd ~/checkA && bash rerun.sh > log.txt 2>&1; echo "status $?"; cd ~')
        in_run, in_new = sums(RUN, same), sums('~/checkA', same)
        check('the script runs in a fresh folder in the page: status 0', r['text'].strip().endswith('status 0'), r['text'] + term(page, 'tail -5 ~/checkA/log.txt')['text'])
        check('… and makes the same files as the agent did, each where it was', len(in_run) == 24 and in_new == in_run, sorted(set(in_run.items()) ^ set(in_new.items())))
        r = term(page, f'cd ~/checkA; cat where.txt literal.txt; ls never.txt results2/note_copy.txt 2>&1 | wc -l; cat ~/runs/victim.txt ~/mine_note.txt; cut -f2,4 samples.tsv; cat config.sh; cd ~')
        home_after = set(term(page, 'cd ~; ls')['text'].split())
        check('… the folder it names is its own – in what it prints and in the files it writes – the commands left out made nothing, and nothing outside it was touched', r['text'].strip().split('\n') == ['saved in /home/student/checkA/results.', '/home/student/checkA', '2', 'still here', 'a note of mine', '/home/student/checkA/data/NA12878_R1.fastq\tcost: $5 `x` \\n', 'OUTDIR="/home/student/checkA/my results"', "REF='/home/student/checkA/data/reference.fa'"] and home_after == home_before | {'checkA'}, (r['text'], sorted(home_after ^ home_before)))
        check('… and the run\'s own folder is as it was', sums(RUN, same) == in_run and not ev(f"MG.app.fs.exists('{RUN}/log.txt')"), sums(RUN, same))
        if os.path.exists('/bin/bash'):
            syn = subprocess.run(['/bin/bash', '-n'], input=sh, capture_output=True, text=True)
            check('bash -n accepts the script', syn.returncode == 0, syn.stderr)
            nr, nsums, nwork = native(sh, 'full')
            want = dict(in_run)
            check('the bash of this computer runs the script, too: status 0', nr.returncode == 0, nr.stderr[-600:])
            check('… and makes the same files, byte for byte', {k: v for k, v in nsums.items() if k not in ('where.txt', 'literal.txt', 'config.sh', 'samples.tsv', 'go.sh', 'sixth.txt')} == want, sorted(set(nsums.items()) ^ set(want.items())))
            check('… the files it writes name its own folder there, too', open(os.path.join(nwork, 'samples.tsv')).read() == f'NA12878\t{nwork}/data/NA12878_R1.fastq\t{nwork}/results/sample_head.txt\tcost: $5 `x` \\n\n' and open(os.path.join(nwork, 'config.sh')).read() == f'OUTDIR="{nwork}/my results"\nREF=\'{nwork}/data/reference.fa\'\n' and open(os.path.join(nwork, 'literal.txt')).read() == nwork + '\n', open(os.path.join(nwork, 'samples.tsv')).read())
            check('… the folder it names is its own there, too', open(os.path.join(nwork, 'where.txt')).read() == f'saved in {nwork}/results.\n', open(os.path.join(nwork, 'where.txt')).read() if os.path.exists(os.path.join(nwork, 'where.txt')) else 'no file')

        # ---------------- a run with a variable RUN_FOLDER of its own ----------------
        card = run_task('auto', OWN)
        ev("MG.app.ai.makeScript(2, '/home/student/runs/2-auto')"); page.wait_for_timeout(700)
        sh2 = ev("MG.app.fs.get('/home/student/runs/2-auto/rerun.sh').text")
        check('a run that has a variable RUN_FOLDER of its own: the page takes another name', '\nRUN_FOLDER_=$PWD\n' in sh2 and '\nRUN_FOLDER="$RUN_FOLDER_"/out\nmkdir -p $RUN_FOLDER && echo x > $RUN_FOLDER/x.txt\n' in sh2 and '\nRUN_FOLDER=$PWD' not in sh2, sh2[-700:])
        r = term(page, 'mkdir ~/checkB && cp ~/runs/2-auto/rerun.sh ~/checkB/ && cd ~/checkB && bash rerun.sh; echo "status $?"; cat out/x.txt; cd ~')
        check('… and that script works', r['text'].strip().split('\n') == ['status 0', 'x'], r['text'])

        # ---------------- "Write a script": a report without the script ----------------
        n0 = len(requests)
        card = run_task('script', LATE)
        R3 = json.loads(ev("MG.app.fs.get('/home/student/runs/3-script/run.json').text"))
        asked = [b for b in requests[n0:] if 'There is no file analysis.sh in your folder' in b['contents'][-1]['parts'][0]['text']]
        check('"Write a script", and the model reports without a script: it is asked for the script, once', len(asked) == 1 and 'file:analysis.sh' in asked[0]['contents'][-1]['parts'][0]['text'], len(asked))
        check('… writes and runs it, and the run ends with its report', R3['outcome'] == 'done' and ev("MG.app.fs.exists('/home/student/runs/3-script/analysis.sh')") and 'analysis.sh makes a.fastq' in R3['report'] and len(R3['steps']) == 2 and R3['steps'][1]['commands'][0]['code'] == 0, (R3['outcome'], R3['report'], len(R3['steps'])))
        check('… the card has no "Make a script" button then: the script is analysis.sh', card.locator('.ag-acts button', has_text='Make a script').count() == 0 and 'did not write the script' not in card.inner_text())
        n0 = len(requests)
        card = run_task('script', NEVER)
        R4 = json.loads(ev("MG.app.fs.get('/home/student/runs/4-script/run.json').text"))
        asked = [b for b in requests[n0:] if 'There is no file analysis.sh in your folder' in b['contents'][-1]['parts'][0]['text']]
        check('a model that still sends no script: asked once, then the run ends', len(asked) == 1 and R4['outcome'] == 'done' and R4['report'].startswith('As I said') and not ev("MG.app.fs.exists('/home/student/runs/4-script/analysis.sh')"), (len(asked), R4['outcome'], R4['report']))
        check('… the card says that there is no script, and offers to make one from the run', 'The agent did not write the script it was asked for (analysis.sh)' in card.inner_text() and card.locator('.ag-acts button', has_text='Make a script').count() == 1, card.inner_text()[-400:])
        card.locator('.ag-acts button', has_text='Make a script').click(); page.wait_for_timeout(800)
        sh4 = ev("MG.app.fs.get('/home/student/runs/4-script/rerun.sh') && MG.app.fs.get('/home/student/runs/4-script/rerun.sh').text") or ''
        check('… which writes rerun.sh – without RUN_FOLDER, which this run does not need', '\nhead -4 data/NA12878_R1.fastq > a.fastq\n' in sh4 and 'RUN_FOLDER' not in sh4, sh4[-500:])
        # ---------------- only a file of the run names the run's folder ----------------
        card = run_task('auto', ONLYFILE)
        ev("MG.app.ai.makeScript(5, '/home/student/runs/5-auto')"); page.wait_for_timeout(700)
        sh5 = ev("MG.app.fs.get('/home/student/runs/5-auto/rerun.sh').text")
        check('a script file that names the run\'s folder: the variable is set, the file is written with it, and the loop that runs it stays', '\nRUN_FOLDER=$PWD\n' in sh5 and '\nmkdir -p scripts\n' in sh5 and '\ncat > scripts/01_first.sh <<END_OF_FILE\n#!/usr/bin/env bash\n# takes the first read\nhead -n 4 $RUN_FOLDER/data/NA12878_R1.fastq > $RUN_FOLDER/first_read.fq\nEND_OF_FILE\nfor s in scripts/*.sh; do bash "$s"; done\nwc -l < first_read.fq > n_first.txt\n' in sh5 and 'CHECK' not in sh5 and 'left out' not in sh5, sh5[-900:])
        r = term(page, 'mkdir ~/checkE && cp -r ~/data ~/runs/5-auto/rerun.sh ~/checkE/ && cd ~/checkE && bash rerun.sh; echo "status $?"; cat n_first.txt; grep -c checkE scripts/01_first.sh; rm ~/runs/5-auto/first_read.fq; bash scripts/01_first.sh; ls ~/runs/5-auto/first_read.fq 2>&1 | grep -c "No such file"; cd ~')
        check('… it works in a fresh folder, and the file written there works in that folder – not in the agent\'s', r['text'].strip().split('\n') == ['status 0', '4', '1', '1'], r['text'])
        if os.path.exists('/bin/bash'):
            nr, nsums, nwork = native(sh5, 'onlyfile')
            check('… with the bash of this computer, too', nr.returncode == 0 and open(os.path.join(nwork, 'n_first.txt')).read().strip() == '4' and nwork in open(os.path.join(nwork, 'scripts/01_first.sh')).read(), (nr.returncode, nr.stderr[-300:]))

        # ---------------- a run that went on where a script with set -eu would stop ----------------
        card = run_task('auto', WENTON)
        R6 = json.loads(ev("MG.app.fs.get('/home/student/runs/6-auto/run.json').text"))
        c6 = {c['cmd'].split('\n')[0]: c for s in R6['steps'] for c in s['commands']}
        check('the record of a run notes where set -e and set -u would have ended it: a command inside a loop that fails, a name without a value',
              c6['for f in a.fq b.fq; do'].get('inner') is True and c6['for f in a.fq b.fq; do']['code'] == 0 and c6['for w in SRR NOPE; do has $w; echo "$w: $?"; done > has.txt'].get('inner') is True
              and c6["echo \"threads: '$THREADS'\" > settings.txt"].get('unset') == ['THREADS'] and not c6['head -n 8 data/NA12878_R1.fastq > a.fq'].get('inner'), {k: {x: v.get(x) for x in ('code', 'inner', 'unset', 'wrote', 'state')} for k, v in c6.items()})
        check('… and what a command that did not end with 0 left behind: diff wrote its file, the mistyped command nothing; the EXIT trap is noted',
              c6['diff a.fq b.fq > differences.txt']['code'] == 1 and c6['diff a.fq b.fq > differences.txt'].get('wrote') == ['differences.txt'] and c6['grpe -c x a.fq']['code'] == 127 and not c6['grpe -c x a.fq'].get('wrote')
              and not c6['grpe -c x a.fq'].get('state') and R6.get('exitTrap') is True, (c6['diff a.fq b.fq > differences.txt'], c6['grpe -c x a.fq'], R6.get('exitTrap')))
        ev("MG.app.ai.makeScript(6, '/home/student/runs/6-auto')"); page.wait_for_timeout(700)
        sh6 = ev("MG.app.fs.get('/home/student/runs/6-auto/rerun.sh').text")
        py = c6["python3 -c 'print(6 * 7)' > answer.txt"]
        check('… and when a command failed for want of a program that this terminal does not have',
              py['code'] == 127 and py.get('here') == ['python3'] and py.get('wrote') == ['answer.txt'] and c6['grpe -c x a.fq'].get('here') == ['grpe'], (py, c6['grpe -c x a.fq']))
        r = term(page, 'cd ~/runs/6-auto && md5sum data/reference.fa ~/data/reference.fa | cut -c 1-32 | uniq | wc -l; head -c 8 data/reference.fa; echo; stat -c %a data/reference.fa; cd ~')
        check('a read-only input of the run is replaced by sed -i as on Linux (the copy keeps its permissions); the course data is as it was',
              c6["sed -i 's/^>human_/>/' data/reference.fa"]['code'] == 0 and r['text'].split() == ['2', '>CYP2C19', '444'] and term(page, 'grep -c "^>human_" ~/data/reference.fa')['text'].strip() == '2', r['text'])
        check('rerun.sh switches -e off around a command inside which a command fails – the loop, and the loop that calls a function',
              "\nset +e  # added by the page: a command inside this one fails, and the agent's run went on\nfor f in a.fq b.fq; do\n  n=$(grep -c '^@SRR' $f)\n  z=$(grep -c 'ZZZZ' $f)\n  echo \"$f $n $z\"\ndone | tee counts.txt\nset -e\n" in sh6
              and "\nhas() { grep -q \"$1\" a.fq; }\nset +e  # added by the page: a command inside this one fails, and the agent's run went on\nfor w in SRR NOPE; do has $w; echo \"$w: $?\"; done > has.txt\nset -e\n" in sh6, sh6[-2200:])
        check('… keeps the command that ended with 1 and wrote a file (the step after it reads the file), and says that the command after it was not run',
              "\nset +e  # added by the page: this command ended with exit status 1 in the agent's run, and left differences.txt behind\ndiff a.fq b.fq > differences.txt\nset -e\n# not run (the command before it failed): wc -l < differences.txt > n_diff.txt\n" in sh6
              and "\ngrep -c '^>' differences.txt > n_only_b.txt\n" in sh6, sh6[-2200:])
        check('… switches -u off where a name has no value, leaves out the command that failed and left nothing, and takes the EXIT trap away',
              "\nset +u  # added by the page: THREADS has no value here, as in the agent's run\necho \"threads: '$THREADS'\" > settings.txt\nset -u\n" in sh6
              and '\n# failed (exit status 127), left out: grpe -c x a.fq\n' in sh6 and "\ntrap - EXIT\n" in sh6 + '\n' and "\ntrap 'rm -f a.fq' EXIT\n" in sh6
              and '# without a value, the script does the same: see "added by the page" below.\nset -eu\n' in sh6, sh6[-1200:])
        check('… leaves out the command that failed because a program is not in this terminal, though it left an (empty) file – on Linux it would do more than it did in the run',
              "\n# failed (exit status 127), left out – this terminal does not have python3 (it left answer.txt behind, which a later command may need). On a computer that has it the command would do more than it did in this run: python3 -c 'print(6 * 7)' > answer.txt\n" in sh6, [l for l in sh6.split('\n') if 'python3' in l])
        check('… keeps tee /dev/stderr; "set -u" comes after the line that asks for PIPESTATUS; the two commands on the line of a here-document stay one piece',
              "\ngrep -c '^@SRR' a.fq | tee /dev/stderr > n_reads.txt\nset +u  # added by the page: LS_OPTIONS has no value here, as in the agent's run\nls $LS_OPTIONS a.fq nosuch.fq 2> /dev/null | cat\necho \"ls ended with ${PIPESTATUS[0]}\" > pst.txt\nset -u\n" in sh6
              and "\nsed -i 's/^>human_/>/' data/reference.fa\ngrep '^>' data/reference.fa > names.txt\ncat > note.txt <<EOF; echo noted >> noted.txt\nnames: $(wc -l < names.txt)\nEOF\n" in sh6, sh6[-1800:])
        check('… and eases -u, not -e, after the agent\'s own "set +e"',
              "\nset +e\nset +u  # added by the page: SAMPLE has no value here, as in the agent's run\necho \"sample: '$SAMPLE'\" > sample.txt\nset -u\n" in sh6, sh6[-700:])
        same6 = 'a.fq b.fq counts.txt differences.txt n_only_b.txt has.txt settings.txt done.txt answer2.txt n_reads.txt pst.txt names.txt note.txt noted.txt sample.txt'
        r = term(page, 'mkdir ~/checkF && cp -r ~/data ~/runs/6-auto/rerun.sh ~/checkF/ && cd ~/checkF && bash rerun.sh > log.txt 2>&1; echo "status $?"; ls n_diff.txt answer.txt 2> /dev/null | wc -l; cat has.txt settings.txt pst.txt noted.txt note.txt; cd ~')
        in_run6, in_new6 = sums('/home/student/runs/6-auto', same6), sums('~/checkF', same6)
        check('the script runs to its end in a fresh folder in the page (status 0), and what it prints into its files is what the run printed',
              r['text'].strip().split('\n') == ['status 0', '0', 'SRR: 0', 'NOPE: 1', "threads: ''", 'ls ended with 2', 'noted', 'names: 2'], r['text'] + term(page, 'tail -5 ~/checkF/log.txt')['text'])
        check('… the files are those of the agent\'s run, a.fq among them (the EXIT trap did not run there either)', len(in_run6) == 15 and in_new6 == in_run6, sorted(set(in_run6.items()) ^ set(in_new6.items())))
        if os.path.exists('/bin/bash'):
            syn = subprocess.run(['/bin/bash', '-n'], input=sh6, capture_output=True, text=True)
            nr, nsums, nwork = native(sh6, 'wenton')
            check('the bash of this computer runs it to its end, too (status 0) – and makes the same files, byte for byte', syn.returncode == 0 and nr.returncode == 0 and {k: v for k, v in nsums.items() if k != 'log.txt'} == in_run6, (syn.stderr, nr.returncode, nr.stderr[-500:], sorted(set(nsums.items()) ^ set(in_run6.items()))))

        # ---------------- a run in which commands ended where a script ends: the agent's own set -e and set -u, exit, ${NAME:?} ----------------
        card = run_task('auto', STRICT)
        R7 = json.loads(ev("MG.app.fs.get('/home/student/runs/7-auto/run.json').text"))
        c7 = {c['cmd'].split('\n')[0]: c for s in R7['steps'] for c in s['commands']}
        loop7, diff7, unset7, exit7, need7 = c7['for p in SRR ZZZZ CCC; do grep -c "$p" a.fq > counts/$p.txt; done'], c7['diff a.fq b.fq > d.txt'], c7['touch s.txt && echo "sample $SAMPLE" >> s.txt'], c7['[ -s nosuch.txt ] || { echo "nothing yet" > status.txt; exit 3; }'], c7['need one']
        check('the record notes what ended a command where a script would end: the agent\'s own set -e (in a loop: at the first pattern that is not found), set -u, exit, ${NAME:?} – and what the command had done by then',
              [loop7['code'], loop7.get('ended'), loop7.get('wrote'), loop7.get('state')] == [1, 'set -e', ['counts/SRR.txt', 'counts/ZZZZ.txt'], ['p']] and [diff7['code'], diff7.get('ended'), diff7.get('wrote')] == [1, 'set -e', ['d.txt']]
              and [unset7['code'], unset7.get('ended'), unset7.get('wrote')] == [1, 'unset', ['s.txt']] and [exit7['code'], exit7.get('ended'), exit7.get('wrote')] == [3, 'exit', ['status.txt']] and [need7['code'], need7.get('ended'), need7.get('wrote')] == [1, 'unset', ['check.log']]
              and c7['echo "not reached" > nr.txt'].get('skipped') == 'the command before it failed', {k: {x: v.get(x) for x in ('code', 'ended', 'wrote', 'state', 'sh', 'skipped')} for k, v in c7.items()})
        check('the agent\'s shell reads commands as a script does: the pattern group !( ) is a syntax error until  shopt -s extglob  (the block is refused); after it, it works',
              [c['cmd'] for s in R7['steps'] for c in s['commands'] if str(c.get('skipped', '')).startswith('bash: syntax error')] == ['mkdir -p tmp && touch tmp/keep.txt tmp/a.tmp tmp/b.tmp\nrm tmp/!(keep.txt)'] and c7['rm tmp/!(keep.txt)']['code'] == 0
              and term(page, 'ls ~/runs/7-auto/tmp; cat ~/runs/7-auto/left.txt')['text'].split() == ['keep.txt', 'keep.txt'], [c for s in R7['steps'] for c in s['commands'] if 'tmp' in c['cmd']])
        ev("MG.app.ai.makeScript(7, '/home/student/runs/7-auto')"); page.wait_for_timeout(700)
        sh7 = ev("MG.app.fs.get('/home/student/runs/7-auto/rerun.sh').text")
        check('rerun.sh lets the loop that set -e cut short run in a subshell, with -e on inside – and says so, and names what is lost with the subshell',
              '\n# added by the page: "set -e" ended this command part-way in the agent\'s run (exit status 1), and the run went on with its next step.\n# A script would end here. So the command runs in a subshell, ( … ), which ends in its place.\n# CHECK: before it ended, the command had set or changed p. That stays in the subshell:\n# a command below that counts on it will not find it.\nset +e\n(\nset -e\nfor p in SRR ZZZZ CCC; do grep -c "$p" a.fq > counts/$p.txt; done\n)\nset -e\n' in sh7, sh7[:2600])
        check('… a line of simple commands that ended with 1 under the agent\'s set -e needs no subshell: "set +e" around it',
              "\nset +e  # added by the page: this command ended with exit status 1 in the agent's run, and left d.txt behind\ndiff a.fq b.fq > d.txt\nset -e\n" in sh7, sh7[-2600:])
        check('… the commands that set -u, exit and ${NAME:?} ended run in subshells, too',
              '\n# added by the page: a name without a value ended this command in the agent\'s run (set -u, or ${NAME:?}), and the run went on with its next step.\n# A script would end here. So the command runs in a subshell, ( … ), which ends in its place.\nset +e\n(\nset -e\ntouch s.txt && echo "sample $SAMPLE" >> s.txt\n)\nset -e\n' in sh7
              and '\n# added by the page: "exit" ended this command in the agent\'s run, and the run went on with its next step.\n# A script would end here. So the command runs in a subshell, ( … ), which ends in its place.\nset +e\n(\nset -e\n[ -s nosuch.txt ] || { echo "nothing yet" > status.txt; exit 3; }\n)\nset -e\n# not run (the command before it failed): echo "not reached" > nr.txt\n' in sh7
              and '\n(\nset -e\nneed one\n)\nset -e\n' in sh7 and '\nshopt -s extglob\nmkdir -p tmp && touch tmp/keep.txt tmp/a.tmp tmp/b.tmp\nrm tmp/!(keep.txt)\nls tmp > left.txt\n' in sh7, sh7[-2600:])
        same7 = 'a.fq b.fq counts/SRR.txt counts/ZZZZ.txt which.txt d.txt s.txt status.txt check.log left.txt tmp/keep.txt'
        r = term(page, 'mkdir ~/checkG && cp -r ~/data ~/runs/7-auto/rerun.sh ~/checkG/ && cd ~/checkG && bash rerun.sh > log.txt 2>&1; echo "status $?"; ls counts/CCC.txt nr.txt tmp/a.tmp 2> /dev/null | wc -l; cat which.txt; echo; cat status.txt check.log; wc -c < s.txt; cd ~')
        in_run7, in_new7 = sums('/home/student/runs/7-auto', same7), sums('~/checkG', same7)
        check('the script runs to its end in a fresh folder in the page (status 0): each of those commands ends where it ended in the run, and the script goes on',
              r['text'].strip().split('\n') == ['status 0', '0', 'SRR.txt ZZZZ.txt ', 'nothing yet', 'checking one', '0'], r['text'] + term(page, 'tail -5 ~/checkG/log.txt')['text'])
        check('… and the files are those of the agent\'s run', len(in_run7) == 11 and in_new7 == in_run7, sorted(set(in_run7.items()) ^ set(in_new7.items())))
        if os.path.exists('/bin/bash'):
            syn = subprocess.run(['/bin/bash', '-O', 'extglob', '-n'], input=sh7, capture_output=True, text=True)  # (-n does not carry out the script's own shopt)
            nr, nsums, nwork = native(sh7, 'strict')
            check('the bash of this computer runs it to its end, too (status 0) – with the same files, byte for byte, and none more', syn.returncode == 0 and nr.returncode == 0 and nsums == in_run7, (syn.stderr, nr.returncode, nr.stderr[-500:], sorted(set(nsums.items()) ^ set(in_run7.items()))))

        # ---------------- which paths a command of the agent is noted to have used ----------------
        # (the page notes every path that the shell works out while a command of the agent runs; a command is left
        # out of the script when one of them is outside the run's folder. A look at the folder above – the row of ".."
        # in ls -la, the folders that mkdir -p walks through – is no use of it.)
        NOTED = """async ([root, lines]) => {
            const T = MG.app.term, out = {};
            await T.exec('mkdir -p ' + root + ' && cd ' + root);
            for (const l of lines) {
                await T.exec(l, { agent: true });
                out[l] = Array.from(T.touched || []).filter((p) => !(p === root || p.startsWith(root + '/')) && !/^\\/(tmp|dev)(\\/|$)/.test(p) && !(p === '/home/student/data' || p.startsWith('/home/student/data/')));
            }
            await T.exec('cd ~');
            return out;
        }"""
        IN = '/home/student/runs/9-inside'
        inside = [f'mkdir -p {IN}/out/deep', 'mkdir -pv x/y/z', 'touch out/a.txt notes.txt', 'ls -la', f'ls -la {IN}', 'ls -lR .', 'realpath .', 'realpath notes.txt', 'cp -r out out2', 'cp --parents out/a.txt x', 'cp -p notes.txt n2.txt', 'mv n2.txt x/', 'rm -rf out2', 'rmdir -p x/y/z', 'find . -type f', f'find {IN} -name "*.txt"', 'du -sh .', 'stat -c %n notes.txt', 'file notes.txt', 'chmod +x notes.txt', 'sha256sum notes.txt > sums.txt', 'sha256sum -c sums.txt', 'tree .', 'cd out && cd -', 'bash -c "ls | wc -l"', 'ls -la ~/data', 'cp ~/data/reference.fa ref.fa']
        noted = page.evaluate(NOTED, [IN, inside])
        check('a command that stays in the run\'s folder is not noted as reaching outside – ls -la (the row of ".."), mkdir -p, realpath and the others, also with the folder named in full', not [l for l in inside if noted[l]], {l: v for l, v in noted.items() if v})
        outside = ['ls ..', 'ls -la ..', 'cat ../victim.txt', 'realpath ..', 'mkdir -p ../9-other', 'touch /home/student/9-outside.txt', 'cp notes.txt ..', 'find .. -maxdepth 1 -name "9-*"', 'cd .. && ls']
        noted = page.evaluate(NOTED, [IN, outside])
        check('… and a command that does reach outside is noted', all(noted[l] for l in outside), [l for l in outside if not noted[l]])
        term(page, 'rm -rf ~/runs/9-inside ~/runs/9-other ~/9-outside.txt ~/runs/notes.txt; cd ~')

        page.reload(); page.wait_for_function('window.MG_READY === true', timeout=30000)
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai'); page.wait_for_timeout(500)
        ev("MG.app.ai.showTab('agent')")
        past = page.locator('.ai-thread[data-tab=agent] .ag.past')
        rows = past.locator('.ag-acts')
        has = [rows.nth(i).locator('button', has_text='Make a script').count() for i in range(rows.count())]
        check('after a reload the earlier runs offer the same: the button for the script run without a script, none for the one with', has == [1, 1, 0, 1, 1, 1, 1], has)

        errors = [l for l in logs if 'PAGEERROR' in l]
        check('no errors in the page', not errors, errors[:5])
        b.close()
    finally:
        srv.terminate()

bad = [r for r in results if not r[1]]
print(f'\n{len(results) - len(bad)} of {len(results)} passed')
for r in bad:
    print('FAILED:', r[0], '–', str(r[2])[:1200])
sys.exit(1 if bad else 0)
