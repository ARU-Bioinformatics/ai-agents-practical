"""The page at several window sizes; Start again; Save all my work / Open my work.
(What the browser keeps: text files in localStorage, program output in IndexedDB, the key in sessionStorage.)"""
import sys, json, time, os
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8870
OUT = OUT_DIR + '/'
os.makedirs(OUT, exist_ok=True)
H = {'access-control-allow-origin': '*'}
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info))
    print(('PASS ' if ok else 'FAIL ') + name + (('  – ' + str(info)[:700]) if info and not ok else ''), flush=True)
def sse(text):
    return 'data: ' + json.dumps({'candidates': [{'content': {'parts': [{'text': text}], 'role': 'model'}, 'index': 0}]}) + '\r\n\r\n'
SCRIPT = ["I count the reads.\n```bash\nwc -l data/NA12878_R1.fastq\nsamtools faidx data/reference.fa\nbgzip -c data/reference.fa > ref.fa.gz\n```", "REPORT\n14,076 lines: 3,519 reads."]
def gemini(route):
    body = json.loads(route.request.post_data or '{}')
    models = [c for c in body.get('contents', []) if c['role'] == 'model']
    last = body['contents'][-1]['parts'][0]['text']
    text = 'ready' if 'single word: ready' in last else SCRIPT[min(len(models), len(SCRIPT) - 1)]
    route.fulfill(status=200, headers=dict(H, **{'content-type': 'text/event-stream'}), body=sse(text))

