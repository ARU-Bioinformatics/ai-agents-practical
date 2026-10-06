"""Playwright helpers for the tests of the practical.
Each test serves the site with ../serve.py on its own port and drives it in headless Chromium."""
import os, subprocess, time, json, sys, re
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # the site
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')  # screenshots, downloads, work files
os.makedirs(OUT_DIR, exist_ok=True)


def server(port=8820, root=ROOT):
    p = subprocess.Popen([sys.executable, os.path.join(root, 'serve.py'), str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    return p


def browser(pw, width=1500, height=950):
    b = pw.chromium.launch(args=['--enable-unsafe-swiftshader', '--use-gl=swiftshader', '--ignore-gpu-blocklist'])
    ctx = b.new_context(viewport={'width': width, 'height': height})
    page = ctx.new_page()
    logs = []
    page.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
    page.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'))
    return b, page, logs


def term(page, line, timeout=600000):
    """run a command in the terminal and return {code, text}"""
    return page.evaluate("""async ([line]) => {
        const T = MG.app.term;
        const before = T.outEl.children.length;
        const code = await T.exec(line);
        const els = Array.from(T.outEl.children).slice(before + 1);
        return { code, text: els.map(e => e.textContent + (e.classList.contains('note') ? '\\n' : '')).join('') };
    }""", [line])
