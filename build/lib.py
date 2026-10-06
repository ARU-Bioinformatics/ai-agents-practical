"""Helpers that write the HTML of the instructions (used by chapters.py)."""
import html


def esc(s):
    return html.escape(str(s), quote=True)


def c(s):
    """inline code"""
    return f'<code>{esc(s)}</code>'


def show(cmd, label='show me'):
    """a button that types a command into the terminal (the student presses Enter)"""
    return f'<button class="do showme" type="button" data-term="{esc(cmd)}">{label}</button>'


def cmd(line, label='show me'):
    """a command, with a button that types it"""
    return f'{c(line)} {show(line, label)}'


def edit(path, label=None):
    return f'<button class="do showme" type="button" data-edit="{esc(path)}">{label or "open " + esc(path.split("/")[-1])}</button>'


def bench(name, label):
    return f'<button class="do showme" type="button" data-bench="{esc(name)}">{label}</button>'


def goto(target, label):
    return f'<button class="do showme" type="button" data-goto="{esc(target)}">{label}</button>'


def prompt(text, tab='chat', mode=None, title=None, button=None):
    """a prompt for the AI, shown in full; the button puts it into the AI's box (the student sends it)"""
    t = title or ('A prompt for the assistant' if tab == 'chat' else 'A task for the agent')
    m = f' data-mode="{esc(mode)}"' if mode else ''
    b = button or ('Put it in the chat box' if tab == 'chat' else 'Put it in the agent’s box')
    return (f'<div class="prompt-card"><div class="pc-head"><span class="pc-t">{t}</span><span class="grow"></span>'
            f'<button class="do ask" type="button" data-prompt="{esc(text)}" data-tab="{esc(tab)}"{m}>{b}</button></div>'
            f'<div class="pc-text">{esc(text)}</div></div>')


def codefile(path, text, create=True, note=None, button='Create this file'):
    """a file shown in the instructions, with Create and Copy buttons"""
    b = f'<button class="do" type="button" data-file-create="{esc(path)}">{button}</button>' if create else ''
    n = f'<div class="cf-note">{note}</div>' if note else ''
    return (f'<div class="codefile" data-path="{esc(path)}"><div class="cf-head"><span class="cf-name">{esc(path)}</span>'
            f'<span class="grow"></span>{b}<button class="btn small" type="button" data-copy-code="1">Copy</button></div>'
            f'<pre class="codeblock">{esc(text.rstrip())}</pre>{n}</div>')


def task(tid, body, auto=None, check=None):
    a = f' data-auto="{esc(auto)}"' if auto else ''
    k = f' data-check="{esc(check)}"' if check else ''
    return f'<li data-task="{esc(tid)}"{a}{k}>{body}</li>'


def activity(title, tasks, extra=''):
    return f'<div class="activity">\n  <div class="act-t">{title}</div>\n  <ol class="steps">\n    ' + '\n    '.join(tasks) + f'\n  </ol>{extra}\n</div>'


def q(qid, text, model, accept=None, hint=None, placeholder=None):
    a = f' data-accept="{esc(accept)}"' if accept else ''
    h = f' data-hint="{esc(hint)}"' if hint else ''
    p = f' data-placeholder="{esc(placeholder)}"' if placeholder else ''
    return f'<div class="q" data-q="{esc(qid)}"{a}{h}{p}>\n  <div class="q-text">{text}</div>\n  <div class="q-model">{model}</div>\n</div>'


def mcq(qid, text, options, model=None):
    """options: list of (html, correct, why)"""
    labs = ''.join(f'<label{" data-correct" if ok else ""} data-why="{esc(why)}"><input type="radio"> {opt}</label>' for opt, ok, why in options)
    m = f'\n  <div class="q-model">{model}</div>' if model else ''
    return f'<div class="q" data-q="{esc(qid)}" data-type="mcq">\n  <div class="q-text">{text}</div>\n  <div class="mcq">{labs}</div>{m}\n</div>'


def callout(kind, title, body):
    return f'<div class="callout {kind}">\n  <div class="co-t">{title}</div>\n  {body}\n</div>'


def chapter(cid, num, title, bench_name, h1, minutes, lede, body):
    t = f'  <div class="meta-row"><span class="pill time">≈ {minutes} min</span></div>\n' if minutes else ''
    return (f'<section class="chapter" id="{cid}" data-num="{num}" data-title="{esc(title)}" data-bench="{bench_name}" hidden>\n'
            f'  <h1>{h1}</h1>\n{t}  <p class="lede">{lede}</p>\n{body}\n</section>\n')
