"""A student's way through the whole practical, with a mocked model that behaves like a real one:
every button of the instructions, every command they show, the four agent runs, the script made
from a run, the comparison of checksums – and every task must tick itself."""
import sys, json, time, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *

PORT = 8850
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info))
    print(('PASS ' if ok else 'FAIL ') + name + (('  – ' + str(info)[:700]) if info and not ok else ''), flush=True)

H = {'access-control-allow-origin': '*'}
def sse(text):
    k = len(text) // 2
    return ''.join('data: ' + json.dumps({'candidates': [{'content': {'parts': [{'text': t}], 'role': 'model'}, 'index': 0}]}) + '\r\n\r\n' for t in (text[:k], text[k:]))

MM = ["I look at the files first.\n```bash\nls -l data\n```",
      "I map the paired reads with minimap2 (preset for short reads), then sort and index the alignments.\n```bash\nminimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nsamtools sort -o mapped.bam mapped.sam\nsamtools index mapped.bam\n```",
      "Now the variants: pileup and call, then the index.\n```bash\nbcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools index variants.vcf.gz\n```",
      "I look at the position that was asked for, and count the variants.\n```bash\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz\nbcftools view -H variants.vcf.gz | wc -l\n```",
      "REPORT\nMapped with minimap2 2.22 (`-ax sr`), called with bcftools (`mpileup | call -mv`).\n\n- `variants.vcf.gz`: 60 variants\n- human_CYP2C19:11616 G>A, genotype **0/1**, QUAL 222, DP4 = 40,4,46,2\n\nNA12878 is heterozygous for CYP2C19*2 – a poor metaboliser of clopidogrel."]
BT = ["Bowtie 2 needs an index of the reference.\n```bash\nbowtie2-build data/reference.fa ref > build.log 2>&1\n```",
      "Map with Bowtie 2, sort and index.\n```bash\nbowtie2 -x ref -1 data/NA12878_R1.fastq -2 data/NA12878_R2.fastq -S aligned.sam\nsamtools sort -o aligned.bam aligned.sam\nsamtools index aligned.bam\n```",
      "Call the variants and keep those with QUAL of at least 20.\n```bash\nbcftools mpileup -f data/reference.fa aligned.bam | bcftools call -mv -Ob -o raw.bcf\nbcftools view -i 'QUAL>=20' -Oz -o variants.vcf.gz raw.bcf\ntabix -p vcf variants.vcf.gz\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz\n```",
      "REPORT\nBowtie 2 → bcftools, filtered at QUAL ≥ 20. Genotype at 11616: 0/1."]
PLAN1 = "1. Map the reads with `minimap2 -ax sr`.\n2. Sort and index with samtools.\n3. Call variants with bcftools into `variants.vcf.gz`; index it.\n4. Check position 11616."
PLAN2 = "1. Quality control and filtering with `fastp`.\n2. Map the filtered reads with `minimap2 -ax sr`.\n3. Sort and index with samtools.\n4. Call variants with bcftools into `variants.vcf.gz`; index it.\n5. Check position 11616."
PL = ["As planned, quality control first.\n```bash\nfastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o clean_R1.fastq -O clean_R2.fastq -h fastp.html -j fastp.json\n```",
      "Map the filtered reads, sort, index.\n```bash\nminimap2 -ax sr data/reference.fa clean_R1.fastq clean_R2.fastq | samtools sort -o mapped.bam\nsamtools index mapped.bam\n```",
      "Call and index.\n```bash\nbcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools index variants.vcf.gz\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz\n```",
      "REPORT\nFollowed the plan. Genotype 0/1."]
