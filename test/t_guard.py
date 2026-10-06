"""Read-only inputs stay as they are, and a program that does not end can be stopped."""
import sys, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8831
with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        def run(c):
            t0 = time.time(); r = term(page, c)
            print(f'$ {c}\n  -> exit {r["code"]} ({time.time()-t0:.1f} s)\n' + '\n'.join('     ' + l[:220] for l in r['text'].strip().split('\n')[-8:]) + '\n', flush=True)
            return r
        run('md5sum data/NA12878_R1.fastq')
        run('seqtk seq -A data/NA12878_R1.fastq > out.fa; ls -l out.fa')
        # a program told to write over its own read-only input: Permission denied, not an endless loop
        page.evaluate("() => { window.__p = MG.app.term.exec('fastp -i data/NA12878_R1.fastq -o data/NA12878_R1.fastq -h f.html -j f.json').then((c) => (window.__done = c)); }")
        for i in range(40):
            time.sleep(0.5)
            if page.evaluate('window.__done !== undefined'): break
        print('fastp over its input finished:', page.evaluate('window.__done'), flush=True)
        print(page.evaluate("Array.from(MG.app.term.outEl.children).slice(-3).map(e => e.textContent).join('|').slice(-500)"))
        if page.evaluate('window.__done === undefined'):
            print('still running -> force stop'); print(page.evaluate('MG.app.term.stop(true)'))
            time.sleep(1); print('done after kill:', page.evaluate('window.__done'))
        run('md5sum data/NA12878_R1.fastq; ls')
        run('sed -i "s/A/C/" data/reference.fa; echo "exit $?"; md5sum data/reference.fa')
        run('sort -o data/MD5SUMS data/MD5SUMS; echo "exit $?"')
        run('samtools faidx data/reference.fa && ls data')
        run('touch mine.txt && chmod -w mine.txt && sed -i "s/a/b/" mine.txt; echo "exit $?"; chmod +w mine.txt && echo text > mine.txt && sed -i "s/t/T/" mine.txt && cat mine.txt')
        # force stop of a running program: awk in an endless loop
        page.evaluate("() => { window.__done = undefined; MG.app.term.exec(\"awk 'BEGIN { while (1) { } }'; echo after\").then((c) => (window.__done = c)); }")
        time.sleep(3)
        print('awk loop running:', page.evaluate('MG.wasm.running'), 'done:', page.evaluate('window.__done'))
        print('first stop:', page.evaluate('MG.app.term.stop()'))
        time.sleep(1)
        print('second stop (lost):', page.evaluate('MG.app.term.stop()'))
        time.sleep(1)
        print('exit after kill:', page.evaluate('window.__done'))
        print(page.evaluate("Array.from(MG.app.term.outEl.children).slice(-4).map(e => e.textContent).join(' | ').slice(-700)"))
        run('ls; ls data')
        run('seqtk seq -A data/NA12878_R1.fastq | head -2; md5sum data/reference.fa')
        print('\n'.join(l for l in logs if 'PAGEERROR' in l)[:2000])
        b.close()
    finally:
        srv.terminate()
