/* =====================================================================
   "AI agents for bioinformatics" – page set-up: the file system with the
   data, the terminal (real WebAssembly programs), the files and editor,
   and the AI (a real model: chat assistant and agent).
   ===================================================================== */
(function () {
  'use strict';
  const MG = window.MG;
  const { esc, bus, toast, store } = MG;
  MG.app = MG.app || {};
  MG.checks = MG.checks || {};
  MG.actions = MG.actions || {};
  const CFG = MG.config;

  const HOME = '/home/student';
  const DATA = HOME + '/data';
  const DATA_TIME = Date.parse('2026-09-30T09:00:00Z');
  const FILES = [
    { name: 'NA12878_R1.fastq', size: 626445 },
    { name: 'NA12878_R2.fastq', size: 626445 },
    { name: 'reference.fa', size: 56963 },
    { name: 'MD5SUMS', size: 149 },
    { name: 'README.md', size: 1591 },
    { name: 'provenance.json', size: 4102 }
  ];
  MG.app.HOME = HOME;
  MG.app.DATA = DATA;
  MG.app.INPUTS = ['NA12878_R1.fastq', 'NA12878_R2.fastq', 'reference.fa'];
  const abs = (u) => new URL(u, location.href).href;

  function setupFs() {
    const fs = new MG.VFS(HOME);
    fs.mkdirp(DATA);
    fs.mkdirp('/tmp');
    fs.entries.get(DATA).protected = true;
    FILES.forEach((f) => fs.put(DATA + '/' + f.name, { kind: 'url', url: abs('data/' + f.name), size: f.size, protected: true, readonly: true, mtime: DATA_TIME }));
    const restored = MG.project.restore(fs);
    if (!restored) fs.cwd = HOME;
    // what programs wrote (BAM, VCF …) comes back from IndexedDB a moment later; then changes are watched
    const then = () => {
      MG.project.watch(fs);
      // a file that came back from a record under another name (it was renamed just before the page was closed) is stored under its own
      MG.project.saveBinary(fs);
      // files of the saved state that are not in this browser's storage: say so, once (they are not part of the next saved state)
      const gone = MG.project.missing || [];
      if (gone.length && MG.app.term) {
        MG.app.term.note(`Not in this browser’s storage, so not here any more: ${gone.slice(0, 6).map((p) => fs.pretty(p)).join(', ')}${gone.length > 6 ? ' and ' + (gone.length - 6) + ' more' : ''}. (A file that a program wrote in the last seconds before the page was closed, a very large file, or files from another computer.) Run the commands, or your script, again to make ${gone.length === 1 ? 'it' : 'them'}.`);
        toast(`Not here any more: <b>${gone.slice(0, 3).map((p) => esc(fs.pretty(p))).join(', ')}${gone.length > 3 ? ' …' : ''}</b> – the Terminal says why.`, 'warn', 9000);
        MG.project.save();
      }
      // records in the browser's storage that no file needs any more go – unless the page is open in another tab, whose files they may be
      setTimeout(() => MG.project.dropStale(fs, MG.app.alone).catch(() => {}), 3000);
    };
    MG.project.restoreBinary(fs, { manifest: true }).then(then, then);
    return fs;
  }
  /* The page in two tabs or windows of one browser: both keep their state in the same storage, and each would
     write over what the other has saved. Both say so. */
  function watchTabs() {
    if (!('BroadcastChannel' in window)) return;
    let ch;
    try {
      ch = new window.BroadcastChannel((CFG.storePrefix || 'practical') + '-tabs');
    } catch (e) {
      return;
    }
    const id = Math.random().toString(36).slice(2);
    const others = new Set();
    // Is this the only tab that has the page open? Each tab holds a lock of its own for as long as it lives (also a
    // tab in the background that the browser has put to sleep, which would not answer a message).
    const lockName = (CFG.storePrefix || 'practical') + '-tab-';
    const locks = window.navigator && window.navigator.locks;
    if (locks && locks.request && locks.query) {
      try {
        locks.request(lockName + id, () => new Promise(() => {})).catch(() => {});
      } catch (e) {
        /* no locks here */
      }
    }
    MG.app.alone = async () => {
      if (others.size) return false;
      if (!locks || !locks.query) return true;
      try {
        const q = await locks.query();
        return !(q.held || []).some((l) => l.name && l.name.startsWith(lockName) && l.name !== lockName + id);
      } catch (e) {
        return true;
      }
    };
    let bar = null, closed = false;
    const show = () => {
      if (others.size && !bar && !closed) {
        bar = document.createElement('div');
        bar.className = 'tabs-warning';
        bar.setAttribute('role', 'alert');
        bar.innerHTML = '<b>This practical is open in another tab or window of this browser.</b> Work in one of them only: both save to the same place, and each would write over what the other has saved. <button type="button" class="btn small">Close this note</button>';
        bar.querySelector('button').addEventListener('click', () => {
          closed = true;
          bar.remove();
          bar = null;
        });
        document.body.appendChild(bar);
      } else if (!others.size && bar) {
        bar.remove();
        bar = null;
      }
    };
    ch.onmessage = (ev) => {
      const m = ev.data || {};
      if (!m.id || m.id === id) return;
      if (m.t === 'hello') {
        others.add(m.id);
        ch.postMessage({ t: 'here', id });
      } else if (m.t === 'here') others.add(m.id);
      else if (m.t === 'bye') others.delete(m.id);
      show();
    };
    ch.postMessage({ t: 'hello', id });
    window.addEventListener('pagehide', () => ch.postMessage({ t: 'bye', id }));
    // (a page that the browser kept and shows again – Back, Forward – says that it is there again)
    window.addEventListener('pageshow', (ev) => ev.persisted && ch.postMessage({ t: 'hello', id }));
  }

  const page = (MG.page = MG.page || {});
  page.firstBench = 'terminal';

  page.init = function () {
    watchTabs();
    const fs = (MG.app.fs = setupFs());
    MG.app.term = new MG.TerminalUI(document.getElementById('termRoot'), {
      fs,
      hostname: CFG.hostname || 'biolab',
      welcome: 'A Linux-like terminal in your browser. The programs are real (fastp, minimap2, bowtie2, samtools, bcftools, GNU tools) and run here, on this computer. The data is in ~/data. Type  help  for the commands.'
    });
  };

  page.lazy = {
    editor: (pane) => (MG.app.editor = new MG.Editor(pane.querySelector('#edRoot'), { fs: MG.app.fs })),
    assistant: (pane) => {
      if (MG.Assistant && !MG.app.ai) MG.app.ai = new MG.Assistant(pane.querySelector('#aiRoot'), {});
    }
  };

  /* opening files from the terminal (open, nano) and from links */
  MG.app.editFile = async (path, opts = {}) => {
    MG.app.showWorkbench('editor');
    for (let i = 0; i < 40 && !MG.app.editor; i++) await new Promise((r) => setTimeout(r, 50));
    await MG.app.editor.openFile(path, opts);
  };
  MG.app.openFile = async (path, opts = {}) => MG.app.editFile(path, opts);
  const ai = async () => {
    MG.app.showWorkbench('assistant');
    for (let i = 0; i < 40 && !MG.app.ai; i++) await new Promise((r) => setTimeout(r, 50));
    return MG.app.ai;
  };

  /* ------------------------------------------------------------------
     buttons in the instructions
     data-term="cmd"        type a command into the terminal
     data-edit="path"       open a file in the editor
     data-prompt="text"     put a prompt into the AI's box (data-tab="chat|agent", data-mode="ask|plan|auto|script");
                            the student reads it, changes it if they like, and sends it
     data-connect           open the AI's connection settings
     ------------------------------------------------------------------ */
  const inHome = (p) => (p.startsWith('/') ? p : p.startsWith('~/') ? HOME + p.slice(1) : HOME + '/' + p);
  MG.actions.edit = async (path) => MG.app.editFile(inHome(path), { create: true });
  MG.actions.prompt = async (text, btn) => {
    const A = await ai();
    if (!A) return;
    A.offerPrompt(text, btn.dataset.tab || 'chat', btn.dataset.mode || null);
  };
  MG.actions.connect = async () => {
    const A = await ai();
    if (A) A.settingsDialog();
  };
  const codeOf = (btn) => {
    const box = btn.closest('.codefile');
    return box ? box.querySelector('pre').textContent : '';
  };
  MG.actions.fileCreate = async (rel, btn) => {
    const fs = MG.app.fs;
    const path = inHome(rel);
    const text = codeOf(btn).replace(/\s+$/, '') + '\n';
    const e = fs.get(path);
    if (e && (e.readonly || e.protected)) return toast(esc(fs.pretty(path)) + ' is read-only.', 'error');
    if (e && e.kind !== 'dir') {
      const old = await fs.readText(path);
      if (old === text) return MG.app.editFile(path, {});
      if (!window.confirm(`${fs.pretty(path)} already exists. Replace its contents with the version shown in the instructions?`)) return;
      const ed = MG.app.editor;
      if (ed && ed.open && ed.open.get(path)) ed.open.get(path).dirty = false;
    }
    if (MG.app.whenAgentIdle) await MG.app.whenAgentIdle();
    fs.mkdirp(MG.path.dirname(path));
    fs.writeText(path, text, e && e.mode ? { mode: e.mode } : {});
    await MG.app.editFile(path, { line: 1 });
    bus.emit('file:create', { path, name: path.split('/').pop() });
  };
  MG.actions.copyCode = async (v, btn) => toast((await MG.copyText(codeOf(btn))) ? 'Copied.' : 'Could not copy – select the text and copy it.', null, 1800);
  /* download a folder as a .zip (data-download="~/check|my-analysis.zip") */
  MG.actions.download = async (spec) => {
    const [dir, name] = spec.split('|');
    await MG.project.download(inHome(dir), name || dir.split('/').pop() + '.zip', {});
  };

  /* state checks for tasks (data-check="name:arg") */
  const textOf = (rel) => {
    const e = MG.app.fs && MG.app.fs.get(inHome(rel));
    return e && e.kind === 'text' ? e.text : null;
  };
  MG.checks.exists = (t, d, path) => !!MG.app.fs && MG.app.fs.exists(inHome(path));
  MG.checks.has = (t, d, arg) => {
    const cut = arg.indexOf('|');
    const txt = textOf(arg.slice(0, cut));
    return txt != null && new RegExp(arg.slice(cut + 1), 'm').test(txt);
  };
  MG.checks.connected = () => !!(MG.app.ai && MG.app.ai.connected());
  /* a finished agent run of a kind: runs:auto, runs:auto:2 (at least two), runs:any */
  MG.checks.runs = (t, d, arg) => {
    const [mode, n] = String(arg || 'any').split(':');
    const A = MG.app.ai;
    if (!A) return false;
    return A.runs.filter((r) => (r.outcome === 'done' || r.outcome === 'limit') && (mode === 'any' || r.mode === mode)).length >= +(n || 1);
  };

  page.resetNote = ', and also your files, the agent’s runs and your API key (download anything you want to keep first)';
  page.workNote = 'everything this page has saved in this browser: your ticks and answers, your files and the records of the agent’s runs. (A work file does not hold your API key, nor the large files that programs wrote, such as BAM files – a script makes those again.)';
  page.onReset = (why) => {
    MG.project.reset();
    MG.project.save = () => {}; // do not write the old files back while the page reloads
    ['ai:settings', 'ai:agentMode', 'ai:runs', 'ai:ok'].forEach((k) => store.remove(k));
    // "Start again" also forgets the key: the next person at this computer must not work with it
    if (why !== 'open') {
      try {
        window.sessionStorage.removeItem('agents-ai-key');
      } catch (e) {
        /* no session storage */
      }
    }
  };
  /* a work file was opened: what programs wrote in this browser before does not belong to it */
  page.onOpenWork = (setKey) => setKey('filesFrom', Date.now());
  /* "Save all my work": the files as they are in the page now (the browser's storage may be full, and behind) – and the
     runs of the agent */
  page.workKeys = () => {
    const out = { files: MG.project.snapshot(MG.app.fs) };
    if (MG.app.ai && Array.isArray(MG.app.ai.runs)) out['ai:runs'] = MG.app.ai.runs;
    return out;
  };
  /* before "Save all my work": write everything to the browser's storage now */
  page.beforeSaveWork = async () => {
    const ed = MG.app.editor;
    const dirty = ed && ed.dirtyPaths ? ed.dirtyPaths() : [];
    if (dirty.length) {
      const go = await new Promise((resolve) => {
        const m = MG.modal('Unsaved changes', `<p>These files have changes in the editor that are not saved yet: <b>${dirty.map((p) => MG.esc(MG.app.fs.pretty(p))).join(', ')}</b>. The work file will contain the <i>saved</i> versions.</p><div class="prompt-actions"><button class="btn" data-x="no" type="button">Cancel – I will save them first</button><button class="btn primary" data-x="yes" type="button">Continue</button></div>`);
        m.box.querySelector('[data-x="no"]').addEventListener('click', () => { m.close(); resolve(false); });
        m.box.querySelector('[data-x="yes"]').addEventListener('click', () => { m.close(); resolve(true); });
      });
      if (!go) return false;
    }
    MG.project.save();
    return true;
  };
  page.help = function () {
    MG.modal(
      'How this page works',
      `<ul>
<li><b>Instructions</b> are on the left, the <b>workbench</b> on the right: Terminal, Files and AI. Drag the divider to resize.</li>
<li><b>Terminal</b>: a Linux-like shell. The programs are real – fastp, minimap2, Bowtie 2, samtools, bcftools and the GNU tools, compiled to WebAssembly – and run in your browser, on this computer. Type <code>help</code> for the list.</li>
<li><b>Files</b>: your folders and an editor. Save with <kbd>Ctrl</kbd>+<kbd>S</kbd> – commands in the terminal use the saved files.</li>
<li><b>AI</b>: a real AI model, which needs an API key (Google Gemini has a free tier). <b>Chat</b> answers questions – you run the commands. <b>Agent</b> carries out a task itself, in a folder of its own under <code>~/runs</code>; you choose how much it may do without asking you.</li>
<li><b>show me</b> buttons in the instructions type a command for you (press <kbd>Enter</kbd> to run it); <b>prompt</b> buttons put a prompt into the AI’s box for you to read, change and send.</li>
<li><b>Your key</b> stays in this browser tab and is sent only to the AI service you chose. What you type, and what the agent’s commands print, goes to that service – never type personal or patient data.</li>
<li><b>Saved in this browser:</b> your ticks and answers, your files and the records of the agent’s runs – they are still there after a reload. Your key is kept for this tab only, until you close it; on a shared computer, disconnect before you leave (⚙ in the AI tab → <b>Disconnect</b>), or use <b>Start again</b>. <b>My answers</b> downloads your answers.</li>
<li><b>Another computer?</b> <b>My answers → Save all my work to a file</b>, then <b>Open my work from a file</b> on the other computer. The file holds your answers and your text files (scripts, records, notes); the large files that programs wrote (BAM, compressed VCF) are not in it – run your script again to make them. (Lab computers may clear the browser’s storage when you log out.)</li>
<li>To start again from scratch: <b>My answers → Start again</b>.</li>
</ul>`
    );
  };
})();