SC = ["I write the whole analysis as one script and run it.\n```file:analysis.sh\n#!/usr/bin/env bash\nset -euo pipefail\n\nREF=data/reference.fa\nSAMPLE=NA12878\n\n# 1. map the reads\nminimap2 -ax sr \"$REF\" data/${SAMPLE}_R1.fastq data/${SAMPLE}_R2.fastq > \"$SAMPLE.sam\"\n\n# 2. sort and index\nsamtools sort -o \"$SAMPLE.bam\" \"$SAMPLE.sam\"\nsamtools index \"$SAMPLE.bam\"\n\n# 3. call the variants\nbcftools mpileup -f \"$REF\" \"$SAMPLE.bam\" | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools index variants.vcf.gz\n\n# 4. the answer\nif [ ! -s variants.vcf.gz ]; then\n  echo \"no variants file\" >&2\n  exit 1\nfi\necho \"Variants: $(bcftools view -H variants.vcf.gz | wc -l)\"\necho \"Genotype at 11616: $(bcftools query -f '[%GT]' -r human_CYP2C19:11616 variants.vcf.gz)\"\n```\n```bash\nbash analysis.sh\n```",
      "REPORT\n`analysis.sh` maps, sorts, calls and prints the answer: 60 variants, genotype 0/1."]
state = {'auto': 0}
requests = []
def gemini(route):
    body = json.loads(route.request.post_data or '{}')
    sysmsg = body.get('system_instruction', {}).get('parts', [{}])[0].get('text', '')
    models = [c for c in body.get('contents', []) if c['role'] == 'model']
    users = [c['parts'][0]['text'] for c in body['contents'] if c['role'] == 'user']
    last = users[-1]
    requests.append({'sys': sysmsg, 'users': users})
    n = len(models)
    if 'single word: ready' in last: text = 'ready'
    elif 'You are an AI agent' in sysmsg:
        if 'Start with a plan' in sysmsg:
            text = PLAN1 if n == 0 else PLAN2 if n == 1 else PL[min(n - 2, len(PL) - 1)]
        elif 'ONE bash script' in sysmsg: text = SC[min(n, len(SC) - 1)]
        elif 'The user sees each of your steps' in sysmsg: text = MM[min(n, len(MM) - 1)]
        else:
            if n == 0: state['auto'] += 1
            text = (MM[1:] if state['auto'] == 1 else BT)[min(n, len(BT) - 1 if state['auto'] != 1 else len(MM) - 2)]
    elif 'My command failed' in last: text = "The file has no index yet. Make one, then ask for the region again:\n\n```bash\nbcftools index variants.vcf.gz\n```"
    elif 'bwa mem' in last: text = "`bwa` is not installed in this terminal, so I cannot give you a command that would work here. Use **minimap2** or **Bowtie 2** instead."
    elif 'How many variants' in last: text = "I cannot see inside your file. Count the lines that are not header lines:\n\n```bash\nbcftools view -H variants.vcf.gz | wc -l\n```"
    elif 'call the variants' in last: text = "Pile up the reads and call the variants, then look at the position:\n\n```bash\nbcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz\n```\n\n`-m` is the calling model, `-v` keeps variant sites only, `-Oz` writes compressed VCF."
    elif 'minimap2' in last: text = "Map, sort and index:\n\n```bash\nminimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nsamtools sort -o mapped.bam mapped.sam\nsamtools index mapped.bam\n```\n\n- `-a` writes SAM, `-x sr` is the preset for short reads."
    else: text = 'I am not sure.'
    route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse(text))

