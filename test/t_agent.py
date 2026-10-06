"""The AI panel with a mocked Gemini API: connecting, the chat, and the agent in its four ways of
working – real commands in the terminal, approval, plans, scripts, refusals, undo (also of files
that programs wrote), limits, a command that never ends, Stop, the record of each run and the
script made from it; a service whose models are busy, silent, over a limit or break off; and the
two other services (Anthropic, an OpenAI-compatible one), each with a stand-in of its own."""
import sys, json, time, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *

PORT = 8840
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info))
    print(('PASS ' if ok else 'FAIL ') + name + (('  – ' + str(info)[:600]) if info and not ok else ''), flush=True)

H = {'access-control-allow-origin': '*'}
def sse(text):
    k = len(text) // 2
    return ''.join('data: ' + json.dumps({'candidates': [{'content': {'parts': [{'text': t}], 'role': 'model'}, 'index': 0}]}) + '\r\n\r\n' for t in (text[:k], text[k:]))

AUTO = [
    "First I look at the input files.\n```bash\nls -l data\nhead -4 data/NA12878_R1.fastq\n```",
    "I map the reads with minimap2, then sort and index the alignments.\n```bash\nminimap2 -ax sr -t 4 data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nsamtools sort -@ 2 -o mapped.bam mapped.sam\nsamtools index mapped.bam\n```",
    "Let me look at the folder above, and work in a subfolder.\n```bash\ncd ..\npwd\nls | head -3\n```",
    "A check that will fail.\n```bash\nsamtools nonsense mapped.bam\necho not-run\n```",
    "A note in the home folder.\n```bash\necho hi > ~/outside.txt && rm -f ~/mine.txt\n```",
    "I write down what I did.\n```file:notes.txt\nmapped with minimap2\n```\n```bash\ncat notes.txt\n```",
    "Now I call the variants and look at the position.\n```bash\nbcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools index variants.vcf.gz\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz\n```",
    "REPORT\nI mapped the reads with **minimap2** and called variants with bcftools.\n\n- File: `variants.vcf.gz`\n- Genotype at human_CYP2C19:11616: **0/1** (G>A), QUAL 222\n\n```text\nhuman_CYP2C19 11616 . G A 222\n```",
]
ASK = [
    "I count the reads first.\n```bash\ngrep -c '^+$' data/NA12878_R1.fastq\n```",
    "Now I list everything.\n```bash\nls -la\n```",
    "I delete the SAM file.\n```bash\nrm -f mapped.sam\n```",
    "I make a notes file.\n```file:notes.txt\nfirst line\n```",
    "Then two more commands.\n```bash\necho one\n```",
    "And another.\n```bash\necho two\n```",
    "REPORT\nDone: counted the reads.",
]
PLAN = [
    "1. Map the reads with minimap2 (`-ax sr`) to `mapped.sam`.\n2. Sort and index with samtools.\n3. Call variants with bcftools into `variants.vcf.gz`.\n4. Check position 11616.",
    "1. Trim the reads with fastp.\n2. Map the trimmed reads with minimap2.\n3. Sort, index, call variants.\n4. Check position 11616.",
    "Step 1 of the plan: trim.\n```bash\nfastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o t1.fastq -O t2.fastq -h fastp.html -j fastp.json\n```",
    "REPORT\nTrimmed the reads as planned.",
]
SCRIPT = [
    "I write the script.\n```file:analysis.sh\n#!/usr/bin/env bash\nset -euo pipefail\n# map\nminimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nsamtools sort -o mapped.bam mapped.sam\nsamtools index mapped.bam\n# call\nbcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools index variants.vcf.gz\nif [ ! -s variants.vcf.gz ]; then echo \"no variants file\" >&2; exit 1; fi\necho \"Variants: $(bcftools view -H variants.vcf.gz | wc -l)\"\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz | cut -f 1,2,4,5,10\n```\n```bash\nbash analysis.sh\n```",
    "REPORT\nThe script analysis.sh maps, calls and prints the genotype: 0/1.",
]
LOOP = ["Again.\n```bash\necho step\n```"] * 60
# everything an agent might do to the student's files outside its own folder
OUTSIDE = [
    "A small SAM file of my own.\n```bash\nminimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq 2> /dev/null | head -300 > small.sam\n```",
    "A redirect over the student's SAM file.\n```bash\nseqtk seq -A data/NA12878_R1.fastq > ~/mapped.sam\n```",
    "A program writes over the student's BAM file.\n```bash\nsamtools sort -o ~/mapped.bam small.sam\n```",
    "Remove a file, then run a program.\n```bash\nrm -f ~/keep.bam && samtools --version | head -1\n```",
    "Move a file, then run a program on it.\n```bash\nmv ~/moved_src.bam ~/moved.bam && samtools quickcheck ~/moved.bam && echo moved-ok\n```",
    "A program that removes its input.\n```bash\nbgzip ~/big.sam\n```",
    "Text over a binary file, and a program that reads it.\n```bash\necho hi > ~/over.bam && cat ~/over.bam\n```",
    "Remove a folder of the student's, then run a program.\n```bash\nrm -rf ~/olddir && samtools --version | head -1\n```",
    "A new file outside.\n```bash\nsamtools view -b -o ~/new.bam small.sam && ls ~/new.bam\n```",
    "REPORT\nDone.",
]
# copies that no program has read yet; a folder the last program ran in; commands that open windows
ALIAS = [
    "Text over the original of a copy, read back through <.\n```bash\necho hi > ~/mapped.bam && cat < ~/mapped.bam\n```",
    "A few alignments of my own.\n```bash\nsamtools view -h ~/mapped.bam | head -200 > small2.sam\n```",
    "Write over a file of the student's, then move the result into my folder.\n```bash\nsamtools view -b -o ~/keep.bam small2.sam && mv ~/keep.bam mine2.bam\n```",
    "Count my file.\n```bash\nsamtools view -c mine2.bam\n```",
    "A folder outside, and a program run in it.\n```bash\nmkdir ~/xdir && cd ~/xdir && samtools --version | head -1\n```",
    "An innocent command.\n```bash\nsamtools --version | head -1\n```",
    "A script that opens a window and saves a file to the computer.\n```bash\nprintf 'open small2.sam\\nnano x.txt\\ndownload small2.sam\\necho end\\n' > o.sh && bash o.sh\n```",
    "Copies of my files in a new folder outside.\n```bash\nmkdir -p ~/results/sub && cp small2.sam mine2.bam ~/results/sub/\n```",
    "Another innocent command.\n```bash\nsamtools view -c mine2.bam\n```",
    "REPORT\nDone.",
]
BUSY = ["A slow step.\n```bash\nsleep 5 && echo slept\n```",
        "A file where a task of the student's looks for one.\n```bash\nmkdir -p ~/check2 && echo x > ~/check2/variants.vcf.gz && sleep 3 && echo there\n```",
        "The file that the student is editing.\n```bash\necho agent > ~/mine.txt && echo agent > ~/closed.txt && sleep 4 && rm ~/mine.txt && sleep 1 && echo over\n```",
        "REPORT\nDone."]
# what must not get into a script made from the run
SCRIPTY = [
    "A few reads.\n```bash\nhead -400 data/NA12878_R1.fastq > few.fastq\n```",
    "Tidy up, in case.\n```bash\nrm -f ~/later.txt ~/later.bam\n```",
    "FASTA, with the full path of my folder.\n```bash\nseqtk seq -A few.fastq > ~/runs/14-auto/few.fa && wc -l < ~/runs/14-auto/few.fa\n```",
    "A file with a strange name.\n```file:n.txt;cd;>INJ.txt\nx\n```",
    "Notes in a subfolder.\n```file:notes/a.txt\nhello\n```\n```bash\ncat notes/a.txt\n```",
    "A file below a file.\n```file:notes/a.txt/b.txt\nx\n```",
    "A helper script that looks outside.\n```file:helper.sh\nls ~/runs > /dev/null\necho helped\n```\n```bash\nbash helper.sh\n```",
    # (steps 8 to 12)
    "I go to my folder, by its full path and with a slash at its end.\n```bash\ncd /home/student/runs/14-auto/ && seqtk seq -A few.fastq | head -2 > two.fa\nOUT=~/runs/14-auto/\nwc -l < $OUT/two.fa > lines.txt\n```",
    "A subfolder; the command that goes there also looks at the home folder.\n```bash\nmkdir -p work\ncd work && ls ~ > /dev/null\necho inside > in.txt\ncp ../few.fastq copy.fastq\n```",
    "A pipeline whose first parts find nothing.\n```bash\ncat notes/a.txt | grep -c zzz | cat\nls *.none 2> /dev/null | wc -l\n```",
    "A helper without .sh in its name.\n```file:helper2\nls ~/runs > /dev/null\n```\n```bash\nbash helper2\n```",
    "A file whose name has a space.\n```file:my notes.txt\nx\n```",
    "REPORT\nDone.",
]
HANG = [
    "Three files of my own first.\n```bash\nsamtools view -b -o mine.bam ~/mapped.bam && cp mine.bam own.bam && cp mine.bam gone.bam && mkdir sub && cp mine.bam sub/in.bam && samtools quickcheck own.bam gone.bam sub/in.bam && echo made\n```",
    "Remove, overwrite, append, then a program that never ends.\n```bash\necho hi > mine.bam && rm gone.bam && rm -r sub && samtools view -b -o during.bam own.bam && rm -f ~/keep.bam && echo hi > ~/over.bam && echo junk >> ~/big.sam && rm -rf ~/olddir && awk 'BEGIN { while (1) { } }'\n```",
    "And on.\n```bash\nsamtools view -c ~/mapped.bam && samtools view -c own.bam && cat mine.bam && samtools view -c gone.bam && samtools view -c sub/in.bam && ls during.bam 2>&1 | grep -c 'No such file'\n```",
    "A program that starts just when the time is up.\n```bash\nsleep 7.9 && awk 'BEGIN { while (1) { } }'\n```",
    "Remove my text file.\n```bash\nrm -f mine.bam && ls | wc -l\n```",
    "Back to where I was before.\n```bash\ncd -\n```",
    "REPORT\nDone.",
]
state = {'script': AUTO, 'hang': False}
# What the service does with the next requests for a model ('*': for any model that has nothing of its own left),
# one word for each request; when nothing is left, the model answers. The answers are those of the real service
# (6 October 2026): "busy" is HTTP 503, a limit is HTTP 429 that names the limit and the time to wait.
plan = {}
hold, requests = [], []
def trouble(route, kind, model):
    J = dict(H, **{'content-type': 'application/json'})
    E = {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}
    stream = lambda *events: route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=''.join('data: ' + json.dumps(e) + '\r\n\r\n' for e in events))
    if kind == 'busy':
        return route.fulfill(status=503, headers=J, body=json.dumps({'error': E}))
    if kind in ('day', 'limit', 'long') or kind.startswith('minute:'):
        err = {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details.', 'status': 'RESOURCE_EXHAUSTED', 'details': []}
        if kind == 'day' or kind.startswith('minute:'):
            per, value, delay = ('PerDay', '20', '44788s') if kind == 'day' else ('PerMinute', '5', kind.split(':')[1] + 's')
            err['details'] = [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': f'GenerateRequests{per}PerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': model}, 'quotaValue': value}]},
                              {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': delay}]
        if kind == 'long':    # a time to wait, but no word about which limit
            err['details'] = [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '3600s'}]
        return route.fulfill(status=429, headers=J, body=json.dumps({'error': err}))
    if kind == 'gone':
        return route.fulfill(status=404, headers=J, body=json.dumps({'error': {'code': 404, 'message': f'models/{model} is not found for API version v1beta, or is not supported for generateContent.', 'status': 'NOT_FOUND'}}))
    if kind == 'bad':
        return route.fulfill(status=400, headers=J, body=json.dumps({'error': {'code': 400, 'message': 'Request contains an invalid argument.', 'status': 'INVALID_ARGUMENT'}}))
    if kind == 'drop':        # the connection fails
        return route.abort('failed')
    if kind == 'hang':        # no answer at all
        hold.append(route)
        return
    if kind == 'inner':       # "200 OK", and then an error instead of an answer
        return stream({'error': E})
    if kind == 'malformed':   # the sentence, and then the ```bash block taken for the call of a tool (as the real service sent it)
        return stream({'candidates': [{'content': {'parts': [{'text': 'I look at what is there.'}], 'role': 'model'}, 'index': 0}]},
                      {'candidates': [{'content': {'parts': [{'text': ''}], 'role': 'model'}, 'finishReason': 'MALFORMED_FUNCTION_CALL', 'finishMessage': 'Malformed function call: call:bash ```\necho recovered\nls data | wc -l\n```', 'index': 0}]})
    if kind == 'empty':       # an answer that ends before it has begun
        return stream({'candidates': [{'content': {'role': 'model'}, 'finishReason': 'MALFORMED_FUNCTION_CALL', 'index': 0}]})
    if kind == 'half':        # an answer that begins, and then an error
        return stream({'candidates': [{'content': {'parts': [{'text': 'Half an ans'}], 'role': 'model'}, 'index': 0}]}, {'error': E})
    raise ValueError(kind)
def gemini(route):
    req = route.request
    body = json.loads(req.post_data or '{}')
    models = [c for c in body.get('contents', []) if c['role'] == 'model']
    key = req.headers.get('x-goog-api-key', '')
    model = req.url.split('/models/')[1].split(':')[0]
    requests.append({'t': time.time(), 'model': model, 'body': body, 'key': key})
    if key != 'GOOD':
        return route.fulfill(status=400, headers=dict(H, **{'content-type': 'application/json'}), body=json.dumps({'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT', 'details': [{'reason': 'API_KEY_INVALID'}]}}))
    todo = plan.get(model) or plan.get('*')
    if todo:
        return trouble(route, todo.pop(0), model)
    if state['hang']:
        hold.append(route)
        return
    last = body['contents'][-1]['parts'][0]['text']
    if 'single word: ready' in last:
        return route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse('ready'))
    if state['script'] == 'chat':
        text = "To count the reads, count the lines and divide by four:\n\n```bash\nwc -l data/NA12878_R1.fastq\necho $(( $(wc -l < data/NA12878_R1.fastq) / 4 ))\n```\n\nA script:\n\n```bash\n#!/usr/bin/env bash\nset -euo pipefail\necho hello\n```"
    else:
        text = state['script'][min(len(models), len(state['script']) - 1)]
    route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse(text))

