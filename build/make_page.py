"""Write ../index.html: the page shell (template.html) with the chapters (chapters.py) in it.
Run:  python3 make_page.py"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chapters

html = '\n'.join(chapters.ALL())
# the first chapter is visible when the page loads
html = html.replace(' hidden>', '>', 1)
shell = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
a = shell.index('<!--CHAPTERS-->') + len('<!--CHAPTERS-->')
b = shell.index('<!--/CHAPTERS-->')
open(os.path.join(HERE, '..', 'index.html'), 'w', encoding='utf-8').write(shell[:a] + '\n' + html + shell[b:])
# every task and question needs its own name
for what, pat in (('task', r'data-task="([^"]+)"'), ('question', r'data-q="([^"]+)"'), ('heading', r'<h2 id="([^"]+)"')):
    ids = re.findall(pat, html)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    print(f'{len(ids)} {what}s' + (f' – used twice: {dup}' if dup else ''))
print(len(html), 'bytes of chapters')
