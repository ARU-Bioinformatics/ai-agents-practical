"""Screenshots of the AI panel in its main states (mocked model)."""
import sys, json, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8842
OUT = OUT_DIR + '/'
H = {'access-control-allow-origin': '*'}
def sse(text):
    k = len(text) // 2
    return ''.join('data: ' + json.dumps({'candidates': [{'content': {'parts': [{'text': t}], 'role': 'model'}, 'index': 0}]}) + '\r\n\r\n' for t in (text[:k], text[k:]))
AUTO = [
    "First I look at the input files.\n```bash\nls -l data\nhead -4 data/NA12878_R1.fastq\n```",
    "I map the reads with minimap2, then sort and index the alignments.\n```bash\nminimap2 -ax sr -t 4 data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nsamtools sort -o mapped.bam mapped.sam\nsamtools index mapped.bam\n```",
    "A check that will fail.\n```bash\nsamtools nonsense mapped.bam\n```",
    "Now I call the variants and look at the position.\n```bash\nbcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz\nbcftools index variants.vcf.gz\nbcftools view -H -r human_CYP2C19:11616 variants.vcf.gz\n```",
    "REPORT\nI mapped the reads with **minimap2** (`-ax sr`) and called variants with `bcftools mpileup | bcftools call -mv`.\n\n- File: `variants.vcf.gz` (60 variants)\n- Genotype at human_CYP2C19:11616: **0/1** (G>A), QUAL 222, depth 106 (DP4 = 40,4,46,2)\n\nOne command failed (`samtools nonsense` does not exist) and was not needed.",
]
PLAN = ["1. **Quality control** – `fastp` on both read files; writes `fastp.html`.\n2. **Map** the reads with `minimap2 -ax sr` to `mapped.sam`.\n3. **Sort and index** with `samtools` → `mapped.bam`.\n4. **Call variants** with `bcftools mpileup | bcftools call -mv` → `variants.vcf.gz`, then index it.\n5. **Check**: look at position 11616 with `bcftools view -r`."]
state = {'script': AUTO}
def gemini(route):
    body = json.loads(route.request.post_data or '{}')
    models = [c for c in body.get('contents', []) if c['role'] == 'model']
    last = body['contents'][-1]['parts'][0]['text']
    if 'single word: ready' in last: text = 'ready'
    elif state['script'] == 'chat': text = "You can map the reads with **minimap2** and sort the result with samtools:\n\n```bash\nminimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nsamtools sort -o mapped.bam mapped.sam\nsamtools index mapped.bam\n```\n\n- `-ax sr` is the preset for short reads.\n- Check the result with `samtools flagstat mapped.bam`.\n\nI cannot see what these print – run them and look."
    else: text = state['script'][min(len(models), len(state['script']) - 1)]
    time.sleep(0.2)
    route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse(text))
with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw, width=1500, height=950)
        page.route('https://generativelanguage.googleapis.com/**', gemini)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        ev = lambda js: page.evaluate(js)
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai'); page.wait_for_timeout(300)
        page.screenshot(path=OUT + '1-connect.png')
        page.fill('.ai-connect [data-k=key]', 'GOOD'); page.click('.ai-connect [data-x=connect]')
        page.wait_for_function('MG.app.ai.connected()', timeout=20000); page.wait_for_timeout(300)
        state['script'] = 'chat'
        page.fill('.ai-input', 'How do I map my reads with minimap2 and make a sorted BAM file?'); page.keyboard.press('Enter')
        page.wait_for_function("!MG.app.ai.busy", timeout=20000); page.wait_for_timeout(400)
        page.screenshot(path=OUT + '2-chat.png')
        ev("MG.app.ai.showTab('agent')"); ev("MG.app.ai.setMode('ask')"); state['script'] = AUTO
        page.fill('.ai-input', 'Find the variants of sample NA12878 and tell me the genotype at position 11616 of human_CYP2C19.'); page.keyboard.press('Enter')
        page.wait_for_selector('.ag-approve .ag-approve-acts', timeout=30000); page.wait_for_timeout(300)
        page.click('.ag-approve button:has-text("Run it")')
        page.wait_for_selector('.ag-approve .ag-approve-acts', timeout=30000); page.wait_for_timeout(300)
        page.screenshot(path=OUT + '3-approve.png')
        page.click('.ag-approve button:has-text("Run, and stop asking")')
        page.wait_for_function('!MG.app.ai.busy', timeout=120000); page.wait_for_timeout(500)
        page.screenshot(path=OUT + '4-done.png')
        ev("document.querySelector('.ai-thread[data-tab=agent]').scrollTop = 0"); page.wait_for_timeout(200)
        page.screenshot(path=OUT + '4b-top.png')
        ev("MG.app.ai.setMode('plan')"); state['script'] = PLAN
        page.fill('.ai-input', 'Find the variants of sample NA12878 and tell me the genotype at position 11616 of human_CYP2C19.'); page.keyboard.press('Enter')
        page.wait_for_selector('.ag-approve .ag-comment', timeout=30000); page.wait_for_timeout(300)
        page.screenshot(path=OUT + '5-plan.png')
        page.click('.ai-send'); page.wait_for_function('!MG.app.ai.busy', timeout=20000)
        ev("MG.app.showWorkbench('terminal')"); page.wait_for_timeout(300)
        page.screenshot(path=OUT + '6-terminal.png')
        ev("MG.app.editFile('/home/student/runs/1-approve/RUN.md', {})"); page.wait_for_timeout(700)
        page.screenshot(path=OUT + '7-runmd.png')
        r = term(page, 'cd ~ && fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o t1.fq -O t2.fq -h fastp.html -j fastp.json 2>/dev/null; open fastp.html')
        page.wait_for_timeout(3500)
        page.screenshot(path=OUT + '8-fastp.png')
        fr = page.frame_locator('iframe.ed-frame')
        try:
            n = fr.locator('.js-plotly-plot').count()
            print('plotly plots in the fastp report:', n)
            fr.locator('.js-plotly-plot').nth(2).scroll_into_view_if_needed(timeout=3000)
        except Exception as e:
            print('frame check:', str(e)[:300])
        page.wait_for_timeout(800)
        page.screenshot(path=OUT + '9-fastp-plots.png')
        print('\n'.join(l for l in logs if 'PAGEERROR' in l or l.startswith('error'))[:3000])
        b.close()
    finally:
        srv.terminate()
