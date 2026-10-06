"""Screenshots of the chapters (tall viewport, so that a whole chapter is visible)."""
import sys, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8843
OUT = OUT_DIR + '/'
with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw, width=1400, height=int(sys.argv[1]) if len(sys.argv) > 1 else 2600)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        for ch in ['start', 'look', 'assistant', 'agent', 'repro', 'ref']:
            page.evaluate(f"MG.app.showChapter('{ch}', true)"); page.wait_for_timeout(400)
            h = page.evaluate("document.querySelector('.tut').scrollHeight")
            print(ch, 'height', h)
            page.locator('.tut').screenshot(path=OUT + f'ch-{ch}.png')
        print('\n'.join(l for l in logs if 'PAGEERROR' in l or l.startswith('error'))[:2000])
        b.close()
    finally:
        srv.terminate()