TASK = 'Find the variants of sample NA12878 and tell me the genotype at position 11616 of human_CYP2C19.'

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
        # the chosen model and the models asked after it; what the page remembers about them (model → why, seconds of rest left, limit per day?, its value)
        M = [ev('MG.config.geminiModel')] + ev('MG.config.geminiFallbackModels'); N = len(M)
        mem = lambda: {x[0]: x[1:] for x in ev("[...MG.aiUtil.modelMemory].map(([m, x]) => [m, x.why, isFinite(x.until) ? Math.round((x.until - Date.now()) / 1000) : -1, !!x.daily, x.limit === undefined ? null : x.limit])")}
        forget = lambda: (plan.clear(), ev("MG.aiUtil.modelMemory.clear()"))

        # ---------------- connecting ----------------
        check('not connected at first: the form is shown, the conversation is not', ev("!MG.app.ai.connected() && !document.querySelector('.ai-connect').hidden && document.querySelector('.ai-foot').hidden"))
        check('the form says where the key and the data go', 'Never do this with personal or patient data' in page.inner_text('.ai-connect') and 'aistudio.google.com/apikey' in page.inner_html('.ai-connect'))
        page.click('.ai-connect [data-x=connect]'); page.wait_for_timeout(200)
        check('no key: asked for one', 'Paste an API key' in page.inner_text('.ai-test-out'))
        page.fill('.ai-connect [data-k=key]', 'BAD'); page.click('.ai-connect [data-x=connect]')
        page.wait_for_function("document.querySelector('.ai-test-out').textContent.startsWith('✗')", timeout=20000)
        check('a wrong key is reported, and nothing is saved', 'API key was not accepted' in page.inner_text('.ai-test-out') and not ev('MG.app.ai.connected()') and ev("sessionStorage.getItem('agents-ai-key')") is None, page.inner_text('.ai-test-out'))
        page.fill('.ai-connect [data-k=key]', 'GOOD'); page.click('.ai-connect [data-x=connect]')
        page.wait_for_function('MG.app.ai.connected()', timeout=20000)
        check('a good key connects: the chat appears', ev("document.querySelector('.ai-connect').hidden && !document.querySelector('.ai-foot').hidden && !document.querySelector('.ai-thread[data-tab=chat]').hidden"))
        check('the key is in sessionStorage only', ev("sessionStorage.getItem('agents-ai-key')") == 'GOOD' and 'GOOD' not in ev('JSON.stringify(Object.assign({}, localStorage))'))
        check('the task "connect" is ticked', ev("document.querySelector('[data-task=s-connect]').classList.contains('task-done')"))
        check('the status shows the model', 'gemini-3.8-flash' in page.inner_text('.ai-status'))

        # ---------------- chat ----------------
        state['script'] = 'chat'
        ev("MG.app.showChapter('assistant', true)"); page.wait_for_timeout(300)
        page.click('#assistant [data-prompt][data-tab=chat]'); page.wait_for_timeout(200)
        check('a prompt button fills the box (it is not sent)', ev("MG.app.ai.input.value").startswith('I have paired-end Illumina reads') and len([r for r in requests if 'I have paired-end' in json.dumps(r['body'])]) == 0)
        page.keyboard.press('Enter')
        page.wait_for_function("!MG.app.ai.busy && document.querySelectorAll('.ai-thread[data-tab=chat] .ai-codebox').length >= 2", timeout=20000)
        sent = requests[-1]['body']
        sysmsg = sent['system_instruction']['parts'][0]['text']
        check('the chat is told about the terminal', 'fastp 0.20.1' in sysmsg and 'bowtie2 2.4.2' in sysmsg and 'You cannot run anything' in sysmsg, sysmsg[:400])
        check('the question carries the folder and the file names', '~/data/NA12878_R1.fastq' in sent['contents'][-1]['parts'][0]['text'] and 'The student is in the folder ~' in sent['contents'][-1]['parts'][0]['text'])
        btns = page.locator('.ai-thread[data-tab=chat] .ai-codebox').first.locator('button').all_inner_texts()
        check('commands can be put in the terminal one at a time', btns[0] == 'Put command 1 of 2 in the terminal', btns)
        page.locator('.ai-thread[data-tab=chat] .ai-codebox').first.locator('button').first.click(); page.wait_for_timeout(900)
        check('… the command is typed, not run', ev('MG.app.term.input.value') == 'wc -l data/NA12878_R1.fastq' and ev('MG.app.currentBench') == 'terminal', ev('MG.app.term.input.value'))
        ev("MG.app.showWorkbench('assistant')")
        btns2 = page.locator('.ai-thread[data-tab=chat] .ai-codebox').nth(1).locator('button').all_inner_texts()
        check('a script can be saved as a file', 'Save as a file…' in btns2, btns2)

        # ---------------- the agent: autonomous ----------------
        ev("MG.app.fs.writeText('/home/student/mine.txt', 'mine\\n')")
        ev("MG.app.ai.showTab('agent')")
        def run_task(mode, script, wait=True, timeout=240000):
            state['script'] = script
            n = ev("document.querySelectorAll('.ai-thread[data-tab=agent] .ag:not(.past)').length")
            ev(f"MG.app.ai.setMode('{mode}')")
            page.fill('.ai-input', TASK)
            page.keyboard.press('Enter')
            if wait:
                page.wait_for_function(f"document.querySelectorAll('.ai-thread[data-tab=agent] .ag:not(.past)').length > {n} && !MG.app.ai.busy", timeout=timeout)
                page.wait_for_timeout(300)
            return page.locator('.ai-thread[data-tab=agent] .ag:not(.past)').last
        cwd0 = ev('MG.app.fs.cwd')
        card = run_task('auto', AUTO)
        text = card.inner_text()
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/1-auto/run.json').text"))
        md = ev("MG.app.fs.get('/home/student/runs/1-auto/RUN.md').text")
        check('auto: the run finishes with the report', 'finished' in card.locator('.ag-head').inner_text() and 'Genotype at human_CYP2C19:11616' in text, card.locator('.ag-head').inner_text())
        check('auto: its folder has the data, read-only', ev("['NA12878_R1.fastq','NA12878_R2.fastq','reference.fa'].every(f => MG.app.fs.get('/home/student/runs/1-auto/data/' + f).readonly)"))
        check('auto: real programs ran – the variants file exists and has the genotype', ev("MG.app.fs.exists('/home/student/runs/1-auto/variants.vcf.gz')") and any('0/1:255,0,255' in c['output'] for s in R['steps'] for c in s['commands']), [c['output'][-200:] for s in R['steps'] for c in s['commands']][-1:])
        check('auto: each command of a block is run and recorded on its own', [len(s['commands']) for s in R['steps']] == [2, 3, 3, 2, 1, 1, 3], [len(s['commands']) for s in R['steps']])
        check('auto: thread options are dropped by the terminal, and the model is told', 'left out' in R['steps'][1]['commands'][0]['output'] and R['steps'][1]['commands'][0]['code'] == 0, R['steps'][1]['commands'][0]['output'][:200])
        c2 = R['steps'][2]['commands']
        check('auto: a cd lasts for the step – and only for the step', c2[0]['code'] == 0 and c2[1]['output'].strip() == '/home/student/runs' and c2[1].get('cwd') == '~/runs' and R['steps'][2].get('cd') is True and not R['steps'][3]['commands'][0].get('cwd'), R['steps'][2])
        check('auto: a failing command stops the rest of its block', R['steps'][3]['commands'][0]['code'] == 1 and R['steps'][3]['commands'][1]['skipped'] == 'the command before it failed', R['steps'][3])
        check('auto: changes outside its folder are undone', not ev("MG.app.fs.exists('/home/student/outside.txt')") and ev("MG.app.fs.get('/home/student/mine.txt').text") == 'mine\n' and '~/outside.txt' in R['steps'][4]['commands'][0]['undone'], R['steps'][4])
        check('auto: a file block writes the file, then the commands run', R['steps'][5]['file']['name'] == 'notes.txt' and ev("MG.app.fs.get('/home/student/runs/1-auto/notes.txt').text") == 'mapped with minimap2\n' and R['steps'][5]['commands'][0]['output'] == 'mapped with minimap2')
        users = [c['parts'][0]['text'] for c in requests[-1]['body']['contents'] if c['role'] == 'user']
        check('auto: the model gets exit status and output of each command', '$ ls -l data\n[exit status 0' in users[1] and 'NA12878_R1.fastq' in users[1] and '[not run, because the command before failed: echo not-run]' in users[4] and '$ pwd\n[exit status 0, 0.0 s, in ~/runs]\n/home/student/runs' in users[3] and 'The next step starts in your folder again' in users[3], users[3][:400])
        check('auto: the model is told the rules', 'REPORT' in requests[-1]['body']['system_instruction']['parts'][0]['text'] and 'at most 20 steps' in requests[-1]['body']['system_instruction']['parts'][0]['text'])
        hist = ev('MG.app.term.shell.history.join("\\n")')
        check('auto: the agent\'s commands are not in the student\'s command history', 'samtools nonsense' not in hist and 'rm -f ~/mine.txt' not in hist and 'wc -l data/NA12878_R1.fastq' not in hist, hist[-300:])
        check('auto: the terminal is back where it was, and unlocked', ev('MG.app.fs.cwd') == cwd0 and not ev('MG.app.term.locked') and not ev('MG.app.term.input.disabled'))
        check('record: RUN.md has task, model, commands, programs and checksums', all(x in md for x in ['# Run 1: an AI agent, autonomous', TASK, 'gemini-3.8-flash', '```bash\nsamtools index mapped.bam\n```', '- minimap2 2.22', '- samtools 1.17', '- bcftools 1.10', '| data/reference.fa | 56963 | d9155e00b786f74b0837f6a675483563 |', '| variants.vcf.gz |', 'written by the page']), md[:1500])
        check('record: the report is quoted, and what failed is there too', '> - Genotype at human_CYP2C19:11616: **0/1**' in md and 'exit status 1' in md and '· in ~/runs' in md)
        check('record: run.json lists programs and files', [p['program'] for p in R['programs']][:3] == ['minimap2', 'samtools', 'bcftools'] and any(o['path'] == 'mapped.bam' and len(o['md5']) == 32 for o in R['outputs']) and len(R['inputs']) == 3, R['programs'])
        check('the tutorial hears about the run', ev("MG.app.ai.runs.length") == 1 and ev("MG.app.ai.runs[0].outcome") == 'done')
        # a script from the run
        card.locator('.ag-acts button', has_text='Make a script').click(); page.wait_for_timeout(800)
        sh = ev("MG.app.fs.get('/home/student/runs/1-auto/rerun.sh').text")
        check('rerun.sh: the commands that worked, in order; the others as comments', '\nset -eu\n' in sh and 'pipefail"' in sh and '\nminimap2 -ax sr -t 4 data/reference.fa' in sh and '# failed (exit status 1), left out: samtools nonsense mapped.bam' in sh and "cat > notes.txt <<'END_OF_FILE'\nmapped with minimap2\nEND_OF_FILE" in sh, sh)
        check('rerun.sh: commands that left the folder are not part of the script', '# left out – it reaches outside the folder (..)' in sh and "# left out – it ran outside the run's folder (in ~/runs): pwd" in sh and '\npwd\n' not in sh and '# 4 commands of the run that worked are not in this script: see “left out” below.' in sh, [l for l in sh.split('\n') if 'left out' in l])
        check('rerun.sh: a command whose changes outside the folder were put back is not part of the script', "# left out – it changed files outside the run's folder (~/outside.txt, ~/mine.txt), which the page put back: echo hi > ~/outside.txt && rm -f ~/mine.txt" in sh and '\necho hi > ~/outside.txt' not in sh, [l for l in sh.split('\n') if 'outside' in l])
        check('rerun.sh opens in the Files tab', ev('MG.app.currentBench') == 'editor' and ev('MG.app.editor.current') == '/home/student/runs/1-auto/rerun.sh')
        r = term(page, 'mkdir ~/check && cp -r ~/data ~/check/ && cp ~/runs/1-auto/rerun.sh ~/check/ && cd ~/check && bash rerun.sh > log.txt 2>&1; echo "exit $?"; bcftools view -H variants.vcf.gz | md5sum; bcftools view -H ~/runs/1-auto/variants.vcf.gz | md5sum; cd ~')
        lines = r['text'].strip().split('\n')
        check('rerun.sh runs in a fresh folder and gives the same variants', 'exit 0' in lines and lines[-1] == lines[-2] and len(lines[-1]) > 32, r['text'][-600:])
        check('… and leaves the student\'s other files alone', ev("MG.app.fs.get('/home/student/mine.txt').text") == 'mine\n' and not ev("MG.app.fs.exists('/home/student/outside.txt')"))

        # ---------------- approve each step ----------------
        ev("MG.app.showWorkbench('assistant')")
        card = run_task('ask', ASK, wait=False)
        def wait_box():
            page.wait_for_selector('.ag-approve .ag-approve-acts', timeout=30000); page.wait_for_timeout(150)
        wait_box()
        check('ask: nothing runs before the student decides', ev("MG.app.term.locked") and "grep -c '^+$'" in page.input_value('.ag-approve textarea.ag-edit') and not ev("Array.from(MG.app.term.outEl.children).slice(-3).some(e => /grep -c/.test(e.textContent))"))
        page.click('.ag-approve button:has-text("Run it")')
        wait_box()
        page.fill('.ag-approve textarea.ag-edit', 'ls -l data')
        page.fill('.ag-approve input.ag-comment', 'only the data folder')
        page.click('.ag-approve button:has-text("Run it")')
        wait_box()
        page.fill('.ag-approve input.ag-comment', 'keep the SAM file')
        page.click('.ag-approve button:has-text("Refuse")')
        wait_box()
        check('ask: a file is shown before it is written', 'write the file notes.txt' in page.inner_text('.ag-approve') and page.input_value('.ag-approve textarea.ag-edit') == 'first line\n')
        page.click('.ag-approve button:has-text("Write it")')
        wait_box()
        page.click('.ag-approve button:has-text("Run, and stop asking")')
        page.wait_for_function('!MG.app.ai.busy', timeout=60000); page.wait_for_timeout(300)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/2-approve/run.json').text"))
        md = ev("MG.app.fs.get('/home/student/runs/2-approve/RUN.md').text")
        check('ask: run, changed, refused, written, all', [s['approval'] for s in R['steps']] == ['run', 'run', 'refused', 'run', 'all', None] and 'edited' in R['steps'][1] and R['steps'][1]['commands'][0]['cmd'] == 'ls -l data' and R['steps'][2]['commands'][0]['skipped'] == 'refused by the user', [(s['approval'], s.get('edited')) for s in R['steps']])
        users = [c['parts'][0]['text'] for c in requests[-1]['body']['contents'] if c['role'] == 'user']
        check('ask: the model is told what the student did', 'The user changed this step before it ran' in users[2] and 'only the data folder' in users[2] and '$ ls -l data' in users[2] and 'did not allow this step' in users[3] and 'keep the SAM file' in users[3], users[2][:300] + ' || ' + users[3][:200])
        check('ask: the record says who decided what', 'The user changed this step before it ran. Comment: “only the data folder”' in md and 'What the agent had proposed:' in md and 'The user refused this step. Comment: “keep the SAM file”' in md and 'all later steps without asking' in md, md[:100])
        check('ask: 3519 reads counted by the real grep', R['steps'][0]['commands'][0]['output'] == '3519', R['steps'][0]['commands'][0])

        # ---------------- plan first ----------------
        card = run_task('plan', PLAN, wait=False)
        page.wait_for_selector('.ag-approve .ag-comment', timeout=30000); page.wait_for_timeout(150)
        check('plan: the plan is shown and nothing has run', 'Map the reads with minimap2' in card.inner_text() and not ev("MG.app.fs.exists('/home/student/runs/3-plan/fastp.json')"))
        page.click('.ag-approve button:has-text("Ask for changes")'); page.wait_for_timeout(200)
        check('plan: changes need words', ev("!!document.querySelector('.ag-approve')"))
        page.fill('.ag-approve textarea.ag-comment', 'Trim the reads with fastp first.')
        page.click('.ag-approve button:has-text("Ask for changes")')
        page.wait_for_function("document.querySelectorAll('.ag-plan').length >= 2 && !!document.querySelector('.ag-approve')", timeout=30000); page.wait_for_timeout(150)
        page.click('.ag-approve button:has-text("Approve the plan")')
        page.wait_for_function('!MG.app.ai.busy', timeout=120000); page.wait_for_timeout(300)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/3-plan/run.json').text"))
        md = ev("MG.app.fs.get('/home/student/runs/3-plan/RUN.md').text")
        check('plan: revised once, approved, then carried out', R['planRounds'] == 2 and R['planChanges'] == ['Trim the reads with fastp first.'] and R['plan'].startswith('1. Trim the reads') and len(R['steps']) == 1 and R['steps'][0]['commands'][0]['code'] == 0, R)
        check('plan: PLAN.md and the record hold the plan', 'Trim the reads with fastp' in ev("MG.app.fs.get('/home/student/runs/3-plan/PLAN.md').text") and '## The plan' in md and '“Trim the reads with fastp first.”' in md and '- fastp 0.20.1' in md)
        users = [c['parts'][0]['text'] for c in requests[-1]['body']['contents'] if c['role'] == 'user']
        check('plan: the model is told of the change and of the approval', 'asks you to change the plan: Trim the reads with fastp first.' in users[1] and 'approved this plan' in users[2], users[1:3])
        check('plan: the system prompt asks for a plan first', 'Start with a plan, and run nothing yet' in requests[-1]['body']['system_instruction']['parts'][0]['text'])

        # ---------------- write a script ----------------
        card = run_task('script', SCRIPT)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/4-script/run.json').text"))
        out = R['steps'][0]['commands'][0]['output']
        check('script: analysis.sh is written and runs (if, $( ), pipes)', R['steps'][0]['file']['name'] == 'analysis.sh' and R['steps'][0]['commands'][0]['code'] == 0 and 'Variants: 60' in out and out.strip().endswith('0/1:255,0,255'), out[-300:])
        check('script: the record names the programs the script used', [p['program'] for p in R['programs']][:3] == ['minimap2', 'samtools', 'bcftools'], R['programs'])
        check('script: no "make a script" button – the script is the result', card.locator('.ag-acts button').all_inner_texts() == ['The record (RUN.md)', 'Go to its folder', 'Download the folder'], card.locator('.ag-acts button').all_inner_texts())
        check('script: the system prompt asks for analysis.sh', 'ONE bash script, analysis.sh' in requests[-1]['body']['system_instruction']['parts'][0]['text'])

        # ---------------- limits, waiting, errors, Stop ----------------
        ev("MG.config.agentMaxSteps = 20")
        card = run_task('auto', LOOP, timeout=300000)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/5-auto/run.json').text"))
        check('limit: the run stops after 20 steps, with a last request for the report', R['outcome'] == 'limit' and len(R['steps']) == 20 and R['requests'] == 21 and 'used all 20 steps' in [c['parts'][0]['text'] for c in requests[-1]['body']['contents'] if c['role'] == 'user'][-1], (R['outcome'], len(R['steps']), R['requests']))
        plan['*'] = ['minute:5'] * N  # every model is over its limit per minute, once
        t0 = time.time()
        card = run_task('auto', ["REPORT\nNothing to do."], timeout=120000)
        waited = time.time() - t0
        check('429: the agent waits as long as the service asks, then goes on', 4 < waited < 40 and 'finished' in card.locator('.ag-head').inner_text() and len(requests[-1]['body']['contents']) == 1, waited)
        forget(); plan['*'] = ['day'] * N     # … and over its limit for today: waiting cannot mend that
        t0 = time.time()
        card = run_task('auto', AUTO, timeout=120000)
        took = time.time() - t0
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/7-auto/run.json').text"))
        check('error: an error of the service that waiting cannot mend ends the run at once, and is recorded', R['outcome'] == 'error' and 'HTTP 429' in R['error'] and 'No requests are left for today' in R['error'] and took < 15 and 'error' in card.locator('.ag-head').inner_text() and 'There is no report' in ev("MG.app.fs.get('/home/student/runs/7-auto/RUN.md').text"), (took, R['error'][:300]))
        forget()
        state['hang'] = True
        card = run_task('auto', AUTO, wait=False)
        page.wait_for_timeout(1500)
        check('while it runs: the terminal is locked and the button says Stop', ev('MG.app.term.locked') and 'Stop' in page.inner_text('.ai-send'))
        page.click('.ai-send')
        page.wait_for_function('!MG.app.ai.busy', timeout=20000)
        state['hang'] = False
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/8-auto/run.json').text"))
        check('Stop: the run ends as stopped, the terminal is free again', R['outcome'] == 'stopped' and not ev('MG.app.term.locked') and ev('MG.app.fs.cwd') == cwd0, R['outcome'])
        # Stop while waiting for approval
        card = run_task('ask', ASK, wait=False)
        wait_box()
        page.click('.ai-send')
        page.wait_for_function('!MG.app.ai.busy', timeout=20000)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/9-approve/run.json').text"))
        check('Stop while a step waits for approval: nothing ran', R['outcome'] == 'stopped' and R['steps'] == [] and not ev("!!document.querySelector('.ag-approve')"), R['steps'])

        # ---------------- the agent's shell is its own ----------------
        term(page, 'cd ~; STUDENTVAR=abc; myfn() { echo "student function"; }; set -u')
        STATE = [
            "I set things up.\n```bash\nset -euo pipefail\nexport AGENTVAR=1\nagentfn() { echo x; }\necho \"student var: [${STUDENTVAR:-unset}]\"\ntype myfn > /dev/null 2>&1 && echo \"has student function\" || echo \"no student function\"\n```",
            "Long output.\n```bash\nseq 1 2000\n```",
            "REPORT\nDone.",
        ]
        card = run_task('auto', STATE, timeout=120000)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/10-auto/run.json').text"))
        out0 = '\n'.join(c['output'] for c in R['steps'][0]['commands'])
        check('the agent starts with a new shell: no variables or functions of the student', 'student var: [unset]' in out0 and 'no student function' in out0, out0)
        r = term(page, 'echo "[${AGENTVAR:-}] [$STUDENTVAR]"; myfn; type agentfn 2>&1 | head -1; false; echo "after false"; echo "$-" | grep -c e; echo "${NOT_SET_X}" 2>&1 | head -1')
        check('… and leaves the student\'s shell as it was (variables, functions, options)', r['text'].split('\n')[0] == '[] [abc]' and 'student function' in r['text'] and 'after false' in r['text'] and 'NOT_SET_X: unbound variable' in r['text'] and 'not found' in r['text'], r['text'])
        term(page, 'set +u')
        sent = [x for x in requests if x['body']['contents'][0]['parts'][0]['text'] == TASK][-1]['body']['contents']
        long_msg = [c['parts'][0]['text'] for c in sent if c['role'] == 'user' and 'seq 1 2000' in c['parts'][0]['text']][-1]
        check('long output reaches the model with its beginning and its end', '\n1\n2\n3\n' in long_msg and '1999\n2000' in long_msg and 'characters left out here' in long_msg and len(long_msg) < 3600, long_msg[:300] + ' … ' + long_msg[-200:])

        # ---------------- outside its folder: also what programs wrote is put back, byte for byte ----------------
        MINE = 'mapped.sam mapped.bam keep.bam moved_src.bam over.bam big.sam olddir/in.bam olddir/note.txt'
        r = term(page, 'cd ~; minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam 2> /dev/null; samtools sort -o mapped.bam mapped.sam; cp mapped.bam keep.bam; cp mapped.bam moved_src.bam; cp mapped.bam over.bam; cp mapped.sam big.sam; mkdir olddir; cp mapped.bam olddir/in.bam; echo note > olddir/note.txt; samtools quickcheck keep.bam moved_src.bam over.bam olddir/in.bam; md5sum ' + MINE)
        before = r['text'].strip().split('\n')[-8:]
        kinds = ev("['mapped.sam','mapped.bam','keep.bam','moved_src.bam','over.bam','big.sam','olddir/in.bam'].map(f => MG.app.fs.get('/home/student/' + f).kind).join(',')")
        check('outside: the student has files that live in the programs\' memory only', kinds == ','.join(['aioli'] * 7) and len(before) == 8 and all(len(l.split()[0]) == 32 for l in before), (kinds, before))
        ev("MG.app.showWorkbench('assistant')")
        card = run_task('auto', OUTSIDE, timeout=180000)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/11-auto/run.json').text"))
        und = [c.get('undone') for s in R['steps'] for c in s['commands']]
        check('outside: each change is undone and reported – to the student, the record and the model', und[0] == [] and all(u for u in und[1:]) and '~/mapped.bam' in und[2] and set(und[4]) == {'~/moved.bam', '~/moved_src.bam'} and set(und[5]) == {'~/big.sam.gz', '~/big.sam'} and '~/olddir/in.bam' in und[7] and und[8] == ['~/new.bam']
              and 'changes outside the folder were undone: ~/mapped.bam' in ev("MG.app.fs.get('/home/student/runs/11-auto/RUN.md').text")
              and 'your changes outside your folder were undone: ~/mapped.sam' in json.dumps(requests[-1]['body']), und)
        r = term(page, 'cd ~; md5sum ' + MINE + '; ls -d moved.bam big.sam.gz new.bam 2>&1; samtools view -c mapped.bam; samtools view -c keep.bam; samtools view -c olddir/in.bam')
        after = r['text'].strip().split('\n')
        check('outside: the student\'s files have their bytes back', after[:8] == before, [x for x in zip(before, after[:8]) if x[0] != x[1]] or after[:8])
        check('outside: what the agent made there is gone, and programs read the files as before', all('No such file' in l for l in after[8:11]) and after[11:14] == ['7038', '7038', '7038'], after[8:])
        r = term(page, 'mkdir ~/gone && samtools --version | head -1 && rm -r ~/gone && samtools --version | head -1; ls -d ~/gone; ls ~/runs | wc -l')
        check('a folder that was removed stays removed after the next program', "cannot access '/home/student/gone'" in r['text'] and r['text'].strip().split('\n')[-1] == '11', r['text'])

        # ---------------- copies, working folders, windows ----------------
        term(page, 'cd ~; cp mapped.bam dropped.bam; samtools quickcheck dropped.bam')   # removed again just before the forced stop, below
        r = term(page, 'cd ~; md5sum mapped.bam | cut -c1-32; cp mapped.bam alias.bam; cp mapped.bam alias2.bam; mv alias2.bam alias3.bam')
        bam = r['text'].strip().split('\n')[0]
        check('copies: the student has copies that no program has read yet', ev("['alias.bam','alias3.bam'].every(f => MG.app.fs.get('/home/student/' + f).apath.endsWith('/mapped.bam'))") and len(bam) == 32, bam)
        ev("MG.app.showWorkbench('assistant')")
        card = run_task('auto', ALIAS, timeout=180000)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/12-auto/run.json').text"))
        cs = [c for s in R['steps'] for c in s['commands']]
        r = term(page, 'cd ~; md5sum mapped.bam alias.bam alias3.bam keep.bam | cut -c1-32; ls -d xdir 2>&1')
        after = r['text'].strip().split('\n')
        check('copies: the original is put back and its copies keep their bytes', cs[0]['output'].strip() == 'hi' and cs[0]['undone'] == ['~/mapped.bam'] and after[:4] == [bam] * 4, (cs[0], after))
        check('copies: a file the agent moved into its folder keeps the agent\'s bytes', cs[2]['undone'] == ['~/keep.bam'] and cs[3]['output'].strip().isdigit() and 150 < int(cs[3]['output'].strip()) < 200, cs[2:4])
        check('a folder outside in which a program ran is removed for good, and the next command is not blamed', cs[4]['undone'] == ['~/xdir'] and cs[5]['code'] == 0 and cs[5]['undone'] == [] and 'No such file' in after[4], (cs[4], cs[5], after[4:]))
        check('copies made in a new folder outside are undone for good – the next command is not blamed, and no empty folder comes back', cs[7]['undone'] and cs[8]['code'] == 0 and cs[8]['undone'] == [] and 'No such file' in term(page, 'samtools --version > /dev/null; ls -d ~/results 2>&1')['text'], (cs[7], cs[8]))
        check('open, nano and download do nothing for the agent, also inside a script', cs[6]['output'].count('not available to the agent') == 3 and cs[6]['output'].strip().endswith('end') and not ev("MG.app.fs.exists('/home/student/runs/12-auto/x.txt')") and ev('MG.app.currentBench') == 'assistant', cs[6]['output'])

        # ---------------- what the student does while a command of the agent runs ----------------
        # the student has a file open in the editor, and another one that is not open
        term(page, 'cd ~; echo "closed, the student\'s" > closed.txt; mkdir sdir; echo t > sdir/f.txt')
        # … and one whose folder was removed while it was open
        ev("MG.app.editFile('/home/student/sdir/f.txt', {})")
        term(page, 'cd ~; rm -r sdir')
        page.wait_for_timeout(300)
        gone_mark = ev("MG.app.editor.open.get('/home/student/sdir/f.txt').gone === true")
        ev("MG.app.editFile('/home/student/mine.txt', {})")
        ev("MG.app.showWorkbench('assistant')")
        card = run_task('auto', BUSY, wait=False)
        page.wait_for_function('!!MG.app.agentBusy', timeout=30000)
        # a file made by a button of the instructions, and a save in the editor
        # (the calls are wrapped so that they return at once: evaluate would wait for a promise)
        ev("(() => { window.__made = MG.app.editFile('/home/student/made_meanwhile.txt', { create: true }).then(() => 'made'); })()")
        page.wait_for_timeout(600)
        early = ev("MG.app.fs.exists('/home/student/made_meanwhile.txt')")
        ev("(() => { const E = MG.app.editor; E.show('/home/student/mine.txt'); E.cm.setValue('changed by the student\\n'); E.save(); window.__saved = MG.app.fs.get('/home/student/mine.txt').text; })()")
        ev("(() => { const E = MG.app.editor; E.show('/home/student/sdir/f.txt'); E.cm.setValue('rescued\\n'); E.save(); E.show('/home/student/mine.txt'); })()")
        page.wait_for_timeout(600)
        saved_at_once = ev("MG.app.fs.get('/home/student/mine.txt').text") == 'changed by the student\n' and ev('!!MG.app.agentBusy')
        # second step: the agent writes the very file that a task of chapter 4 looks for – while the student clicks about
        ev("MG.app.showChapter('repro', true)")
        page.wait_for_function("!!MG.app.agentBusy && MG.app.fs.exists('/home/student/check2/variants.vcf.gz')", timeout=30000)
        ev("MG.app.showWorkbench('terminal')"); page.wait_for_timeout(200); ev("MG.app.showWorkbench('editor')"); page.wait_for_timeout(200)
        # third step: the agent writes into the file the student has open, the student saves, the agent removes the file
        page.wait_for_function("!!MG.app.agentBusy && MG.app.fs.get('/home/student/mine.txt') && MG.app.fs.get('/home/student/mine.txt').text === 'agent\\n'", timeout=30000)
        ev("(() => { MG.app.editFile('/home/student/mine.txt', {}); })()"); page.wait_for_timeout(700)
        shown = ev("MG.app.editor.current === '/home/student/mine.txt' ? MG.app.editor.cm.getValue() : 'not open'")
        # a file that is not open yet, and into which the agent's command has written: it is opened when the command is over
        ev("(() => { window.__opened = MG.app.editFile('/home/student/closed.txt', {}).then(() => MG.app.editor.open.get('/home/student/closed.txt').doc.getValue()); })()"); page.wait_for_timeout(500)
        opened_early = ev("MG.app.editor.open.has('/home/student/closed.txt')")
        ev("(() => { MG.app.editor.show('/home/student/mine.txt'); })()")
        ev("(() => { MG.app.editor.cm.setValue('second save\\n'); MG.app.editor.save(); })()")
        page.wait_for_function('!MG.app.ai.busy', timeout=60000); page.wait_for_timeout(600)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/13-auto/run.json').text"))
        c0 = R['steps'][0]['commands'][0]
        check('meanwhile: a file the agent wrote outside its folder does not tick a task of the student\'s', R['steps'][1]['commands'][0]['undone'] and not ev("MG.app.fs.exists('/home/student/check2')") and not ev("document.querySelector('[data-task=r-run2]').classList.contains('task-done')"), R['steps'][1]['commands'][0])
        ev("MG.app.showChapter('agent', true)")
        check('meanwhile: a new file of the student\'s waits for the end of the agent\'s command, and stays', not early and ev("window.__made") == 'made' and ev("MG.app.fs.exists('/home/student/made_meanwhile.txt')"), early)
        check('meanwhile: a save in the editor does not wait, and stays', saved_at_once and ev("window.__saved") == 'changed by the student\n')
        check('meanwhile: the agent\'s command is not blamed for what the student did', c0['code'] == 0 and c0['undone'] == [] and c0['output'].strip() == 'slept' and R['outcome'] == 'done', c0)
        check('meanwhile: the editor does not take over what the agent writes into an open file', shown == 'changed by the student\n', shown)
        check('meanwhile: a file whose folder was removed is marked in the editor; saved, it is back with its folder – and the agent is not blamed for the folder', gone_mark and term(page, 'cat ~/sdir/f.txt; ls ~/sdir')['text'].strip().split('\n') == ['rescued', 'f.txt'] and c0['undone'] == [], (gone_mark, term(page, 'cat ~/sdir/f.txt; ls ~/sdir')['text'], c0))
        check('meanwhile: a file the agent has written into is opened only when the command is over – with the student\'s text', not opened_early and ev("window.__opened") == "closed, the student's\n" and ev("MG.app.fs.get('/home/student/closed.txt').text") == "closed, the student's\n", (opened_early, ev("window.__opened")))
        check('meanwhile: the version the student saved stays, whatever the agent did to the file before or after', ev("MG.app.fs.get('/home/student/mine.txt') && MG.app.fs.get('/home/student/mine.txt').text") == 'second save\n' and ev("MG.app.editor.open.get('/home/student/mine.txt').doc.getValue()") == 'second save\n' and R['steps'][2]['commands'][0]['output'].strip() == 'over', (ev("MG.app.fs.get('/home/student/mine.txt') && MG.app.fs.get('/home/student/mine.txt').text"), R['steps'][2]['commands'][0]))
        r = term(page, 'cat ~/mine.txt')
        check('… also for the programs', r['text'].strip() == 'second save', r['text'])
        ev("MG.app.showWorkbench('assistant')")

        # ---------------- a script from a run must not reach outside the folder it is run in ----------------
        card = run_task('auto', SCRIPTY, timeout=120000)
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/14-auto/run.json').text"))
        files = [s.get('file') for s in R['steps']]
        check('a file block with a name that is not plain is refused; a file below a file too – and the run goes on', R['outcome'] == 'done' and 'plain name' in files[3]['skipped'] and files[4]['name'] == 'notes/a.txt' and 'is a file, not a folder' in files[5]['skipped'] and not ev("MG.app.fs.exists('/home/student/INJ.txt')"), files)
        ev("MG.app.ai.makeScript(14, '/home/student/runs/14-auto')")
        page.wait_for_timeout(600)
        sh = ev("MG.app.fs.get('/home/student/runs/14-auto/rerun.sh').text")
        check('rerun.sh: a command that names files outside is left out, even if it changed nothing in the run', '# left out – it reaches outside the folder (~/later.txt, ~/later.bam)' in sh and '\nrm -f ~/later.txt' not in sh, [l for l in sh.split('\n') if 'later' in l])
        check('rerun.sh: the full path of the run\'s folder becomes "$RUN_FOLDER", the folder the script runs in', '\nseqtk seq -A few.fastq > "$RUN_FOLDER"/few.fa && wc -l < "$RUN_FOLDER"/few.fa\n' in sh and '14-auto/few.fa' not in sh and '\nset -eu\n\n# RUN_FOLDER: the folder this script runs in.' in sh and '\nRUN_FOLDER=$PWD\n' in sh, [l for l in sh.split('\n') if 'few.fa' in l or 'RUN_FOLDER=' in l])
        check('rerun.sh: files are written with their folders; a script file that looks outside is marked', "\nmkdir -p notes\ncat > notes/a.txt <<'END_OF_FILE'\nhello\nEND_OF_FILE\n" in sh and '# CHECK: this file reaches outside the folder (~/runs)' in sh and 'INJ' not in sh, sh)
        check('rerun.sh: "cd FOLDER/" and OUT=FOLDER/ with the full path of the run\'s folder – never a cd without a folder', '\ncd "$RUN_FOLDER"/ && seqtk seq -A few.fastq | head -2 > two.fa\nOUT="$RUN_FOLDER"/\nwc -l < $OUT/two.fa > lines.txt\n' in sh and '\ncd  ' not in sh and 'OUT=\n' not in sh, [l for l in sh.split('\n') if 'two.fa' in l or 'OUT' in l])
        check('rerun.sh: when a command that changed folder is left out, the script goes there itself; ".." that stays in the folder is kept', "\nmkdir -p work\n# left out – it reaches outside the folder (~); put it back, with paths inside the folder, if the script needs it: cd work && ls ~ > /dev/null\ncd \"$RUN_FOLDER\"/work  # added by the page: the folder in which the next command ran\necho inside > in.txt\ncp ../few.fastq copy.fastq\ncd \"$RUN_FOLDER\"  # added by the page: the agent's next step started in the run's folder again\n" in sh and '\n(\n' not in sh, [l for l in sh.split('\n') if 'work' in l or 'in.txt' in l or 'copy' in l])
        check('rerun.sh: no "pipefail" – a pipeline that worked in the run does not stop the script; a file that is run as a script is marked too', '\nset -eu\n' in sh and '\ncat notes/a.txt | grep -c zzz | cat\nls *.none 2> /dev/null | wc -l\n' in sh and sh.count('# CHECK: this file reaches outside the folder (~/runs)') == 2, [l for l in sh.split('\n') if 'CHECK' in l or 'zzz' in l or 'set -' in l])
        check('rerun.sh: a command that runs such a file is left out, too', '# left out – it runs helper.sh, which reaches outside the folder (~/runs); change that file, then put the command back: bash helper.sh' in sh and '# left out – it runs helper2, which reaches outside the folder (~/runs)' in sh and '\nbash helper.sh\n' not in sh and '\nbash helper2\n' not in sh, [l for l in sh.split('\n') if 'helper' in l])
        check('a file block whose name has a space is refused, with the whole name', files[11]['name'] == 'my notes.txt' and 'plain name' in files[11]['skipped'] and not ev("MG.app.fs.exists('/home/student/runs/14-auto/my')"), files[11])
        home_before = set(term(page, 'cd ~; ls')['text'].split())
        r = term(page, 'echo keep > ~/later.txt; mkdir ~/fresh && cp -r ~/data ~/runs/14-auto/rerun.sh ~/fresh/ && cd ~/fresh && bash rerun.sh > log.txt 2>&1; echo "status $?"; cat ~/later.txt; ls few.fa notes/a.txt; md5sum few.fa ~/runs/14-auto/few.fa | cut -c1-32 | uniq | wc -l; cd ~')
        check('rerun.sh, run in a fresh folder, leaves the rest of the home folder alone', r['text'].strip().split('\n') == ['status 0', 'keep', 'few.fa', 'notes/a.txt', '1'], r['text'] + term(page, 'tail -5 ~/fresh/log.txt')['text'])
        r = term(page, 'cd ~/fresh; ls two.fa lines.txt work/in.txt work/copy.fastq | tr "\\n" " "; cat lines.txt; md5sum two.fa ~/runs/14-auto/two.fa | cut -c1-32 | uniq | wc -l; md5sum work/copy.fastq few.fastq | cut -c1-32 | uniq | wc -l; cd ~')
        home_after = set(term(page, 'cd ~; ls')['text'].split())
        check('… its results are in the fresh folder – also of the commands that named the run\'s folder in full or changed folder – and nothing else is new in the home folder', r['text'].strip().split('\n') == ['lines.txt two.fa work/copy.fastq work/in.txt 2', '1', '1'] and home_after == home_before | {'fresh', 'later.txt'}, (r['text'], sorted(home_after ^ home_before)))
        ev("MG.app.showWorkbench('assistant')")

        # ---------------- a command of the agent that never ends ----------------
        # a file made a moment before the agent starts: it must not be lost with the programs
        # … and a file removed a moment before must not come back
        r = term(page, 'cd ~; ls dropped.bam && rm dropped.bam; samtools view -b -o fresh.bam mapped.bam; md5sum ' + MINE + ' fresh.bam')
        before2 = r['text'].strip().split('\n')[-9:]
        term(page, 'cd ~/data; cd ~')   # the student's "cd -" would go to ~/data
        ev("MG.config.agentCommandSeconds = 8")
        ev("MG.app.showWorkbench('assistant')")
        t0 = time.time()
        card = run_task('auto', HANG, timeout=180000)
        took = time.time() - t0
        ev("MG.config.agentCommandSeconds = 150")
        R = json.loads(ev("MG.app.fs.get('/home/student/runs/15-auto/run.json').text"))
        cs = [c for s in R['steps'] for c in s['commands']]
        check('hang: the command is stopped by the page after the time allowed, and the run goes on', len(cs) == 6 and cs[1].get('timedOut') is True and cs[1]['code'] != 0 and 15 < took < 90 and cs[2]['code'] == 0 and R['outcome'] == 'done', (took, [(c['code'], c.get('timedOut'), c['output'][-80:]) for c in cs]))
        check('hang: also a program that starts just when the time is up', cs[3].get('timedOut') is True and cs[3]['secs'] < 12 and cs[4]['code'] == 0, cs[3])
        check('hang: the agent\'s own earlier files are as before the command – also one that the command had removed, and one whose folder it had removed; what it wrote as text stays; what a program wrote during the command is gone', cs[2]['output'].strip().split('\n') == ['7038', '7038', 'hi', '7038', '7038', '1'], cs[2]['output'])
        check('hang: the card, the record and the model name what is gone', cs[1].get('gone') == ['during.bam'] and 'what programs wrote during this command is gone (during.bam)' in card.inner_text() and 'what they wrote during this command is gone (during.bam)' in ev("MG.app.fs.get('/home/student/runs/15-auto/RUN.md').text") and 'what programs wrote during this command is gone (during.bam)' in json.dumps(requests[-1]['body'], ensure_ascii=False), (cs[1].get('gone'), card.inner_text()[-600:]))
        check('hang: the request to stop is noted once, and names the Stop button', all(c['output'].count('Stop requested') <= 1 for c in cs) and 'press Stop again' in cs[1]['output'] and 'Ctrl+C' not in cs[1]['output'], [c['output'][-300:] for c in cs if 'Stop requested' in c['output']])
        check('the agent\'s "cd -" does not go to the student\'s folders, and the student\'s still goes where it did', cs[5]['code'] == 1 and 'OLDPWD not set' in cs[5]['output'] and term(page, 'cd -; cd ~')['text'].strip() == '/home/student/data', (cs[5], ))
        check('hang: the record and the model are told', 'stopped by the page: it ran for too long' in ev("MG.app.fs.get('/home/student/runs/15-auto/RUN.md').text") and 'the programs were started afresh' in ev("MG.app.fs.get('/home/student/runs/15-auto/RUN.md').text") and '[stopped: it ran for too long] [the programs had to be restarted' in json.dumps(requests[-1]['body'], ensure_ascii=False))
        check('hang: what the command had put in place of the student\'s files is named as undone', set(['~/over.bam', '~/big.sam']) <= set(cs[1]['undone']) and not cs[1].get('lost'), cs[1])
        r = term(page, 'cd ~; md5sum ' + MINE + ' fresh.bam; samtools view -c keep.bam; tail -c 5 big.sam | grep -c junk; ls dropped.bam 2>&1 | grep -c "No such file"')
        after = r['text'].strip().split('\n')
        check('hang: the student\'s files are as before the command – also the one made a moment earlier; nothing the command appended; nothing that had been removed', after[:9] == before2 and before2[:8] == before and after[9:12] == ['7038', '0', '1'], [x for x in zip(before2, after[:9]) if x[0] != x[1]] or after)

        # ---------------- the student stops a program by force ----------------
        # a file removed and a file moved just before: neither old name may come back from the browser's storage
        term(page, 'cd ~; cp mapped.bam x1.bam; cp mapped.bam st.bam; samtools quickcheck x1.bam st.bam')
        page.wait_for_timeout(4500)   # both are in IndexedDB now
        n0 = ev('MG.app.term.outEl.children.length')
        ev("(() => { window.__stopped = undefined; MG.app.term.exec(\"rm x1.bam; mv st.bam ren.bam; awk 'BEGIN { while (1) { } }'\").then((c) => (window.__stopped = c)); })()")
        page.wait_for_function("MG.wasm.running === 'gawk'", timeout=20000); page.wait_for_timeout(300)
        ev('MG.app.term.stop()'); page.wait_for_timeout(200); ev('MG.app.term.stop()')
        page.wait_for_function('window.__stopped !== undefined', timeout=20000); page.wait_for_timeout(800)
        notes = ev(f"Array.from(MG.app.term.outEl.children).slice({n0}).map(e => e.textContent).join('\\n')")
        r = term(page, 'cd ~; ls x1.bam st.bam 2>&1 | grep -c "No such file"; md5sum mapped.bam | cut -c1-32; md5sum ren.bam 2>&1 | cut -c1-32')
        got = r['text'].strip().split('\n')
        # the moved file had been stored under its old name: its bytes come back under the new one
        check('student\'s forced stop: a removed file and the old name of a moved file do not come back; the moved file is back intact', got[:2] == ['2', bam] and got[2] == bam and 'Lost with' not in notes and 'earlier version' not in notes, (r['text'], notes[-400:]))

        # two files of the same size, made in the same moment (fastp's two outputs): one moved over the other
        r = term(page, 'cd ~; fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o q1.fastq -O q2.fastq -h q.html -j q.json 2> /dev/null; md5sum q1.fastq q2.fastq | cut -c1-32')
        q1, q2 = r['text'].strip().split('\n')[-2:]
        page.wait_for_timeout(4500)   # both are in IndexedDB
        term(page, 'cd ~; mv q2.fastq q1.fastq')

        # ---------------- after a reload ----------------
        page.wait_for_timeout(4000)  # program output is written to IndexedDB a moment after it is made
        page.reload(); page.wait_for_function('window.MG_READY === true', timeout=30000)
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai')
        check('reload: still connected (key in this tab), runs are listed', ev('MG.app.ai.connected()') and ev("document.querySelectorAll('.ag.past .ag-pastrow').length") == 15, ev("document.querySelectorAll('.ag.past .ag-pastrow').length"))
        page.wait_for_timeout(1500)
        check('reload: records and scripts are kept (localStorage)', ev("MG.app.fs.exists('/home/student/runs/1-auto/RUN.md') && MG.app.fs.exists('/home/student/runs/1-auto/rerun.sh') && MG.app.fs.exists('/home/student/runs/4-script/analysis.sh')"))
        check('reload: what programs wrote is kept too (IndexedDB)', ev("MG.app.fs.exists('/home/student/runs/1-auto/mapped.bam') && MG.app.fs.get('/home/student/runs/1-auto/mapped.bam').kind === 'blob'"), ev("JSON.stringify(Array.from(MG.app.fs.entries).filter(([k]) => k.startsWith('/home/student/runs/1-auto/')).map(([k, e]) => [k.slice(26), e.kind]))"))
        r = term(page, 'samtools view -c ~/runs/1-auto/mapped.bam; bcftools view -H ~/runs/1-auto/variants.vcf.gz | md5sum; bcftools view -H ~/check/variants.vcf.gz | wc -l')
        check('reload: the kept files still work', r['text'].split() [:2] == ['7038', '547dcc814f0a3f906b1ace9ecc998408'] and r['text'].strip().endswith('60'), r['text'])
        r = term(page, 'cd ~; md5sum ' + MINE + ' fresh.bam; md5sum alias.bam alias3.bam | cut -c1-32')
        check('reload: the files the agent had touched outside its folder are still the student\'s', r['text'].strip().split('\n') == before2 + [bam, bam], r['text'])
        r = term(page, 'cd ~; md5sum q1.fastq | cut -c1-32; ls q2.fastq 2>&1 | grep -c "No such file"')
        check('reload: a file moved over another of the same size and time has the moved file\'s bytes', q1 != q2 and r['text'].strip().split('\n') == [q2, '1'], (q1, q2, r['text']))
        r = term(page, 'cd ~; ls x1.bam st.bam runs/15-auto/mine.bam 2>&1 | grep -c "No such file"; samtools view -c runs/15-auto/own.bam; cat mine.txt')
        check('reload: nothing that was removed is back; the agent\'s own file and the student\'s saved text are', r['text'].strip().split('\n') == ['3', '7038', 'second save'], r['text'])
        # a file saved in the editor while a command of the agent runs is kept, also if the page is loaded again before the command ends
        ev("MG.app.editFile('/home/student/closed.txt', {})")
        ev("MG.app.editFile('/home/student/mine.txt', {})")
        ev("MG.app.showWorkbench('assistant')")
        ev("MG.app.ai.showTab('agent')")
        # … and one saved in the moment before the command starts
        ev("(() => { const E = MG.app.editor; E.show('/home/student/closed.txt'); E.cm.setValue('saved just before the command\\n'); E.save(); })()")
        card = run_task('auto', ["A long wait.\n```bash\nsleep 9 && echo late\n```", "REPORT\nDone."], wait=False)
        page.wait_for_function('!!MG.app.agentBusy', timeout=30000)
        ev("(() => { const E = MG.app.editor; E.show('/home/student/mine.txt'); E.cm.setValue('saved before the reload\\n'); E.save(); })()")
        page.wait_for_timeout(1500)
        page.reload(); page.wait_for_function('window.MG_READY === true', timeout=30000); page.wait_for_timeout(800)
        check('reload in the middle of an agent\'s command: what the student had saved is there', ev("MG.app.fs.get('/home/student/mine.txt').text") == 'saved before the reload\n', ev("MG.app.fs.get('/home/student/mine.txt') && MG.app.fs.get('/home/student/mine.txt').text"))
        check('… also what was saved in the moment before the command started', ev("MG.app.fs.get('/home/student/closed.txt').text") == 'saved just before the command\n', ev("MG.app.fs.get('/home/student/closed.txt') && MG.app.fs.get('/home/student/closed.txt').text"))
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai')
        # the run that was under way has no record: its folder gets a note that says why, and it is listed as interrupted
        cut = ev("MG.app.fs.list('/home/student/runs').filter(c => !MG.app.fs.exists(c.path + '/run.json')).map(c => c.name)")
        note = ev(f"(MG.app.fs.get('/home/student/runs/{cut[0]}/RUN.md') || {{}}).text") if len(cut) == 1 else ''
        rows = page.locator('.ag.past .ag-pastrow')
        last_acts = page.locator('.ag.past .ag-acts').last.inner_text()
        check('reload in the middle of a run: its folder gets a note instead of a record, and the run is listed as interrupted – with no script to make', len(cut) == 1 and 'interrupted' in (note or '') and 'The page was closed or loaded again while this run was under way' in (note or '') and rows.count() == 16 and 'interrupted' in rows.last.inner_text() and 'Make a script' not in last_acts and 'The note (RUN.md)' in last_acts, (cut, note, rows.count(), last_acts))

        # ---------------- models that are busy, silent, over a limit, or break off ----------------
        ASKJS = """async ([cfg]) => {
          let text = '', resets = 0;
          const notes = [], t0 = performance.now(), bar = document.querySelector('.ai-status');
          const out = (x) => Object.assign(x, { text, notes, resets, secs: (performance.now() - t0) / 1000, bar: bar.textContent.trim(), tip: bar.title, dot: bar.querySelector('.kdot').className });
          try {
            const res = await MG.app.ai.stream([{ role: 'user', content: 'Say something.' }], (d) => (text += d), undefined, Object.assign({ onReset: () => { text = ''; resets++; } }, cfg || {}), (n) => notes.push(n));
            return out({ ok: true, model: res.model, skipped: res.skipped.map((x) => x.model + ':' + x.why + (x.daily ? ':day' : '')) });
          } catch (e) {
            return out({ ok: false, message: e.message, status: e.status || 0, retryIn: e.retryIn || 0, network: !!e.network });
          }
        }"""
        def ask(cfg=None):
            n = len(requests)
            r = page.evaluate(ASKJS, [cfg])
            r['asked'] = [q['model'] for q in requests[n:]]
            return r
        over = lambda m: ev(f"MG.aiUtil.modelMemory.get('{m}').until = Date.now() - 1000")   # its rest is over
        state['script'] = ['The answer.']
        forget()
        r = ask()
        check('the chosen model answers: no other is asked, nothing is remembered', r['ok'] and r['model'] == M[0] and r['asked'] == [M[0]] and r['skipped'] == [] and r['text'] == 'The answer.' and mem() == {}, r)
        # busy
        plan[M[0]] = ['busy']
        r = ask()
        check('busy: the next model of the list answers, and a note says so', r['ok'] and r['model'] == M[1] and r['asked'] == M[:2] and r['skipped'] == [M[0] + ':busy'] and r['notes'] == [f'{M[0]} is busy – asking {M[1]} instead…'], r)
        check('busy: the bar shows that the chosen model is at rest', r['bar'].replace('\xa0', ' ').split() == [M[0], 'busy'] and f'{M[0]} is busy.' in r['tip'] and 'rest' in r['dot'], (r['bar'], r['tip'], r['dot']))
        r = ask()
        check('busy: for two minutes the model is not asked again – and the answer still says why another one replied', r['ok'] and r['asked'] == [M[1]] and r['skipped'] == [M[0] + ':busy'] and 100 < mem()[M[0]][1] <= 120, (r, mem()))
        over(M[0]); plan[M[0]] = ['busy']
        r = ask()
        check('busy again after its rest: the next rest is twice as long', r['asked'] == M[:2] and 220 < mem()[M[0]][1] <= 240, (r['asked'], mem()))
        over(M[0])
        r = ask()
        check('after its rest the model is asked again; when it answers, nothing is remembered and the bar is as before', r['ok'] and r['model'] == M[0] and r['asked'] == [M[0]] and mem() == {} and r['bar'] == M[0] and 'ok' in r['dot'], (r, mem()))
        # a limit per day
        forget(); plan['*'] = ['day'] * N
        r = ask()
        check('every model over its limit for today: all were asked once; the error says so, with the numbers the service gave, and that waiting does not help', not r['ok'] and r['status'] == 429 and r['retryIn'] == 0 and r['asked'] == M and 'No requests are left for today' in r['message'] and f'{M[0]} is over its limit for today: 20 requests a day, again after ' in r['message'] and r['message'].count('is over its limit for today') == N, r)
        check('… and the bar says it of the chosen model', r['bar'].replace('\xa0', ' ').split() == [M[0], 'over', 'its', 'limit'] and f'{M[0]} is over its limit for today: 20 requests a day' in r['tip'], (r['bar'], r['tip']))
        r = ask(); m = mem()
        check('… none is asked again today: the time is the one the service gave', not r['ok'] and r['asked'] == [] and 'No requests are left for today' in r['message'] and 44000 < m[M[0]][1] <= 44789 and m[M[0]][2] is True and m[M[0]][3] == 20, (r, m))
        ev(f"MG.aiUtil.modelMemory.delete('{M[4]}')")
        r = ask()
        check('one model with requests left: it answers at once, and the answer names the chosen model\'s limit', r['ok'] and r['model'] == M[4] and r['asked'] == [M[4]] and r['skipped'] == [M[0] + ':limit:day'], r)
        # a limit per minute
        forget(); plan['*'] = ['minute:7'] * N
        r = ask()
        check('every model over its limit per minute: the error says after how many seconds asking again can help', not r['ok'] and r['status'] == 429 and 1 <= r['retryIn'] <= 8 and r['asked'] == M and 'Too many requests' in r['message'] and f'{M[1]} is over its limit per minute' in r['message'], r)
        r2 = ask()
        check('… and nothing is asked before that', not r2['ok'] and r2['asked'] == [] and 1 <= r2['retryIn'] <= r['retryIn'], r2)
        forget(); plan[M[0]] = ['limit']; plan[M[1]] = ['long']
        r = ask(); m = mem()
        check('"too many requests" with no time given: a rest of a minute; with a long time: taken as the limit for today', r['ok'] and r['model'] == M[2] and r['skipped'] == [M[0] + ':limit', M[1] + ':limit:day'] and 55 < m[M[0]][1] <= 61 and m[M[0]][2] is False and 3500 < m[M[1]][1] <= 3601 and m[M[1]][2] is True, (r, m))
        # not found
        forget(); plan[M[0]] = ['gone']
        r = ask(); r2 = ask()
        check('a model that is not found is passed over, and not asked again', r['ok'] and r['model'] == M[1] and r['skipped'] == [M[0] + ':notfound'] and r['notes'] == [f'{M[0]} was not found – asking {M[1]} instead…'] and r2['asked'] == [M[1]] and mem()[M[0]][:2] == ['notfound', -1], (r, r2, mem()))
        # no answer
        forget(); plan[M[0]] = ['drop']
        r = ask()
        check('no answer (the connection fails): the next model is asked', r['ok'] and r['model'] == M[1] and r['skipped'] == [M[0] + ':noanswer'] and r['notes'] == [f'{M[0]} gave no answer – asking {M[1]} instead…'] and 50 < mem()[M[0]][1] <= 60, (r, mem()))
        forget(); plan[M[0]] = ['drop']; plan[M[1]] = ['drop']
        r = ask()
        check('two models in a row give no answer: that is the connection – no more are asked', not r['ok'] and r['asked'] == M[:2] and r['network'] and r['status'] == 0 and r['retryIn'] == 20 and r['message'].startswith('Could not reach the Gemini API') and f'{M[1]} gave no answer' in r['message'], r)
        forget(); plan[M[0]] = ['busy']; plan[M[1]] = ['drop']; plan[M[2]] = ['drop']
        r = ask()
        check('… when another model answered a moment ago, if only with "busy", the message does not blame the connection', not r['ok'] and r['asked'] == M[:3] and r['status'] == 0 and r['retryIn'] == 20 and r['message'].startswith('No answer came from the Gemini API, though it can be reached') and 'internet' not in r['message'], r)
        forget(); plan[M[0]] = ['busy']; plan[M[1]] = ['drop']; plan[M[2]] = ['busy']; plan[M[3]] = ['drop']
        r = ask()
        check('… but silent models between busy ones are passed over like those', r['ok'] and r['model'] == M[4] and r['asked'] == M[:5], r)
        ev('MG.config.aiWaitSeconds = 2')
        forget(); plan[M[0]] = ['hang']
        r = ask()
        check('no answer (the service says nothing): given up after the time allowed, and the next model is asked', r['ok'] and r['model'] == M[1] and r['skipped'] == [M[0] + ':noanswer'] and 1.9 < r['secs'] < 8, r)
        # an answer that is an error, or ends in one
        forget(); plan[M[0]] = ['inner']
        r = ask()
        check('an error in place of the answer, after "200 OK": as a busy model', r['ok'] and r['model'] == M[1] and r['skipped'] == [M[0] + ':busy'] and r['resets'] == 0, r)
        forget(); plan[M[0]] = ['half']
        r = ask()
        check('an answer that breaks off with an error: taken back, and the next model is asked', r['ok'] and r['model'] == M[1] and r['text'] == 'The answer.' and r['resets'] == 1 and r['skipped'] == [M[0] + ':broke'] and r['notes'] == [f'{M[0]} broke off – asking {M[1]} instead…'] and mem()[M[0]][0] == 'busy', (r, mem()))
        forget(); plan[M[0]] = ['half']
        r = ask({'onReset': None})
        check('… where an answer cannot be taken back, the error is passed on', not r['ok'] and r['status'] == 503 and r['text'] == 'Half an ans' and r['asked'] == [M[0]], r)
        # the connection itself can break in the middle of an answer, or go silent. A mocked answer arrives whole, so the
        # next answer is made in the page: it begins, and then fails or stalls (and ends, as a real one does, when the page gives it up)
        ev("""(() => {
          window.__realFetch = window.fetch;
          window.fetch = (url, opts) => {
            const kind = window.__breakNext;
            if (!kind || !String(url).includes('generativelanguage')) return window.__realFetch(url, opts);
            window.__breakNext = null;
            const body = new ReadableStream({ start(c) {
              c.enqueue(new TextEncoder().encode('data: ' + JSON.stringify({ candidates: [{ content: { parts: [{ text: 'Half an ans' }], role: 'model' }, index: 0 }] }) + '\\r\\n\\r\\n'));
              if (kind === 'error') setTimeout(() => c.error(new TypeError('network error')), 150);
              if (opts && opts.signal) opts.signal.addEventListener('abort', () => { try { c.error(new DOMException('The user aborted a request.', 'AbortError')); } catch (e) { /* it had failed already */ } });
            } });
            return Promise.resolve(new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } }));
          };
        })()""")
        for kind, what in (('error', 'the connection breaks'), ('stall', 'nothing more comes')):
            forget(); ev(f"window.__breakNext = '{kind}'")
            r = ask()
            check(f'in the middle of an answer {what}: taken back, and the next model is asked', r['ok'] and r['model'] == M[1] and r['asked'] == [M[1]] and r['text'] == 'The answer.' and r['resets'] == 1 and r['skipped'] == [M[0] + ':broke'] and mem()[M[0]][0] == 'noanswer' and (kind == 'error' or 1.9 < r['secs'] < 8), (r, mem()))
        ev('window.fetch = window.__realFetch; MG.config.aiWaitSeconds = 60')
        # every model busy
        forget(); plan['*'] = ['busy'] * N
        r = ask()
        check('every model busy: all are asked once; the error says so, and that asking again soon can help', not r['ok'] and r['status'] == 503 and r['retryIn'] == 20 and r['asked'] == M and 'Google’s servers are busy' in r['message'] and f'{M[N - 1]} is busy' in r['message'], r)
        plan['*'] = ['busy'] * 4
        r = ask(); r2 = ask()
        check('… asked again while all are at rest: only the two that have rested longest, then the next two', not r['ok'] and r['asked'] == M[:2] and not r2['ok'] and r2['asked'] == M[2:4], (r['asked'], r2['asked']))
        r = ask()
        check('… and when one of them answers, that is the answer', r['ok'] and r['model'] == M[4] and r['asked'] == [M[4]] and r['skipped'] == [M[0] + ':busy'], r)
        # other errors, another key, no network
        forget(); plan[M[0]] = ['bad']
        r = ask()
        check('an error of another kind is no reason to ask another model', not r['ok'] and r['status'] == 400 and r['asked'] == [M[0]] and mem() == {}, r)
        forget(); plan[M[0]] = ['busy']; ask()
        had = mem()
        r = ask({'key': 'OTHER'})
        check('another key: what was remembered is forgotten (limits belong to the project of a key)', M[0] in had and not r['ok'] and r['asked'] == [M[0]] and 'API key was not accepted' in r['message'] and mem() == {}, (had, r, mem()))
        page.context.set_offline(True)
        r = ask()
        page.context.set_offline(False)
        check('offline: said at once – nothing is asked, nothing remembered', not r['ok'] and r['asked'] == [] and 'offline' in r['message'] and r['retryIn'] == 20 and mem() == {}, r)
        # in the chat: the answer of the model that replied, and its name
        ev("MG.app.ai.showTab('chat')")
        forget(); plan[M[0]] = ['half']; plan[M[1]] = ['busy']
        page.fill('.ai-input', 'Say something.'); page.keyboard.press('Enter')
        page.wait_for_function('!MG.app.ai.busy', timeout=20000); page.wait_for_timeout(300)
        last = page.locator('.ai-thread[data-tab=chat] .ai-msg.assistant').last
        check('chat: the answer that broke off is not shown, the one that came is – with the model, and what kept the others', last.locator('.ai-body').inner_text().strip() == 'The answer.' and last.locator('.ai-badge').text_content().startswith(f'{M[2]} ({M[0]} broke off, {M[1]} busy) · '), (last.locator('.ai-body').inner_text(), last.locator('.ai-badge').text_content()))
        forget(); plan['*'] = ['day'] * N
        page.fill('.ai-input', 'Say something more.'); page.keyboard.press('Enter')
        page.wait_for_function('!MG.app.ai.busy', timeout=20000); page.wait_for_timeout(300)
        last = page.locator('.ai-thread[data-tab=chat] .ai-msg.assistant').last
        check('chat: when no model has requests left for today, the answer says so', 'err' in last.get_attribute('class') and 'No requests are left for today' in last.inner_text(), last.inner_text()[:300])
        forget(); plan[M[0]] = ['empty']; turns = ev('MG.app.ai.msgs.length')
        page.fill('.ai-input', 'Say nothing.'); page.keyboard.press('Enter')
        page.wait_for_function('!MG.app.ai.busy', timeout=20000); page.wait_for_timeout(300)
        last = page.locator('.ai-thread[data-tab=chat] .ai-msg.assistant').last
        check('chat: an empty reply is said to be one, and is not kept as a turn of the conversation', f'{M[0]} sent an empty reply. Ask again' in last.inner_text() and 'returned an error' not in last.inner_text() and ev('MG.app.ai.msgs.length') == turns and mem() == {}, (last.inner_text()[:200], turns, ev('MG.app.ai.msgs.length')))
        # the agent
        ev("MG.app.ai.showTab('agent')")
        def last_run():
            name = ev("MG.app.fs.list('/home/student/runs').map(c => c.name).filter(n => MG.app.fs.exists('/home/student/runs/' + n + '/run.json')).sort((a, b) => parseInt(a) - parseInt(b)).pop()")
            return json.loads(ev(f"MG.app.fs.get('/home/student/runs/{name}/run.json').text"))
        forget(); plan[M[0]] = ['hang']; ev('MG.config.aiWaitSeconds = 2')
        card = run_task('auto', ["One step.\n```bash\necho one\n```", "REPORT\nDone in one step."], timeout=60000)
        ev('MG.config.aiWaitSeconds = 60')
        R = last_run()
        check('agent: a model that says nothing does not end the run – the next one goes on, and the record names it', R['outcome'] == 'done' and R['models'] == [M[1]] and R['requests'] == 2 and 'finished' in card.locator('.ag-head').inner_text(), (R['outcome'], R['models'], R['requests'], R['error']))
        forget(); plan[M[0]] = ['empty']; n0 = len(requests)
        card = run_task('auto', ["One step.\n```bash\necho one\n```", "REPORT\n\nREPORT\n\nDone in one step."], timeout=60000)
        R = last_run()
        check('agent: an empty reply is asked again, and is not a turn of the conversation', R['outcome'] == 'done' and R['requests'] == 3 and len(R['steps']) == 1 and [len(q['body']['contents']) for q in requests[n0:]] == [1, 1, 3], (R['outcome'], R['requests'], [len(q['body']['contents']) for q in requests[n0:]]))
        check('agent: a report that begins with the word REPORT twice is shown without it', R['report'] == 'Done in one step.' and 'REPORT' not in card.locator('.ag-report').inner_text(), R['report'])
        forget(); plan[M[0]] = ['malformed']; n0 = len(requests)
        card = run_task('auto', ["(the first reply is the one that the service cut off)", "REPORT\nDone."], timeout=60000)
        R = last_run()
        check('agent: a step that the service cut off as a "malformed function call" is not lost – the block is taken from what the service says it took away', R['outcome'] == 'done' and R['requests'] == 2 and len(requests) - n0 == 2 and len(R['steps']) == 1 and R['steps'][0]['say'] == 'I look at what is there.' and [c['cmd'] for c in R['steps'][0]['commands']] == ['echo recovered', 'ls data | wc -l'] and R['steps'][0]['commands'][0]['output'].strip() == 'recovered' and R['steps'][0]['commands'][1]['output'].strip() == '3', (R['outcome'], R['requests'], R['steps']))
        forget(); n0 = len(requests)
        card = run_task('auto', ["I look.\n```bash\necho real\n```\n\nREPORT\nThe command printed: invented.", "REPORT\nThe command printed: real."], timeout=60000)
        R = last_run()
        md = ev(f"MG.app.fs.get('/home/student/runs/{R['folder'].split('/')[-1]}/RUN.md').text")
        told = requests[-1]['body']['contents'][-1]['parts'][0]['text']
        check('agent: a report in the same reply as a step – written before the step ran – is not the report; the step runs, and the agent is told', R['outcome'] == 'done' and len(R['steps']) == 1 and R['steps'][0]['say'] == 'I look.' and R['steps'][0].get('early') == 'The command printed: invented.' and R['steps'][0]['commands'][0]['output'].strip() == 'real' and R['report'] == 'The command printed: real.' and 'It was not taken as your report' in told and '$ echo real' in told, (R['steps'], R['report'], told[-300:]))
        check('… the card and the record say so, and the record keeps what was written', 'before this step had run' in card.inner_text() and 'invented' not in card.locator('.ag-report').inner_text() and 'before this step had run – the agent wrote a report' in md and '> The command printed: invented.' in md and md.index('It printed:') < md.index('> The command printed: invented.') < md.index('## The agent’s report'), md[-900:])
        pr = lambda t: page.evaluate("(t) => { const P = MG.aiUtil.parseReply(t); return [P.final, P.early, P.say, P.bash, P.file ? P.file.name : null]; }", t)
        check('… only the word REPORT alone on its line, outside the blocks, in a reply that is a step', pr("A note.\n```file:README.md\n# Report\n\ntext\n```") == [False, '', 'A note.', None, 'README.md'] and pr("REPORT.md is not there yet.\n```bash\nls\n```")[:2] == [False, ''] and pr("```bash\nls\n```\n**REPORT:**\nDone.")[:3] == [False, 'Done.', ''] and pr("REPORT\nDone.\n```bash\nls\n```")[:2] == [True, ''] and pr("I think.\n\nREPORT\nDone.")[:2] == [True, ''] and [pr(t)[0] for t in ("REPORT: done.", "## REPORT", "REPORT. I mapped the reads.", "FINAL REPORT\nx", "REPORT-1.txt holds it.\n```bash\ncat REPORT-1.txt\n```", "REPORT/ is a folder.\n```bash\nls REPORT\n```", "REPORTS follow.\n```bash\nls\n```")] == [True, True, True, True, False, False, False], [pr("A note.\n```file:README.md\n# Report\n\ntext\n```"), pr("REPORT.md is not there yet.\n```bash\nls\n```"), pr("```bash\nls\n```\n**REPORT:**\nDone."), pr("REPORT\nDone.\n```bash\nls\n```"), pr("I think.\n\nREPORT\nDone.")])
        forget(); plan[M[0]] = ['empty'] * 3
        card = run_task('auto', ["REPORT\nNothing to do."], timeout=60000)
        R = last_run()
        check('agent: three empty replies in a row end the run, and it says why', R['outcome'] == 'error' and 'sent an empty reply, three times in a row' in R['error'] and R['requests'] == 3, (R['outcome'], R['error'], R['requests']))
        forget(); plan['*'] = ['busy'] * N
        t0 = time.time()
        card = run_task('auto', ["REPORT\nNothing to do."], wait=False)
        page.wait_for_function("/The service is busy – waiting \\d+ s, then asking again/.test(document.querySelector('.ai-thread[data-tab=agent]').textContent)", timeout=20000)
        page.wait_for_function('!MG.app.ai.busy', timeout=60000); page.wait_for_timeout(300)
        waited = time.time() - t0
        R = last_run()
        check('agent: every model busy – it waits, asks again, and goes on', R['outcome'] == 'done' and R['models'] == [M[0]] and 18 < waited < 50, (waited, R['outcome'], R['models']))
        forget(); plan['*'] = ['minute:5'] * (N * 4)
        n0 = len(requests); t0 = time.time()
        card = run_task('auto', ["REPORT\nNothing to do."], timeout=120000)
        waited = time.time() - t0
        R = last_run()
        check('agent: still over the limit per minute after three waits – the run ends, and says what was tried', R['outcome'] == 'error' and 'Too many requests' in R['error'] and 'The page waited three times and the limit is still reached' in R['error'] and 14 < waited < 60 and len(requests) - n0 == N * 4 and plan['*'] == [], (waited, len(requests) - n0, R['error'][-300:]))
        forget()

        # ---------------- the other services ----------------
        # Anthropic's Messages API and an OpenAI-compatible "chat completions" service, as the page asks them. One model each:
        # no list of models to fall back on, and no limit on how long the service may be silent (a model on a laptop can
        # take minutes to begin).
        sent = []; g0 = len(requests)
        SSE = dict(H, **{'content-type': 'text/event-stream'}); JS = dict(H, **{'content-type': 'application/json'})
        def reply_of(turns):
            return state['script'][min(turns, len(state['script']) - 1)]
        def anthropic(route):
            req = route.request
            body = json.loads(req.post_data or '{}')
            sent.append({'service': 'anthropic', 'url': req.url, 'headers': dict(req.headers), 'body': body})
            kind = plan['anthropic'].pop(0) if plan.get('anthropic') else ''
            if kind == 'busy': return route.fulfill(status=529, headers=JS, body=json.dumps({'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}))
            if kind == 'limit': return route.fulfill(status=429, headers=dict(JS, **{'retry-after': '6', 'access-control-expose-headers': 'retry-after'}), body=json.dumps({'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'This request would exceed your rate limit.'}}))
            if kind == 'drop': return route.abort('failed')
            e = lambda t, d: f'event: {t}\ndata: {json.dumps(dict(d, type=t))}\n\n'
            text = reply_of(len([m for m in body['messages'] if m['role'] == 'assistant']))
            k = len(text) // 2
            out = e('message_start', {'message': {'id': 'msg_1', 'role': 'assistant', 'content': []}}) + e('content_block_start', {'index': 0, 'content_block': {'type': 'text', 'text': ''}}) + e('ping', {})
            out += ''.join(e('content_block_delta', {'index': 0, 'delta': {'type': 'text_delta', 'text': t}}) for t in (text[:k], text[k:]))
            out += e('error', {'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}) if kind == 'half' else e('content_block_stop', {'index': 0}) + e('message_stop', {})
            route.fulfill(status=200, headers=SSE, body=out)
        def openai(route):
            req = route.request
            body = json.loads(req.post_data or '{}')
            sent.append({'service': 'openai', 'url': req.url, 'headers': dict(req.headers), 'body': body})
            kind = plan['openai'].pop(0) if plan.get('openai') else ''
            if kind == 'busy': return route.fulfill(status=500, headers=JS, body=json.dumps({'error': {'message': 'The server had an error while processing your request.', 'type': 'server_error'}}))
            if kind == 'drop': return route.abort('failed')
            if kind == 'slow': time.sleep(2.5)
            text = reply_of(len([m for m in body['messages'] if m['role'] == 'assistant']))
            k = len(text) // 2
            out = ''.join('data: ' + json.dumps({'id': 'c', 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': d}]}) + '\n\n' for d in ({'role': 'assistant', 'content': ''}, {'content': text[:k]}, {'content': text[k:]}, {})) + 'data: [DONE]\n\n'
            route.fulfill(status=200, headers=SSE, body=out)
        page.route('https://api.anthropic.com/**', anthropic)
        page.route('https://llm.example.test/**', openai)
        CLAUDE = {'settings': {'provider': 'anthropic', 'model': '', 'geminiModel': '', 'baseURL': '', 'openaiModel': ''}, 'key': 'KEY-A'}
        LOCAL = {'settings': {'provider': 'openai', 'model': '', 'geminiModel': '', 'baseURL': 'https://llm.example.test/v1/', 'openaiModel': 'local-model'}, 'key': 'KEY-O'}
        def ask2(cfg, **more):
            n = len(sent)
            r = page.evaluate(ASKJS, [dict(cfg, **more)])
            r['sent'] = sent[n:]
            return r
        state['script'] = ['The answer.']
        claude = ev('MG.config.anthropicModel')
        r = ask2(CLAUDE); q = r['sent'][0] if r['sent'] else {'headers': {}, 'body': {}, 'url': ''}
        check('Anthropic: the request is the one its API asks for, and the answer is read', r['ok'] and r['model'] == claude and r['text'] == 'The answer.' and r['skipped'] == [] and len(r['sent']) == 1 and q['url'] == 'https://api.anthropic.com/v1/messages' and q['headers'].get('x-api-key') == 'KEY-A' and q['headers'].get('anthropic-version') == '2023-06-01' and q['headers'].get('anthropic-dangerous-direct-browser-access') == 'true' and q['body'].get('model') == claude and q['body'].get('stream') is True and q['body'].get('system') and q['body']['messages'] == [{'role': 'user', 'content': 'Say something.'}] and 'x-goog-api-key' not in q['headers'], (r, {k: v for k, v in q['headers'].items() if k.startswith('x-') or k.startswith('anthropic')}, q['body']))
        plan['anthropic'] = ['busy']
        r = ask2(CLAUDE)
        check('Anthropic: busy once – a second try, with a note', r['ok'] and r['text'] == 'The answer.' and len(r['sent']) == 2 and r['notes'] == [f'{claude} is busy – trying again…'], r)
        plan['anthropic'] = ['busy', 'busy']
        r = ask2(CLAUDE)
        check('Anthropic: busy twice – the error, and no third try', not r['ok'] and r['status'] == 529 and len(r['sent']) == 2 and 'The service is busy or had a temporary problem' in r['message'] and r['retryIn'] == 0, r)
        plan['anthropic'] = ['limit']
        r = ask2(CLAUDE)
        check('Anthropic: "too many requests" – the error says after how many seconds to ask again, as the service did', not r['ok'] and r['status'] == 429 and r['retryIn'] == 6 and len(r['sent']) == 1 and 'Too many requests, or no credit left' in r['message'], r)
        plan['anthropic'] = ['half']
        r = ask2(CLAUDE)
        check('Anthropic: an error after the answer has begun is passed on, with what had arrived', not r['ok'] and r['status'] == 529 and r['text'] == 'The answer.' and len(r['sent']) == 1 and r['resets'] == 0, r)
        plan['anthropic'] = ['drop']
        r = ask2(CLAUDE)
        check('Anthropic: a connection that fails is said to be one', not r['ok'] and r['network'] and r['message'].startswith('Could not reach the Anthropic API (') and r['message'].endswith('Check the internet connection.') and len(r['sent']) == 1, r)
        r = ask2(LOCAL); q = r['sent'][0] if r['sent'] else {'headers': {}, 'body': {}, 'url': ''}
        check('OpenAI-compatible: the request is the one such services ask for, and the answer is read', r['ok'] and r['model'] == 'local-model' and r['text'] == 'The answer.' and q['url'] == 'https://llm.example.test/v1/chat/completions' and q['headers'].get('authorization') == 'Bearer KEY-O' and q['body'].get('model') == 'local-model' and q['body'].get('stream') is True and [m['role'] for m in q['body']['messages']] == ['system', 'user'] and 'x-goog-api-key' not in q['headers'] and 'x-api-key' not in q['headers'], (r, q['url'], q['body']))
        r = ask2(LOCAL, key='')
        check('OpenAI-compatible: a service that needs no key gets none', r['ok'] and 'authorization' not in r['sent'][0]['headers'], [k for k in r['sent'][0]['headers']] if r['sent'] else r)
        plan['openai'] = ['busy']
        r = ask2(LOCAL)
        check('OpenAI-compatible: a server error once – a second try', r['ok'] and len(r['sent']) == 2 and r['notes'] == ['local-model is busy – trying again…'], r)
        plan['openai'] = ['drop']
        r = ask2(LOCAL)
        check('OpenAI-compatible: when the address cannot be reached, the message names it and what such a service must allow', not r['ok'] and r['message'].startswith('Could not reach https://llm.example.test/v1 (') and 'must allow requests from web pages (CORS)' in r['message'], r)
        ev('MG.config.aiWaitSeconds = 1'); plan['openai'] = ['slow']
        r = ask2(LOCAL)
        ev('MG.config.aiWaitSeconds = 60')
        check('OpenAI-compatible: a slow answer is waited for – the time allowed for silence is for Gemini\'s list of models only', r['ok'] and r['text'] == 'The answer.' and r['secs'] > 2.3, r)
        check('with another service no Gemini model is asked, and nothing is remembered about them', mem() == {} and len(requests) == g0, (mem(), len(requests) - g0))
        # an agent's run with another service: chosen in the settings, tested, and "too many requests" in the middle of the run
        page.click('.ai-bar .tbtn[aria-label="AI settings"]'); page.wait_for_selector('.modal [data-x=connect]')
        page.select_option('.modal [data-k=provider]', 'anthropic'); page.fill('.modal [data-k=key]', 'KEY-A')
        state['script'] = ['ready']
        page.click('.modal [data-x=connect]')
        page.wait_for_function("!document.querySelector('.modal') && MG.app.ai.settings.provider === 'anthropic'", timeout=20000); page.wait_for_timeout(300)
        check('another service can be chosen in the settings: it is tested, and the bar shows its model', claude in page.inner_text('.ai-status') and ev("sessionStorage.getItem('agents-ai-key')") == 'KEY-A' and ev("!!document.querySelector('.ai-status .kdot.ok')"), page.inner_text('.ai-status'))
        plan['anthropic'] = ['', 'limit']; n0 = len(sent); t0 = time.time()
        card = run_task('auto', ["One step.\n```bash\necho one\n```", "REPORT\nDone in one step."], timeout=60000)
        waited = time.time() - t0
        R = last_run()
        md = ev(f"MG.app.fs.get('/home/student/runs/{R['folder'].split('/')[-1]}/RUN.md').text")
        check('agent with Anthropic: the run works, waits as long as the service asks after "too many requests", and the record names service and model', R['outcome'] == 'done' and R['models'] == [claude] and R['service'] == 'Anthropic API' and R['requests'] == 2 and len(sent) - n0 == 3 and 5.5 < waited < 30 and f'{claude} (Anthropic API)' in md and sent[-1]['body']['messages'][-1]['role'] == 'user' and '$ echo one' in sent[-1]['body']['messages'][-1]['content'], (waited, R['outcome'], R['models'], R['service'], R['requests'], len(sent) - n0))

        page.click('.ai-bar .tbtn[aria-label="AI settings"]'); page.wait_for_selector('.modal [data-x=forget]')
        page.click('.modal [data-x=forget]'); page.wait_for_timeout(300)
        check('disconnect: the key is gone and the form is back', ev("sessionStorage.getItem('agents-ai-key')") is None and not ev('MG.app.ai.connected()') and not ev("document.querySelector('.ai-connect').hidden"))
        # (a run that ends with an error of the service writes that error to the console: those are expected)
        bad = [l for l in logs if 'PAGEERROR' in l or (l.startswith('error') and 'Failed to load resource' not in l and not re.search(r'HTTP (429|503)\. |sent an empty reply, three times', l))]
        # (for information: how much of the browser's small storage the text files of this session take – the limit is 3,500,000)
        print('text files in the saved state:', ev("(() => { const s = MG.project.snapshot(MG.app.fs); return s.entries.filter(e => e.k === 't').length + ' files, ' + s.entries.reduce((n, e) => n + (e.t ? e.t.length : 0), 0) + ' characters; not kept: ' + s.skipped; })()"))
        check('no errors in the page', not bad, bad[:5])
        for r in hold:   # the request that was left unanswered for the Stop test
            try:
                r.abort()
            except Exception:
                pass
        page.wait_for_timeout(200)
        b.close()
    finally:
        srv.terminate()
    fails = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(fails)} of {len(results)} passed')
    for f in fails:
        print('FAILED:', f[0], '–', str(f[2])[:1200])