with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw, width=1500, height=1000)
        page.route('https://generativelanguage.googleapis.com/**', gemini)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        ev = lambda js: page.evaluate(js)
        done = lambda t: ev(f"document.querySelector('[data-task=\"{t}\"]').classList.contains('task-done')")
        def idle():
            page.wait_for_function('!MG.app.term.busy', timeout=120000); page.wait_for_timeout(120)
        def enter():
            page.wait_for_timeout(250)
            page.locator('.term-input').press('Enter'); page.wait_for_timeout(150); idle()
        def showme(task, nth=0, run=True):
            """press a 'show me' button of a task, then Enter in the terminal"""
            page.locator(f'[data-task="{task}"] [data-term]').nth(nth).click()
            page.wait_for_function('MG.app.term.input.value.length > 0', timeout=15000)
            page.wait_for_timeout(1200 if len(ev('MG.app.term.input.value')) > 100 else 700)
            if run: enter()
        def last_out(n=6):
            """what the last command printed (everything after the last line that shows a command)"""
            return ev("(() => { const els = Array.from(MG.app.term.outEl.children); let k = els.length - 1; while (k > 0 && !els[k].classList.contains('cmdline')) k--; return els.slice(k + 1).map(e => e.textContent).join('\\n'); })()")
        def chapter(c):
            ev(f"MG.app.showChapter('{c}', true)"); page.wait_for_timeout(300)
        def send_prompt(sel, wait_chat=True):
            page.locator(sel).click(); page.wait_for_timeout(300)
            assert ev('MG.app.ai.input.value.length') > 20
            page.locator('.ai-send').click()
            page.wait_for_timeout(300)
            if wait_chat: page.wait_for_function('!MG.app.ai.busy', timeout=60000); page.wait_for_timeout(200)
        def chat_buttons():
            return page.locator('.ai-thread[data-tab=chat] .ai-msg.assistant').last.locator('.ai-codebox button.primary')
        def tick(task):
            page.locator(f'[data-task="{task}"] .task-check input').check()

        # ---------------- 0 Start here ----------------
        check('first chapter shows the AI tab', ev("MG.app.currentChapter()") == 'start' and ev('MG.app.currentBench') == 'assistant')
        tick('s-open')
        page.fill('.ai-connect [data-k=key]', 'GOOD'); page.click('.ai-connect [data-x=connect]')
        page.wait_for_function('MG.app.ai.connected()', timeout=20000)
        showme('s-help')
        check('0: connect and help tick', done('s-connect') and done('s-help') and 'fastp 0.20.1' in last_out(2), last_out(2)[:300])

        # ---------------- 1 Look first ----------------
        chapter('look')
        check('1: the chapter opens the terminal', ev('MG.app.currentBench') == 'terminal')
        showme('l-ls', 0); showme('l-ls', 1)
        check('1: README is shown', 'position **11,616**' in last_out(3), last_out(3)[-300:])
        showme('l-head'); showme('l-count')
        check('1: 3519 reads counted', last_out(1).strip() == '3519', last_out(2))
        showme('l-ref')
        check('1: two reference sequences', last_out(1).strip() == '>human_CYP2C19\n>human_CYP2C9', last_out(1))
        showme('l-md5')
        check('1: checksums OK, back in the home folder', last_out(1).count(': OK') == 3 and ev('MG.app.fs.cwd') == '/home/student', last_out(1))
        showme('l-fastp')
        check('1: fastp ran', 'reads passed filter: 6170' in last_out(3), last_out(3)[-500:])
        showme('l-report'); page.wait_for_timeout(2500)
        plots = page.frame_locator('iframe.ed-frame').locator('.js-plotly-plot').count()
        check('1: the fastp report opens in Files, with its plots drawn', ev('MG.app.currentBench') == 'editor' and plots >= 8, plots)
        showme('l-json', 0); showme('l-json', 1)
        check('1: jq reads the JSON report', '"q30_rate": 0.820751' in last_out(1), last_out(1)[-300:])
        showme('l-versions')
        check('1: versions', all(x in last_out(1) for x in ['fastp 0.20.1', '2.22-r1101', 'version 2.4.2', 'samtools 1.17', 'bcftools 1.10']), last_out(1))
        t1 = [t for t in ['l-ls', 'l-head', 'l-count', 'l-ref', 'l-md5', 'l-fastp', 'l-report', 'l-json', 'l-versions'] if not done(t)]
        check('1: every task ticked itself', not t1, t1)
        def short(qid, value):
            page.fill(f'[data-q="{qid}"] input[type=text]', value); page.locator(f'[data-q="{qid}"] button:has-text("Check")').click(); page.wait_for_timeout(150)
            return page.locator(f'[data-q="{qid}"] .q-feedback').inner_text()
        check('1: answers 3519 and 6170 are accepted, wrong ones are not', short('l-q1', '3,519').startswith('✓') and short('l-q2', '6170').startswith('✓') and short('l-q1', '7038').startswith('✗') , short('l-q1', '3519'))
        short('l-q1', '3519')

        # ---------------- 2 The assistant ----------------
        chapter('assistant')
        check('2: the chapter opens the AI tab, on Chat', ev('MG.app.currentBench') == 'assistant')
        page.locator('[data-task="a-ask"] [data-term]').click(); page.wait_for_timeout(600); enter()
        ev("MG.app.showWorkbench('assistant')")
        send_prompt('[data-task="a-ask"] [data-prompt]')
        check('2: the answer has commands with a terminal button', chat_buttons().count() == 1 and chat_buttons().first.inner_text() == 'Put command 1 of 3 in the terminal', chat_buttons().all_inner_texts())
        check('2: the first answer does not tick the later question about bwa', done('a-ask') and not done('a-bwa') and not done('a-run'))
        for k in range(3):
            ev("MG.app.showWorkbench('assistant')")
            chat_buttons().first.click(); page.wait_for_timeout(1300); enter()
        showme('a-flagstat')
        check('2: mapped with the assistant’s commands: 96.86 %', '6817 + 0 mapped (96.86%' in last_out(1), last_out(1)[:400])
        ev("MG.app.showWorkbench('assistant')")
        send_prompt('[data-task="a-ask2"] [data-prompt]')
        chat_buttons().first.click(); page.wait_for_timeout(1300); enter()
        ev("MG.app.showWorkbench('assistant')")
        chat_buttons().first.click(); page.wait_for_timeout(1300); enter()
        check('2: the region query fails without an index, and the terminal offers to ask the AI', 'Could not' in last_out(3) or 'index' in last_out(3).lower() and ev("!!document.querySelector('.term-ask')"), last_out(3))
        page.locator('.term-ask').last.click()
        page.wait_for_function("MG.app.currentBench === 'assistant'"); page.wait_for_timeout(500)
        page.wait_for_function('!MG.app.ai.busy', timeout=60000); page.wait_for_timeout(200)
        check('2: the error went to the assistant with the command and its message', 'bcftools view -H -r human_CYP2C19:11616' in requests[-1]['users'][-1] and 'The end of what it printed' in requests[-1]['users'][-1], requests[-1]['users'][-1][-500:])
        chat_buttons().first.click(); page.wait_for_timeout(900); enter()
        tick('a-err')
        showme('a-site')
        check('2: the genotype line', '0/1:255,0,255' in last_out(1) and 'DP4=40,4,46,2' in last_out(1), last_out(1))
        ev("MG.app.showWorkbench('assistant')")
        send_prompt('[data-task="a-count"] [data-prompt]')
        showme('a-count')
        check('2: 60 variants', last_out(1).strip() == '60', last_out(1))
        ev("MG.app.showWorkbench('assistant')")
        send_prompt('[data-task="a-bwa"] [data-prompt]')
        t2 = [t for t in ['a-ask', 'a-run', 'a-flagstat', 'a-ask2', 'a-err', 'a-site', 'a-count', 'a-bwa'] if not done(t)]
        check('2: every task ticked', not t2, t2)
        check('2: 96.86 and 0/1 are accepted', short('a-q1', '96.86%').startswith('✓') and short('a-q2', '0/1').startswith('✓') and short('a-q2', '1/1').startswith('✗'))
        short('a-q2', '0/1')

        # ---------------- 3 The agent ----------------
        chapter('agent')
        def wait_box():
            page.wait_for_selector('.ag-approve .ag-approve-acts', timeout=60000); page.wait_for_timeout(200)
        def finish():
            page.wait_for_function('!MG.app.ai.busy', timeout=240000); page.wait_for_timeout(400)
        send_prompt('[data-task="g-ask-send"] [data-prompt]', wait_chat=False)
        check('3: "do it for me" chose Agent and "Approve each step"', ev('MG.app.ai.tab') == 'agent' and ev('MG.app.ai.agentMode') == 'ask')
        wait_box(); page.fill('.ag-approve input.ag-comment', 'I have looked at the files already'); page.click('.ag-approve button:has-text("Refuse")')
        wait_box(); page.click('.ag-approve button:has-text("Run it")')
        wait_box(); page.click('.ag-approve button:has-text("Run it")')
        wait_box(); page.click('.ag-approve button:has-text("Run, and stop asking")')
        finish()
        card = page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').last
        # from the home folder the command would show the student's own file of chapter 2: that is not the check
        showme('g-ask-check')
        check('3: the check of the report counts only in the run’s folder', ev('MG.app.fs.cwd') == '/home/student' and '0/1:255,0,255' in last_out(1) and not done('g-ask-check'))
        ev("MG.app.showWorkbench('assistant')")
        card.locator('.ag-acts button', has_text='Go to its folder').click(); page.wait_for_timeout(900); enter()
        check('3: "Go to its folder" changes into the run’s folder', ev('MG.app.fs.cwd') == '/home/student/runs/1-approve', ev('MG.app.fs.cwd'))
        showme('g-ask-check')
        t3a = [t for t in ['g-ask-send', 'g-ask-run', 'g-ask-change', 'g-ask-done', 'g-ask-check'] if not done(t)]
        check('3a: approve each step – tasks ticked', not t3a, t3a)
        # the record of run 1 (the model answer of Q3.1 points to it) is not the record of the plan run
        ev("MG.app.showWorkbench('assistant')")
        card.locator('.ag-acts button', has_text='The record').click(); page.wait_for_timeout(700)
        check('3a: … and nothing of the later sections ticked early', not done('g-plan-record') and not done('g-auto-n') and not done('g-auto-cmp'), [t for t in ['g-plan-record', 'g-auto-n', 'g-auto-cmp'] if done(t)])
        ev("MG.app.showWorkbench('assistant')")
        send_prompt('[data-task="g-plan-send"] [data-prompt]', wait_chat=False)
        page.wait_for_selector('.ag-approve textarea.ag-comment', timeout=60000); page.wait_for_timeout(200)
        page.fill('.ag-approve textarea.ag-comment', 'Check the quality of the reads with fastp first, and map the filtered reads.')
        page.click('.ag-approve button:has-text("Ask for changes")')
        page.wait_for_function("document.querySelectorAll('.ag-plan').length >= 2 && !!document.querySelector('.ag-approve')", timeout=60000); page.wait_for_timeout(200)
        page.click('.ag-approve button:has-text("Approve the plan")')
        finish()
        page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').last.locator('.ag-acts button', has_text='The record').click(); page.wait_for_timeout(700)
        t3b = [t for t in ['g-plan-send', 'g-plan-change', 'g-plan-ok', 'g-plan-record'] if not done(t)]
        check('3b: plan first – tasks ticked', not t3b, t3b)
        for task in ['g-auto-1', 'g-auto-2']:
            ev("MG.app.showWorkbench('assistant')")
            send_prompt(f'[data-task="{task}"] [data-prompt]', wait_chat=False); finish()
        showme('g-auto-cmp')
        out = last_out(1)
        runs = {b.split('\n')[0].strip(): b.split('\n')[1:] for b in out.split('== ')[1:]}
        check('3c: for each run the model and the main commands that worked – and nothing else', list(runs) == ['1-approve/', '2-plan/', '3-auto/', '4-auto/']
              and all(r[0] == 'model: gemini-3.8-flash' for r in runs.values())
              and [l.split()[0] for l in runs['1-approve/'][1:] if l] == ['minimap2', 'bcftools']
              and [l.split()[0] for l in runs['2-plan/'][1:] if l] == ['fastp', 'minimap2', 'bcftools']
              and [' '.join(l.split()[:2]) for l in runs['4-auto/'][1:] if l] == ['bowtie2-build data/reference.fa', 'bowtie2 -x', 'bcftools mpileup', 'bcftools view'], out[-1800:])
        showme('g-auto-n')
        out = last_out(1)
        check('3c: variants per run, and the genotype in each', '1-approve/ 60 variants, at 11616: G>A QUAL=222 0/1' in out and '2-plan/ 60 variants' in out and '3-auto/ 60 variants' in out and re.search(r'4-auto/ \d+ variants, at 11616: G>A QUAL=178 0/1', out) is not None, out)
        ev("MG.app.showWorkbench('assistant')")
        # while the agent writes and runs its script, the student reads ahead in chapter 4
        send_prompt('[data-task="g-script-send"] [data-prompt]', wait_chat=False)
        chapter('repro'); ev("MG.app.showWorkbench('assistant')")
        finish()
        check('3d: the script that the agent ran does not tick the student’s “run the script” task', not done('r-run1') and not done('r-run2'), [t for t in ['r-run1', 'r-run2'] if done(t)])
        chapter('agent'); ev("MG.app.showWorkbench('assistant')")
        check('3d: back in chapter 3 the finished run counts', done('g-script-send'))
        card = page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').last
        check('3d: the script ran and printed the answer', 'Genotype at 11616: 0/1' in json.loads(ev("MG.app.fs.get('/home/student/runs/5-script/run.json').text"))['steps'][0]['commands'][0]['output'])
        card.locator('.ag-file button', has_text='Open').click(); page.wait_for_timeout(700)
        t3 = [t for t in ['g-auto-1', 'g-auto-2', 'g-auto-cmp', 'g-auto-n', 'g-script-send', 'g-script-read'] if not done(t)]
        check('3c, 3d: tasks ticked', not t3, t3)

        # ---------------- 4 Make it repeatable ----------------
        chapter('repro')
        ev("MG.app.showWorkbench('assistant')")
        card3 = page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').nth(2)
        check('4: the third card is run 3', 'Run 3' in card3.locator('.ag-head').inner_text())
        card3.locator('.ag-acts button', has_text='The record').click(); page.wait_for_timeout(600)
        ev("MG.app.showWorkbench('assistant')")
        card3.locator('.ag-acts button', has_text='Make a script').click(); page.wait_for_timeout(900)
        sh = ev("MG.app.fs.get('/home/student/runs/3-auto/rerun.sh').text")
        check('4: rerun.sh of the autonomous run', sh.count('\nminimap2 -ax sr') == 1 and 'bcftools index variants.vcf.gz' in sh, sh)
        # tidy the script in the editor: take out a look-only command, save
        ev("""(() => { const cm = MG.app.editor.cm; cm.setValue(cm.getValue().replace('bcftools view -H variants.vcf.gz | wc -l\\n', '')); })()""")
        page.keyboard.press('Control+s'); page.wait_for_timeout(400)
        check('4: the tidied script is saved', 'wc -l' not in ev("MG.app.fs.get('/home/student/runs/3-auto/rerun.sh').text") and done('r-tidy'))
        ev("MG.app.showWorkbench('assistant')")
        card3.locator('.ag-acts button', has_text='Go to its folder').click(); page.wait_for_timeout(900); enter()
        showme('r-run1')
        check('4: the script runs in a new folder', ev('MG.app.fs.cwd') == '/home/student/check1' and ev("MG.app.fs.exists('/home/student/check1/variants.vcf.gz')") and done('r-run1'), last_out(2)[-400:])
        showme('r-run2')
        showme('r-md5')
        sums = [l.split()[0] for l in last_out(1).strip().split('\n')]
        check('4: the two .vcf.gz files differ', len(sums) == 2 and sums[0] != sums[1] and done('r-md5') and not done('r-same'), last_out(1))
        showme('r-diff')
        out = last_out(1)
        check('4: … only in the date of the header', out.count('Date=') == 2 and out.strip().split('\n')[0] == '29c29', out)
        showme('r-same')
        out = last_out(1).strip().split('\n')
        sums = {l.split()[-1]: l.split()[0] for l in out}
        check('4: the variants are the same in both checks and in the run the script came from', sums['/home/student/check1'] == sums['/home/student/check2'] == sums['/home/student/runs/3-auto'] == '547dcc814f0a3f906b1ace9ecc998408' and sums['/home/student/runs/4-auto'] != sums['/home/student/runs/3-auto'] and len(sums) == 7, out)
        # the download button of a run's card is not the download of the test folder
        ev("MG.app.showWorkbench('assistant')")
        with page.expect_download() as dl0:
            card3.locator('.ag-acts button', has_text='Download the folder').click()
        dl0.value.path()
        check('4: downloading a run’s folder does not tick the last step', not done('r-zip'))
        page.locator('[data-task="r-readme"] [data-file-create]').click(); page.wait_for_timeout(700)
        check('4: README.md is created in ~/check1 and opens', ev('MG.app.editor.current') == '/home/student/check1/README.md' and done('r-readme') and not done('r-fill'))
        ev("""(() => { const cm = MG.app.editor.cm; cm.setValue(cm.getValue().replace(/What I did:      \\.\\.\\.   \\(for example: /, 'What I did:      ').replace('Genotype:  ...', 'Genotype:  0/1')); })()""")
        page.keyboard.press('Control+s'); page.wait_for_timeout(500)
        with page.expect_download() as dl:
            page.locator('[data-task="r-zip"] [data-download]').click()
        path = dl.value.path()
        import zipfile
        names = sorted(zipfile.ZipFile(path).namelist())
        check('4: the .zip has data, script, record, results and note', all(x in names for x in ['check1/README.md', 'check1/rerun.sh', 'check1/RUN.md', 'check1/variants.vcf.gz', 'check1/data/reference.fa', 'check1/data/NA12878_R1.fastq', 'check1/mapped.bam']), names)
        t4 = [t for t in ['r-record', 'r-script', 'r-tidy', 'r-run1', 'r-fix', 'r-run2', 'r-md5', 'r-diff', 'r-same', 'r-readme', 'r-fill', 'r-zip'] if not done(t)]
        check('4: every task ticked', not t4, t4)

        # the same test for a "Write a script" run: its analysis.sh is copied as rerun.sh. The folder is there
        # already, with read-only copies of the data – the line must work all the same
        ev("MG.app.showWorkbench('assistant')")
        page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').nth(4).locator('.ag-acts button', has_text='Go to its folder').click(); page.wait_for_timeout(900); enter()
        page.locator('[data-task="r-run1"] details.alt summary').click(); page.wait_for_timeout(200)
        showme('r-run1', 1)
        check('4: the line for a script run works, also a second time', ev('MG.app.fs.cwd') == '/home/student/check1' and 'Genotype at 11616: 0/1' in last_out(1) and ev("MG.app.fs.get('/home/student/check1/rerun.sh').text") == ev("MG.app.fs.get('/home/student/runs/5-script/analysis.sh').text") and ev("MG.app.fs.exists('/home/student/check1/NA12878.bam')"), last_out(1)[-600:])
        showme('r-run2')
        check('4: … and the second folder can be made again from the first', ev('MG.app.fs.cwd') == '/home/student/check2' and 'Genotype at 11616: 0/1' in last_out(1), last_out(1)[-600:])

        # ---------------- the end ----------------
        chapter('ref')
        page.wait_for_timeout(300)
        page.locator('#ref [data-term]').last.click(); page.wait_for_timeout(900); enter()
        check('R: the README of the data can be read from any folder', 'position **11,616**' in last_out(1), last_out(1)[-300:])
        allt = ev("Array.from(document.querySelectorAll('[data-task]')).filter(li => !li.classList.contains('task-done')).map(li => li.dataset.task)")
        check('every task of the practical is done', allt == [], allt)
        check('progress counts tasks and questions', re.match(r'^\d+% done$', page.inner_text('.progress-label')) is not None, page.inner_text('.progress-label'))
        used = len(requests)
        check('requests to the model in the whole walk (a free tier must allow this many)', used < 60, used)
        print('requests:', used)
        bad = [l for l in logs if 'PAGEERROR' in l or (l.startswith('error') and 'Failed to load resource' not in l)]
        # (for information: how much of the browser's small storage the text files of this session take – the limit is 3,500,000)
        print('text files in the saved state:', ev("(() => { const s = MG.project.snapshot(MG.app.fs); return s.entries.filter(e => e.k === 't').length + ' files, ' + s.entries.reduce((n, e) => n + (e.t ? e.t.length : 0), 0) + ' characters; not kept: ' + s.skipped; })()"))
        check('no errors in the page', not bad, bad[:5])
        b.close()
    finally:
        srv.terminate()
    fails = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(fails)} of {len(results)} passed')
    for f in fails:
        print('FAILED:', f[0], '–', str(f[2])[:1500])
