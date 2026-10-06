"""What programs wrote is kept in the browser (IndexedDB) and comes back after a reload and after a forced stop –
as it was, or not at all and with a message: never as an older version, never a file that had been removed.
Also: the page open in two tabs."""
import sys, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8872
H = '/home/student'
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  – {detail}'), flush=True)


IDB = """async () => {
    const db = await new Promise((res, rej) => { const rq = indexedDB.open('aiagents-files', 1); rq.onsuccess = () => res(rq.result); rq.onerror = () => rej(rq.error); rq.onupgradeneeded = () => rq.result.createObjectStore('files', { keyPath: 'path' }); });
    const recs = await new Promise((res, rej) => { const rq = db.transaction('files', 'readonly').objectStore('files').getAll(); rq.onsuccess = () => res(rq.result); rq.onerror = () => rej(rq.error); });
    const out = {};
    for (const r of recs) out[r.path.replace('/home/student/', '')] = MG.md5(new Uint8Array(await r.blob.arrayBuffer()));
    db.close();
    return out;
}"""

with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b = pw.chromium.launch(args=['--enable-unsafe-swiftshader', '--use-gl=swiftshader', '--ignore-gpu-blocklist'])
        ctx = b.new_context(viewport={'width': 1500, 'height': 950})
        page = ctx.new_page()
        logs = []
        page.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
        page.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'))

        def load(p=page):
            p.goto(f'http://127.0.0.1:{PORT}/index.html')
            p.wait_for_function('window.MG_READY === true', timeout=30000)
            p.wait_for_timeout(700)   # program output comes back from IndexedDB a moment later

        def reload_now():
            page.reload()
            page.wait_for_function('window.MG_READY === true', timeout=30000)
            page.wait_for_timeout(700)

        ev = page.evaluate
        sh = lambda c: term(page, c)
        out = lambda c: term(page, c)['text'].strip()
        md5 = lambda names: dict(l.split()[::-1] for l in out('cd ~; md5sum ' + names + ' 2>/dev/null').split('\n') if len(l.split()) == 2)
        notes = lambda: ev("Array.from(MG.app.term.outEl.querySelectorAll('.note')).map(e => e.textContent)")
        idb = lambda: ev(IDB)
        binaries = lambda: sorted(ev("Array.from(MG.app.fs.entries).filter(([k, e]) => k.startsWith('/home/student/') && !e.protected && (e.kind === 'aioli' || e.kind === 'blob')).map(([k]) => k.slice(14))"))

        load()
        sh('cd ~; minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq 2>/dev/null | samtools sort -o a.bam; samtools view -b -o c.bam a.bam; bgzip -c data/reference.fa > r.gz; echo note > notes.txt')
        first = md5('a.bam c.bam r.gz')
        page.wait_for_timeout(4000)
        check('program output is written to the browser\'s storage: the files and their bytes', idb() == first and len(first) == 3, (idb(), first))

        # ---- a reload
        reload_now()
        check('reload: every file is back with its bytes, nothing is reported missing', md5('a.bam c.bam r.gz') == first and ev('MG.project.missing.length') == 0 and not any('storage' in n for n in notes()), (md5('a.bam c.bam r.gz'), notes()))

        # ---- renamed and removed, then a reload at once
        sh('cd ~; mv a.bam b.bam; rm c.bam')
        reload_now()
        got = md5('a.bam b.bam c.bam r.gz')
        check('reload right after mv and rm: the removed file and the old name are not back; the renamed file is, with its bytes', got == {'b.bam': first['a.bam'], 'r.gz': first['r.gz']}, got)
        page.wait_for_timeout(5500)   # (records that no file needs go 3 s after the page was loaded – if no other tab has it open)
        check('… and the storage then holds exactly the files that exist', idb() == got and binaries() == ['b.bam', 'r.gz'], (idb(), binaries()))

        # ---- written again, then a reload at once: not the older version
        sh('cd ~; bgzip -c data/NA12878_R1.fastq > r.gz')
        new = md5('r.gz')['r.gz']
        reload_now()
        got = md5('r.gz')
        n = [x for x in notes() if 'Not in this browser' in x]
        check('reload right after a file was written again: the file is the new version, or is gone and named – never the old version', new != first['r.gz'] and (got == {'r.gz': new} or (got == {} and len(n) == 1 and '~/r.gz' in n[0])), (got, n))
        page.wait_for_timeout(5500)
        check('… and the old version is not in the storage any more', idb().get('r.gz') in (None, new) and 'b.bam' in idb(), idb())
        reload_now()
        check('… the message comes once', not [x for x in notes() if 'Not in this browser' in x], notes())

        # ---- the student's forced stop
        sh('cd ~; samtools view -b -o d.bam b.bam; samtools view -h -o big.sam b.bam; bgzip -c data/reference.fa > s.gz')
        page.wait_for_timeout(4000)
        before = md5('b.bam d.bam big.sam s.gz')
        # in the seconds before the stop: one file renamed, one touched, one write-protected, one written again, one new
        ev("""(() => { window.__hang = MG.app.term.exec("cd ~; mv d.bam e.bam; touch b.bam; chmod a-w s.gz; samtools view -h -o big.sam -s 0.5 b.bam; samtools view -b -o fresh.bam b.bam; awk 'BEGIN { while (1) { } }'"); })()""")
        page.wait_for_function("MG.wasm.running === 'gawk'", timeout=60000)
        page.wait_for_timeout(500)
        ev("(() => { MG.app.term.stop(); MG.app.term.stop(true); })()")
        ev("window.__hang")
        page.wait_for_timeout(1500)
        after = md5('b.bam d.bam e.bam big.sam s.gz fresh.bam')
        ns = ' '.join(notes()[-3:])
        check('forced stop: a renamed file is back under its new name with its bytes; the old name is not', after.get('e.bam') == before['d.bam'] and 'd.bam' not in after, after)
        check('forced stop: a file that was only touched, and one whose permissions changed, are back as they were – and not called an earlier version', after.get('b.bam') == before['b.bam'] and after.get('s.gz') == before['s.gz'] and '~/b.bam' not in ns and '~/s.gz' not in ns and 'Permission denied' in out('cd ~; echo x >> s.gz'), (after, ns))
        check('forced stop: a file written again is back as the earlier version, and named; a new file is lost, and named', after.get('big.sam') == before['big.sam'] and 'fresh.bam' not in after and 'Back as an earlier version' in ns and '~/big.sam' in ns.split('Back as an earlier version')[1] and 'Lost with the stopped program: ~/fresh.bam' in ns, (after, ns))
        check('forced stop: the programs work again, on the files that came back', out('cd ~; samtools view -c e.bam; zcat s.gz | head -1 | cut -c1-6') == '7038\n>human', out('cd ~; samtools view -c e.bam'))
        page.wait_for_timeout(4000)
        check('… and the storage then holds exactly the files that exist', idb() == md5(' '.join(binaries())) and 'd.bam' not in idb(), (idb(), binaries()))
        reload_now()
        check('… and they are the same after a reload', md5('b.bam e.bam big.sam s.gz') == {k: v for k, v in after.items()}, md5('b.bam e.bam big.sam s.gz'))

        # ---- the page in two tabs of one browser
        page2 = ctx.new_page()
        page2.on('pageerror', lambda e: logs.append(f'PAGEERROR (tab 2): {e}'))
        load(page2)
        page.wait_for_timeout(400)
        both = [p.evaluate("!!document.querySelector('.tabs-warning')") for p in (page, page2)]
        check('two tabs: both say that the page is open twice', both == [True, True], both)
        sh('cd ~; samtools view -b -o tab1.bam b.bam')
        page.wait_for_timeout(4000)
        term(page2, 'cd ~; echo note > from_tab2.txt; samtools --version > /dev/null')
        page2.wait_for_timeout(4000)
        check('two tabs: the second tab does not delete what the first has stored since', 'tab1.bam' in idb(), sorted(idb()))
        # … not when it is loaded again, either: the state it loads does not name the first tab's new file
        page2.reload()
        page2.wait_for_function('window.MG_READY === true', timeout=30000)
        page2.wait_for_timeout(5500)
        check('two tabs: the second tab, loaded again, does not delete it either – and does not take it for its own', 'tab1.bam' in idb() and not page2.evaluate("MG.app.fs.exists('/home/student/tab1.bam')") and page2.evaluate("MG.app.fs.exists('/home/student/b.bam')"), sorted(idb()))
        check('two tabs: each knows that it is not alone', [p.evaluate('MG.app.alone()') for p in (page, page2)] == [False, False])
        page2.close()
        page.wait_for_timeout(500)
        check('two tabs: the note goes when the other tab is closed, and the tab that is left knows that it is alone', not ev("!!document.querySelector('.tabs-warning')") and ev('MG.app.alone()') is True)
        reload_now()
        check('two tabs: after a reload the first tab has its files', md5('tab1.bam b.bam') .keys() == {'tab1.bam', 'b.bam'}, md5('tab1.bam b.bam'))

        # ---- the viewer of tables: two changes of the shown file in one moment do not double what is shown
        sh("cd ~; printf 'a\\tb\\n1\\t2\\n' > table.tsv")
        ev("MG.app.editFile('/home/student/table.tsv', {})")
        page.wait_for_timeout(400)
        ev("(() => { const fs = MG.app.fs; fs.writeText('/home/student/table.tsv', 'x\\ty\\n3\\t4\\n'); fs.writeText('/home/student/table.tsv', 'x\\ty\\n5\\t6\\n'); })()")
        page.wait_for_timeout(600)
        cells = ev("Array.from(document.querySelectorAll('.ed-table th, .ed-table td')).map(e => e.textContent).join('|')")
        check('the table viewer shows the file once, also after two changes in one moment', cells == 'x|y|5|6', cells)

        # ---- a file that a program wrote and that is too large to be kept: said when it is made
        sh('cd ~; cat data/NA12878_R1.fastq data/NA12878_R1.fastq data/NA12878_R1.fastq data/NA12878_R1.fastq data/NA12878_R1.fastq data/NA12878_R1.fastq data/NA12878_R1.fastq data/NA12878_R1.fastq > part.txt; cat part.txt part.txt part.txt part.txt part.txt part.txt part.txt part.txt part.txt > huge.txt; rm part.txt')
        page.wait_for_function("Array.from(document.querySelectorAll('.toast')).some(e => e.textContent.includes('larger than 40 MB'))", timeout=30000)
        told = ev("Array.from(document.querySelectorAll('.toast')).map(e => e.textContent).filter(t => t.includes('larger than 40 MB'))")
        check('a file of a program that is larger than 40 MB: the page says at once that it will not be kept', len(told) == 1 and '~/huge.txt' in told[0] and 'huge.txt' not in idb(), told)
        sh('cd ~; touch huge.txt; echo x > small.txt')
        page.wait_for_timeout(4000)
        told = ev("Array.from(document.querySelectorAll('.toast')).map(e => e.textContent).filter(t => t.includes('larger than 40 MB'))")
        check('… once', len(told) <= 1, told)
        sh('cd ~; rm huge.txt')

        # ---- the browser's storage for the state is full: what programs wrote after that is not lost at the next load
        sh('cd ~; bgzip -c data/reference.fa > sa.gz')
        page.wait_for_function("!MG.project._saving && MG.project.binaryOf(MG.app.fs).every(([p, e]) => MG.project.kept.get(p) === e)", timeout=30000)
        page.wait_for_timeout(1500)
        ev("""(() => { const chunk = 'x'.repeat(100000);
            try { for (let i = 0; i < 400; i++) localStorage.setItem('otherpage:junk' + i, chunk); } catch (e) {}
            try { for (let i = 0; i < 4000; i++) localStorage.setItem('otherpage:s' + i, 'y'.repeat(300)); } catch (e) {} })()""")
        sh('cd ~; head -c 20000 data/reference.fa > t2.txt; mv sa.gz sa_renamed.gz; bgzip -c data/README.md > sb.gz')
        page.wait_for_function("Array.from(document.querySelectorAll('.toast')).some(e => e.textContent.includes('storage is full'))", timeout=30000)
        page.wait_for_function("!MG.project._saving && MG.project.binaryOf(MG.app.fs).every(([p, e]) => MG.project.kept.get(p) === e)", timeout=30000)
        page.wait_for_timeout(1500)
        want = md5('sa_renamed.gz sb.gz')
        page.click('#answersBtn'); page.wait_for_selector('.popmenu')
        with page.expect_download() as dl:
            page.click('.popmenu button:has-text("Save all my work")')
        wpath = os.path.join(OUT_DIR, 'store-work.json')
        dl.value.save_as(wpath)
        wfiles = {e['p'][14:]: e for e in json.load(open(wpath))['keys']['files']['entries']}
        check('storage full: "Save all my work" still saves the files as they are now', 't2.txt' in wfiles and len(wfiles['t2.txt'].get('t', '')) == 20000, sorted(wfiles)[:20])
        check('storage full: the student is told – in the terminal, too', any('Your browser storage is full' in x for x in notes()), notes()[-3:])
        reload_now()
        got = md5('sa.gz sa_renamed.gz sb.gz')
        n = [x for x in notes() if 'Not in this browser' in x]
        check('storage full, a reload in the same tab: the state was kept for the tab – program output and text files are as they were, nothing is named as missing', len(want) == 2 and got == want and not n and ev("(MG.app.fs.get('/home/student/t2.txt') || { text: '' }).text.length") == 20000, (got, want, n))
        page.wait_for_timeout(4500)
        check('… they are still in the storage after the tidying', set(want.items()) <= set(idb().items()), idb())
        # … also when files were removed, renamed and written again in the last moment before the page is loaded again
        sh('cd ~; bgzip -c data/MD5SUMS > qb.gz; bgzip -c data/README.md > qc.gz; bgzip -c data/reference.fa > qd.gz')
        page.wait_for_function("!MG.project._saving && MG.project.binaryOf(MG.app.fs).every(([p, e]) => MG.project.kept.get(p) === e)", timeout=30000)
        page.wait_for_timeout(1200)
        qc = md5('qc.gz')['qc.gz']
        sh('cd ~; rm qb.gz; mv qc.gz qc2.gz; bgzip -c data/NA12878_R1.fastq > qd.gz')
        qd = md5('qd.gz')['qd.gz']
        reload_now()
        got = md5('qb.gz qc.gz qc2.gz qd.gz')
        n = ' '.join(x for x in notes() if 'Not in this browser' in x)
        check('storage full, a reload right after rm, mv and a rewrite: the removed file and the old name are not back; the renamed file is; the rewritten one is the new version, or gone and named', 'qb.gz' not in got and 'qc.gz' not in got and got.get('qc2.gz') == qc and (got.get('qd.gz') == qd or ('qd.gz' not in got and '~/qd.gz' in n)), (got, n))
        # a new tab does not have the state that was kept for the first one: it has the older state of the storage –
        # and what programs wrote after that state still comes back
        page.wait_for_timeout(4500)
        stored = idb()
        page.close()
        page3 = ctx.new_page()
        page3.on('pageerror', lambda e: logs.append(f'PAGEERROR (tab 3): {e}'))
        load(page3)
        there = page3.evaluate("Array.from(MG.app.fs.entries.keys()).filter(k => /\\/(sa|sa_renamed|sb|qb|qc|qc2)\\.gz$/.test(k)).map(k => k.slice(14)).sort()")
        n3 = ' '.join(page3.evaluate("Array.from(MG.app.term.outEl.querySelectorAll('.note')).map(e => e.textContent)"))
        check('storage full, a new tab: the program output that was written after the last saved state is there; the file that this state still names is named', there == ['qc2.gz', 'sa_renamed.gz', 'sb.gz'] and '~/sa.gz' in n3 and 'Not in this browser' in n3, (there, n3[-300:], sorted(stored)))
        page3.evaluate("(() => { Object.keys(localStorage).filter(k => k.startsWith('otherpage:')).forEach(k => localStorage.removeItem(k)); })()")

        errors = [l for l in logs if 'PAGEERROR' in l]
        check('no errors in the page', not errors, errors[:5])
        b.close()
    finally:
        srv.terminate()
print(f'\n{sum(results)} of {len(results)} passed')