with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        # ---------------- window sizes ----------------
        for w, hgt in ((1500, 950), (1280, 720), (1024, 768), (820, 1100), (390, 800)):
            b, page, logs = browser(pw, width=w, height=hgt)
            page.goto(f'http://127.0.0.1:{PORT}/index.html')
            page.wait_for_function('window.MG_READY === true', timeout=30000)
            page.wait_for_timeout(400)
            m = page.evaluate("""() => {
                const vis = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), shown: r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden' }; };
                return { sw: document.documentElement.scrollWidth, iw: window.innerWidth, tut: vis(document.querySelector('.chapter:not([hidden])')), term: vis(document.querySelector('#termRoot')), input: vis(document.querySelector('#termRoot input, #termRoot textarea')), tabs: vis(document.querySelector('[data-wb=assistant]')), nav: vis(document.querySelector('[data-goto], .chapnav, nav')) };
            }""")
            page.screenshot(path=f'{OUT}ui-{w}.png')
            check(f'{w}×{hgt}: nothing sticks out sideways', m['sw'] <= m['iw'] + 1, m)
            narrow = w <= 1000
            if narrow:
                # the workbench is behind a button, and slides over the instructions
                fab = page.evaluate("(() => { const r = document.querySelector('.bench-fab').getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth && r.bottom <= window.innerHeight; })()")
                check(f'{w}×{hgt}: the instructions fill the window; a Workbench button is on the screen', m['tut'] and m['tut']['shown'] and m['tut']['w'] > w * 0.9 and fab, m)
                page.click('.bench-fab'); page.wait_for_timeout(500)
            else:
                check(f'{w}×{hgt}: the instructions and the workbench tabs are there', m['tut'] and m['tut']['shown'] and m['tabs'] and m['tabs']['shown'], m)
            # the AI tab and the terminal can be reached and used
            page.click('.wb-tab[data-wb=assistant]'); page.wait_for_function('!!MG.app.ai'); page.wait_for_timeout(300)
            a = page.evaluate("""() => { const r = document.querySelector('.ai-connect [data-k=key]').getBoundingClientRect(); return { w: r.width, x: r.x, right: r.right, iw: window.innerWidth, y: r.y, ih: window.innerHeight }; }""")
            check(f'{w}×{hgt}: the key field of the AI tab is on the screen', a['w'] > 120 and a['x'] >= 0 and a['right'] <= a['iw'] + 1, a)
            page.screenshot(path=f'{OUT}ui-{w}-ai.png')
            page.click('.wb-tab[data-wb=terminal]'); page.wait_for_timeout(200)
            r = term(page, 'echo size-ok')
            check(f'{w}×{hgt}: the terminal works', 'size-ok' in r['text'], r)
            if narrow:
                page.screenshot(path=f'{OUT}ui-{w}-term.png')
                page.click('.bench-close'); page.wait_for_timeout(500)
                back = page.evaluate("!document.body.classList.contains('bench-open')")
                # a "show me" button opens the workbench and types the command
                page.evaluate("MG.app.showChapter('look', true)"); page.wait_for_timeout(300)
                page.click('#look [data-term]'); page.wait_for_timeout(900)
                check(f'{w}×{hgt}: the workbench closes again, and a “show me” button opens it with the command', back and page.evaluate("document.body.classList.contains('bench-open')") and page.evaluate('MG.app.term.input.value').startswith('cd ~ && ls -l data'), page.evaluate('MG.app.term.input.value'))
            b.close()

        # ---------------- what is kept, Start again, work file ----------------
        b = pw.chromium.launch(args=['--enable-unsafe-swiftshader', '--use-gl=swiftshader', '--ignore-gpu-blocklist'])
        ctx = b.new_context(viewport={'width': 1500, 'height': 950}, accept_downloads=True)
        page = ctx.new_page()
        logs = []
        page.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
        page.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'))
        page.route('https://generativelanguage.googleapis.com/**', gemini)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        ev = lambda js: page.evaluate(js)
        ready = lambda: (page.wait_for_function('window.MG_READY === true', timeout=30000), page.wait_for_timeout(1800))
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai')
        page.fill('.ai-connect [data-k=key]', 'GOOD'); page.click('.ai-connect [data-x=connect]')
        page.wait_for_function('MG.app.ai.connected()', timeout=20000)
        ev("MG.app.ai.showTab('agent')"); ev("MG.app.ai.setMode('auto')")
        page.fill('.ai-input', 'Count the reads.'); page.keyboard.press('Enter')
        page.wait_for_function("!MG.app.ai.busy && MG.app.ai.runs.length === 1", timeout=60000)
        term(page, 'cd ~ && echo "my note" > note.txt && printf "#!/bin/bash\\necho hi\\n" > s.sh && chmod +x s.sh && mkdir -p work && cd work && minimap2 -ax sr ~/data/reference.fa ~/data/NA12878_R1.fastq 2>/dev/null | samtools sort -o m.bam && samtools index m.bam && cd ~')
        # an answer and a ticked task
        page.evaluate("""() => { const q = document.querySelector('[data-q="s-q1"] textarea'); q.value = 'the commands and the line of the VCF'; q.dispatchEvent(new Event('input', { bubbles: true })); }""")
        page.wait_for_timeout(4000)   # IndexedDB is written a moment after the files are made
        kinds = lambda: json.loads(ev("JSON.stringify(Object.fromEntries(Array.from(MG.app.fs.entries).filter(([k, e]) => k.startsWith('/home/student/') && !e.protected && e.kind !== 'dir').map(([k, e]) => [k.slice(14), e.kind])))"))
        before = kinds()
        check('files exist: text and program output', before.get('note.txt') == 'text' and before.get('work/m.bam') in ('aioli', 'blob') and before.get('runs/1-auto/ref.fa.gz') in ('aioli', 'blob') and before.get('runs/1-auto/RUN.md') == 'text', before)
        idb = lambda: json.loads(page.evaluate("""() => new Promise((res) => { const rq = indexedDB.open('aiagents-files', 1); rq.onupgradeneeded = () => rq.result.createObjectStore('files', { keyPath: 'path' }); rq.onsuccess = () => { const t = rq.result.transaction('files').objectStore('files').getAllKeys(); t.onsuccess = () => { rq.result.close(); res(JSON.stringify(t.result)); }; }; rq.onerror = () => res('[]'); })"""))
        check('program output is in IndexedDB', '/home/student/work/m.bam' in idb() and '/home/student/runs/1-auto/ref.fa.gz' in idb(), idb())

        # reload: everything is back
        page.reload(); ready()
        after = kinds()
        check('reload: text files, program output, answer and run are back', after.get('note.txt') == 'text' and after.get('work/m.bam') == 'blob' and after.get('work/m.bam.bai') == 'blob' and after.get('runs/1-auto/RUN.md') == 'text' and 'the commands' in ev("document.querySelector('[data-q=\"s-q1\"] textarea').value"), after)
        r = term(page, 'samtools view -c ~/work/m.bam; cat ~/note.txt; ~/s.sh; zcat ~/runs/1-auto/ref.fa.gz | head -1')
        check('reload: the files work', r['text'].split('\n')[:4] == ['3525', 'my note', 'hi', '>human_CYP2C19'] or (r['text'].split('\n')[1:4] == ['my note', 'hi', '>human_CYP2C19']), r['text'])

        # Save all my work
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai')
        check('reload: still connected in this tab', ev('MG.app.ai.connected()'))
        page.click('#answersBtn'); page.wait_for_selector('.popmenu')
        with page.expect_download() as dl:
            page.click('.popmenu button:has-text("Save all my work")')
        path = OUT + 'work.json'
        dl.value.save_as(path)
        work = json.load(open(path))
        files = {e['p'][14:]: e for e in work['keys']['files']['entries']}
        raw = open(path).read()
        check('work file: answers, text files and the record of the run; no key, no program output', 'note.txt' in files and 'runs/1-auto/RUN.md' in files and 's.sh' in files and 'work/m.bam' not in files and 'GOOD' not in raw and 'the commands and the line' in raw and len(work['keys'].get('ai:runs', [])) == 1, list(files)[:30])
        check('work file: it is small', os.path.getsize(path) < 400000, os.path.getsize(path))

        # Start again
        page.click('#answersBtn'); page.wait_for_selector('.popmenu')
        page.click('.popmenu button:has-text("Start again")'); page.wait_for_selector('.modal [data-x=yes]')
        note = page.inner_text('.modal')
        check('Start again says what will be cleared', 'files' in note and 'API key' in note, note)
        page.click('.modal [data-x=yes]')
        page.wait_for_load_state('load'); ready()
        after = kinds()
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai')
        check('Start again: no files, no runs, no answers, no key', after == {} and ev('MG.app.ai.runs.length') == 0 and ev("document.querySelector('[data-q=\"s-q1\"] textarea').value") == '' and ev("sessionStorage.getItem('agents-ai-key')") is None and not ev('MG.app.ai.connected()'), after)
        check('Start again: IndexedDB is empty', idb() == [], idb())
        # the same folder is made again: nothing old may come back after a reload
        term(page, 'mkdir -p ~/work ~/runs/1-auto && echo new > ~/work/new.txt')
        page.wait_for_timeout(1200)
        page.reload(); ready()
        after = kinds()
        check('Start again: nothing old comes back when the folders are made again', after == {'work/new.txt': 'text'}, after)

        # Open my work
        page.click('#answersBtn'); page.wait_for_selector('.popmenu')
        with page.expect_file_chooser() as fc:
            page.click('.popmenu button:has-text("Open my work")')
        fc.value.set_files(path)
        page.wait_for_selector('.modal [data-x=yes]')
        note = page.inner_text('.modal')
        check('Open my work says what it replaces, and what is not in a work file', 'replaces' in note and 'API key' in note and 'BAM' in note, note)
        page.click('.modal [data-x=yes]')
        page.wait_for_load_state('load'); ready()
        after = kinds()
        ev("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.app.ai')
        check('Open my work: text files, answers and the run are back; program output is not', after.get('note.txt') == 'text' and after.get('runs/1-auto/RUN.md') == 'text' and 'work/m.bam' not in after and 'work/new.txt' not in after and 'the commands' in ev("document.querySelector('[data-q=\"s-q1\"] textarea').value") and ev('MG.app.ai.runs.length') == 1, after)
        r = term(page, 'cat ~/note.txt; ~/s.sh; ls ~/runs/1-auto | tr "\\n" " "')
        check('Open my work: the files work, the script is still executable', r['text'].split('\n')[:2] == ['my note', 'hi'] and 'RUN.md' in r['text'], r['text'])
        cards = ev("document.querySelectorAll('.ag.past .ag-pastrow').length")
        check('Open my work: the earlier run is listed in the AI tab', cards == 1, cards)
        bad = [l for l in logs if 'PAGEERROR' in l or (l.startswith('error') and 'Failed to load resource' not in l)]
        check('no errors in the page', not bad, bad[:5])
        b.close()

        # ---------------- settings of config.js ----------------
        b, page, logs = browser(pw)
        # config.js sets window.MG_CONFIG; change two of its values as a lecturer would by editing the file
        page.add_init_script("""Object.defineProperty(window, 'MG_CONFIG', { configurable: true, get() { return undefined; },
            set(v) { v.courseTitle = 'Genomics 7 – AI agents'; v.courseSubtitle = 'Week 9 practical'; v.hostname = 'lab7'; Object.defineProperty(window, 'MG_CONFIG', { value: v, writable: true, configurable: true }); } });""")
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        got = page.evaluate("({ title: document.querySelector('.brand-title').textContent, sub: document.querySelector('.brand-sub').textContent, tab: document.title, prompt: document.querySelector('#termRoot').textContent })")
        check('config.js: courseTitle, courseSubtitle and hostname are used', got['title'] == 'Genomics 7 – AI agents' and got['sub'] == 'Week 9 practical' and got['tab'] == 'Genomics 7 – AI agents – Week 9 practical' and 'lab7' in got['prompt'], got)
        b.close()
    finally:
        srv.terminate()
    fails = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(fails)} of {len(results)} passed')
    for f in fails:
        print('FAILED:', f[0], '–', str(f[2])[:1200])
