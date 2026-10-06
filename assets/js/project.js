/* =====================================================================
   The student's files: kept in this browser between visits, and
   downloadable as a .zip.

   Text files (scripts, records of the agent's runs, notes, small tables)
   and copies of the course data are kept in the browser's localStorage,
   and are part of "Save all my work to a file".
   What programs wrote (BAM, compressed VCF, large files) is kept in the
   browser's IndexedDB – in this browser only. It is not in the work
   file: a script makes it again, which is rather the point.
   ===================================================================== */
(function () {
  'use strict';
  const MG = window.MG;
  const { store, bus, toast, esc } = MG;
  const HOME = '/home/student';
  const MAX_TEXT = 300000;
  const MAX_TOTAL = 3500000;
  const MAX_BINARY = 40e6; // one file
  const DB_NAME = ((MG.config && MG.config.storePrefix) || 'practical') + '-files';

  /* ---- IndexedDB: path -> { path, blob, mtime, mode, readonly, saved, id } ----
     id names the bytes of a record. A file whose bytes are those of a record carries that id (entry.kid) – also after
     it was renamed, copied, touched or had its permissions changed, which leaves the bytes as they are. */
  const newId = () => Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 9);
  /** the records that can be used: complete, and not from before the last "Start again" or "Open my work" */
  const usable = (recs) => {
    const from = store.get('filesFrom', 0);
    return (recs || []).filter((r) => r && r.path && r.blob && !(r.saved < from));
  };
  const blobEntry = (r, like) => ({ kind: 'blob', blob: r.blob, mtime: (like || r).mtime, mode: (like || r).mode || undefined, readonly: (like || r).readonly || undefined, kid: r.id || undefined });
  const sameFlags = (r, e) => r.mtime === e.mtime && !!r.readonly === !!e.readonly && (r.mode || '') === (e.mode || '');
  const idb = {
    open() {
      if (!this.ready) {
        this.ready = new Promise((resolve, reject) => {
          let rq;
          try {
            rq = window.indexedDB.open(DB_NAME, 1);
          } catch (e) {
            return reject(e);
          }
          rq.onupgradeneeded = () => rq.result.createObjectStore('files', { keyPath: 'path' });
          rq.onsuccess = () => resolve(rq.result);
          rq.onerror = () => reject(rq.error);
        });
        this.ready.catch(() => {});
      }
      return this.ready;
    },
    async tx(mode, fn) {
      const db = await this.open();
      return new Promise((resolve, reject) => {
        const t = db.transaction('files', mode);
        const out = fn(t.objectStore('files'));
        t.oncomplete = () => resolve(out && out.result !== undefined ? out.result : undefined);
        t.onerror = t.onabort = () => reject(t.error);
      });
    },
    put: (rec) => idb.tx('readwrite', (st) => st.put(rec)),
    del: (path) => idb.tx('readwrite', (st) => st.delete(path)),
    /** delete the record of a path – if it is still the one with this id */
    delIf: (path, id) =>
      idb.tx('readwrite', (st) => {
        const rq = st.get(path);
        rq.onsuccess = () => rq.result && rq.result.id === id && st.delete(path);
      }),
    all: () => idb.tx('readonly', (st) => st.getAll()),
    keys: () => idb.tx('readonly', (st) => st.getAllKeys()),
    clear: () => idb.tx('readwrite', (st) => st.clear())
  };

  /* When the browser's storage for the state (localStorage, shared by all pages of the site) is full, the state is
     kept for this tab instead (sessionStorage has room of its own): it is there after a reload, as long as the tab
     stays open. The newer of the two is the state. */
  const SESSION_KEY = ((MG.config && MG.config.storePrefix) || 'practical') + ':files-of-this-tab';
  const session = {
    get() {
      try {
        const v = window.sessionStorage.getItem(SESSION_KEY);
        return v ? JSON.parse(v) : null;
      } catch (e) {
        return null;
      }
    },
    set(v) {
      try {
        window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(v));
        return true;
      } catch (e) {
        return false;
      }
    },
    remove() {
      try {
        window.sessionStorage.removeItem(SESSION_KEY);
      } catch (e) {
        /* no session storage */
      }
    }
  };
  const savedState = () => {
    const a = store.get('files', null), b = session.get();
    return b && Array.isArray(b.entries) && !(a && a.saved >= b.saved) ? b : a;
  };
  /** → true: written to localStorage; false: it is full (the state is then kept for this tab, if that is possible) */
  const writeState = (snap) => {
    if (store.set('files', snap)) {
      session.remove();
      return true;
    }
    session.set(snap);
    return false;
  };

  const project = {
    /** put the saved files back into the file system */
    restore(fs) {
      const saved = (this._state = savedState());
      if (!saved || !Array.isArray(saved.entries)) return false;
      for (const e of saved.entries) {
        try {
          if (fs.get(e.p) && fs.get(e.p).protected) continue; // the course data is put there by the page
          if (e.k === 'd') fs.mkdirp(e.p);
          else if (e.k === 't') fs.put(e.p, { kind: 'text', text: e.t, mtime: e.m, mode: e.x ? 'x' : undefined, readonly: e.r || undefined });
          else if (e.k === 'u') fs.put(e.p, { kind: 'url', url: new URL(e.u, location.href).href, size: e.s, mtime: e.m, readonly: e.r || undefined });
        } catch (err) {
          /* skip a bad entry */
        }
      }
      if (saved.cwd && fs.isDir(saved.cwd)) fs.cwd = saved.cwd;
      return true;
    },
    snapshot(fs) {
      const entries = [];
      const big = []; // text files that do not fit: they are named after a reload (see restoreBinary)
      let total = 0;
      let skipped = 0;
      for (const [p, e] of fs.entries) {
        if (!(p === HOME || p.startsWith(HOME + '/')) || p === HOME || e.protected) continue;
        if (e.kind === 'dir') entries.push({ k: 'd', p });
        else if (e.kind === 'text') {
          if (e.text.length > MAX_TEXT || total + e.text.length > MAX_TOTAL) {
            skipped++;
            big.push(p);
            continue;
          }
          total += e.text.length;
          entries.push({ k: 't', p, t: e.text, m: e.mtime, x: e.mode === 'x' ? 1 : 0, r: e.readonly ? 1 : 0 });
        } else if (e.kind === 'url') {
          entries.push({ k: 'u', p, u: e.url.replace(location.href.replace(/[^/]*$/, ''), ''), s: e.size, m: e.mtime, r: e.readonly ? 1 : 0 });
        } else skipped++;
      }
      // the files that programs wrote: is each one in IndexedDB as it is now, and which record holds its bytes (see restoreBinary)
      const bin = this.binaryOf(fs).map(([p, e]) => [p, this.kept.get(p) === e ? 1 : 0, e.kid || '']);
      return { entries, bin, big, cwd: fs.cwd, skipped, saved: Date.now() };
    },
    save() {
      const fs = MG.app.fs;
      if (!fs || this._paused) return;
      const snap = this.snapshot(fs);
      // a text file that does not fit is not there after a reload: say so when it happens, once for each file
      this._bigTold = this._bigTold || new Set();
      const fresh = snap.big.filter((p) => !this._bigTold.has(p));
      if (fresh.length) {
        fresh.forEach((p) => this._bigTold.add(p));
        toast(`Too large to be kept in this browser when the page is closed or loaded again: <b>${fresh.slice(0, 4).map((p) => esc(fs.pretty(p))).join(', ')}${fresh.length > 4 ? ' …' : ''}</b>. (Text files: up to 300 kB each, 3.5 MB together.) Download what you need, or remove what you do not.`, 'warn', 12000);
      }
      if (!writeState(snap)) {
        // (all pages of a site share one small storage: other practicals of the same site, done in this browser, take their part of it)
        if (!this._warned) {
          toast('<b>Your browser storage is full</b>: what you change in your files from now on is kept only as long as this tab stays open. Save it with <b>My answers → Save all my work to a file</b>. To make room, remove large text files you do not need (a SAM file, say).', 'warn', 14000);
          // (a toast goes away: the terminal keeps the message)
          if (MG.app && MG.app.term && MG.app.term.note) MG.app.term.note('Your browser storage is full: changes to your text files are kept only as long as this tab stays open – not when it is closed. Save them with My answers → Save all my work to a file; to make room, remove large text files you do not need.');
        }
        this._warned = true;
      } else this._warned = false;
    },
    watch(fs) {
      const soon = MG.debounce(() => this.save(), 800);
      // program output is written 2.5 s after the first change that is not yet kept – not after the last one:
      // a run of changes must not put the saving off for as long as it lasts
      let timer = null, due = 0;
      const later = (ms) => {
        const at = Date.now() + ms;
        if (timer && due <= at) return;
        clearTimeout(timer);
        due = at;
        timer = setTimeout(() => {
          timer = null;
          this.saveBinary(fs);
        }, ms);
      };
      fs.onChange((path, what) => {
        soon();
        // … and sooner after a file was removed or renamed: its record must not outlive it for long (a page that is
        // loaded again with a state that could not be saved must not bring a removed file back)
        later(what === 'remove' || what === 'rename' ? 300 : 2500);
      });
      window.addEventListener('beforeunload', () => this.save());
      window.addEventListener('pagehide', () => this.save()); // (where beforeunload does not come: phones and tablets)
      bus.on('editor:save', (d) => this._paused && this.saveOne(fs, d.path));
      setInterval(() => this.save(), 30000);
    },
    reset() {
      store.remove('files');
      session.remove();
      store.remove('termHistory');
      store.remove('edOpen');
      store.remove('edCurrent');
      // whatever is in IndexedDB from before this moment is no longer wanted
      store.set('filesFrom', Date.now());
      this.kept = new Map();
      this.known = new Set();
      this._stale = [];
      this._stopped = true; // a save that is under way writes nothing more
      idb.clear().catch(() => {});
    },

    /* ---- what programs wrote: kept in IndexedDB ---- */
    kept: new Map(), // path -> the entry whose bytes are in IndexedDB (a file that changes gets a new entry)
    known: new Set(), // the paths whose record in IndexedDB is this page's: it wrote the record, or took a file from it.
    //                   It removes no others: the page may be open in a second tab of the browser, with other files.
    _stale: [], // records that no file of this page needs: removed a little later, if no other tab has the page open (dropStale)
    missing: [], // after the page was loaded: files of the saved state that are not in IndexedDB (see restoreBinary)
    _run: 0, // counts the saves that were given up (see _giveUp)
    binaryOf(fs) {
      const out = [];
      for (const [p, e] of fs.entries) if (p.startsWith(HOME + '/') && !e.protected && (e.kind === 'aioli' || e.kind === 'blob')) out.push([p, e]);
      return out;
    },
    /* While a command of the AI agent runs, the state of the files is not written to the browser's
       storage: what the command changes outside the agent's folder is put back first (assistant.js),
       and only then is the state kept. (A page that is reloaded in the middle of such a command comes
       back with the files as they were before it.) */
    pause() {
      this.save(); // what changed in the last moment (a file saved in the editor, a new file) is written first
      this._paused = true;
    },
    resume(fs) {
      this._paused = false;
      this.save();
      if (this._pending) {
        this._pending = false;
        this.saveBinary(fs);
      }
    },
    /** write to IndexedDB now whatever is not yet kept there, and wait until it is done */
    async flush(fs) {
      if (this._stopped) return;
      for (let i = 0; i < 600 && (this._saving || this._hold); i++) await new Promise((r) => setTimeout(r, 30));
      if (this._saving) this._giveUp(); // a save that has not ended after 18 s never will
      await this.saveBinary(fs);
    },
    /** the save that is under way writes nothing more (the programs it reads from were stopped, or it hangs); a new one may start */
    _giveUp() {
      this._run++;
      this._saving = false;
      this._again = false;
    },
    /** The programs were stopped by force: the files in `lost` lived in their memory. Each comes back from IndexedDB:
        with its own bytes if a record holds them – also when the file was renamed, copied or touched after it was
        stored – or else as the version that is stored under its name (an earlier one). Nothing else comes back, and
        nothing is written to IndexedDB until this is done. → how many came back */
    async afterKill(fs, lost) {
      this._hold = true;
      const was = (MG.wasm && MG.wasm.lostEntries) || new Map(); // path -> the entry that was lost
      let n = 0;
      try {
        let recs;
        try {
          recs = usable(await idb.all());
        } catch (err) {
          return 0;
        }
        const byPath = new Map(recs.map((r) => [r.path, r]));
        const byId = new Map(recs.filter((r) => r.id).map((r) => [r.id, r]));
        for (const p of lost) {
          this.kept.delete(p);
          if (fs.exists(p) || !fs.isDir(MG.path.dirname(p))) continue;
          const e = was.get(p);
          const exact = e && e.kid ? byId.get(e.kid) : null;
          const r = exact || byPath.get(p);
          if (!r) continue;
          fs.put(p, exact ? blobEntry(r, e) : blobEntry(r));
          this.known.add(r.path);
          // (a record under another name, or with other permissions, is written again by the next save)
          if (r.path === p && (!exact || sameFlags(r, e))) this.kept.set(p, fs.entries.get(p));
          n++;
        }
        return n;
      } finally {
        this._hold = false;
        if (this._pending && !this._paused) {
          this._pending = false;
          this.saveBinary(fs);
        }
      }
    },
    async saveBinary(fs) {
      if (this._stopped) return;
      if (this._paused || this._hold) {
        this._pending = true;
        return;
      }
      if (this._saving) {
        this._again = true;
        return;
      }
      this._saving = true;
      const run = this._run;
      const live = () => run === this._run && !this._stopped; // false: this save was given up
      let wrote = false;
      const drop = async (p) => {
        await idb.del(p);
        this.known.delete(p);
        this.kept.delete(p);
        wrote = true;
      };
      try {
        const now = this.binaryOf(fs);
        const paths = new Set(now.map(([p]) => p));
        for (const [p, e] of now) {
          if (this.kept.get(p) === e) continue;
          if (fs.size(e) > MAX_BINARY) {
            // too large to keep: say so when it is made, once – and an older, smaller version must not come back in its place
            this._largeTold = this._largeTold || new Set();
            if (!this._largeTold.has(p)) {
              this._largeTold.add(p);
              toast(`<b>${esc(fs.pretty(p))}</b> is larger than 40 MB: it is here as long as this page stays open, and is not kept when the page is closed or loaded again. Download it if you need it – or make it again with your script.`, 'warn', 12000);
            }
            if (this.known.has(p)) await drop(p);
            if (!live()) return;
            continue;
          }
          let blob;
          try {
            blob = e.kind === 'blob' ? e.blob : new Blob([await fs.readBytes(p)]);
          } catch (err) {
            continue; // not readable just now (the programs were restarted): try again at the next change
          }
          if (!live()) return;
          if (fs.entries.get(p) !== e) continue; // it changed while it was read
          if (this._paused) {
            this._pending = true;
            break;
          }
          const id = newId();
          await idb.put({ path: p, blob, mtime: e.mtime || Date.now(), mode: e.mode || '', readonly: !!e.readonly, saved: Date.now(), id });
          this.known.add(p);
          if (!live()) return;
          e.kid = id;
          this.kept.set(p, e);
          wrote = true;
        }
        // the record of a path that is no longer program output goes – after the writing: the bytes of a file that
        // was renamed are kept under its old name until they are kept under the new one
        for (const p of Array.from(this.known)) {
          if (paths.has(p)) continue;
          if (this._paused) {
            this._pending = true;
            break;
          }
          await drop(p);
          if (!live()) return;
        }
      } catch (err) {
        if (!this._idbWarned) console.warn('Program output could not be kept in this browser (IndexedDB): ' + (err && err.message));
        this._idbWarned = true;
      } finally {
        if (run === this._run) {
          this._saving = false;
          // which files are kept is part of the saved state
          if (wrote) this.save();
          if (this._again) {
            this._again = false;
            this.saveBinary(fs);
          }
        }
      }
    },
    /** Put the kept program output back.
        opts.manifest (when the page is loaded): the saved state names the files that programs had written, says which
          of them were in IndexedDB as they were, and which record holds the bytes of each. Those come back – a file
          that was renamed or copied just before the page was closed, too. A file whose bytes had not reached
          IndexedDB – written in the last seconds, or larger than 40 MB – does not come back as an older version: it
          is named in this.missing. A record that the saved state does not name comes back if it was written after
          that state (the state could not be saved any more: the browser's storage for it was full). Any other record
          that no file needs (the file was removed) is deleted – a little later, and only if the page is not open in
          another tab, whose files they may be (dropStale).
        opts.only (after a command of the AI agent was stopped by force): a set of paths – those and no others come
          back, as they are stored (the state before the command); opts.under: … and whatever is kept of this folder,
          with the folders in it that the command had removed. */
    async restoreBinary(fs, opts = {}) {
      const state = opts.manifest ? this._state || savedState() || {} : {};
      const manifest = Array.isArray(state.bin) ? state.bin : null;
      // … and the text files that were too large for the saved state
      const absent = () => (manifest ? manifest.map((x) => x[0]) : []).concat(Array.isArray(state.big) ? state.big : []).filter((p) => !fs.exists(p));
      let all;
      try {
        all = await idb.all();
      } catch (err) {
        this.missing = absent();
        return 0;
      }
      const recs = usable(all);
      let n = 0;
      const drop = (p) => {
        this.known.delete(p);
        idb.del(p).catch(() => {});
      };
      (all || []).forEach((r) => r && r.path && !recs.includes(r) && drop(r.path));
      const isBinary = (e) => !!e && (e.kind === 'blob' || e.kind === 'aioli');
      if (manifest) {
        const byPath = new Map(recs.map((r) => [r.path, r]));
        const byId = new Map(recs.filter((r) => r.id).map((r) => [r.id, r]));
        const used = new Set();
        for (const [p, isKept, kid] of manifest) {
          if (fs.exists(p) || !fs.isDir(MG.path.dirname(p))) continue;
          const r = isKept === 1 ? byPath.get(p) : kid ? byId.get(kid) : null;
          if (!r) continue;
          fs.put(p, blobEntry(r));
          if (r.path === p) this.kept.set(p, fs.entries.get(p));
          used.add(r.path);
          this.known.add(r.path);
          n++;
        }
        for (const r of recs) {
          if (used.has(r.path)) continue;
          const there = fs.get(r.path);
          if (isBinary(there)) continue; // (the file came from another record: this one is written over by the next save)
          if (!there && state.saved && r.saved > state.saved && fs.isDir(MG.path.dirname(r.path))) {
            // written after the state was last saved: the file comes back
            fs.put(r.path, blobEntry(r));
            this.kept.set(r.path, fs.entries.get(r.path));
            this.known.add(r.path);
            n++;
          } else this._stale.push(r);
        }
        this.missing = absent();
        return n;
      }
      for (const r of recs) {
        const there = fs.get(r.path);
        const below = !!opts.under && r.path.startsWith(opts.under + '/');
        const wanted = !opts.only || opts.only.has(r.path) || below;
        // (in the agent's folder a file comes back with its folder, if the command that was stopped had removed that)
        if (wanted && !there && below && !fs.isDir(MG.path.dirname(r.path))) {
          try {
            fs.mkdirp(MG.path.dirname(r.path));
          } catch (e) {
            /* a file is where the folder was: the file stays away */
          }
        }
        if (there || !wanted || !fs.isDir(MG.path.dirname(r.path))) {
          // its folder is gone, the file is now an ordinary (text) file, or it had been removed: the kept copy is out of date
          // (when the page is loaded without a saved state – not after a command of the AI agent, where the records are the state before it)
          if (!opts.only && !isBinary(there)) this._stale.push(r);
          continue;
        }
        fs.put(r.path, blobEntry(r));
        this.kept.set(r.path, fs.entries.get(r.path));
        this.known.add(r.path);
        n++;
      }
      return n;
    },
    /** The records that no file of this page needed when it was loaded (_stale) are deleted – if this is the only tab
        that has the page open: in another tab they may be that tab's files. A record that was written since, or whose
        file is there now, stays. alone: a function → true/false (or a promise of it). → how many were deleted */
    async dropStale(fs, alone) {
      const list = this._stale;
      this._stale = [];
      if (!list.length || this._stopped) return 0;
      let ok = true;
      try {
        ok = !alone || (await alone());
      } catch (e) {
        ok = false;
      }
      if (!ok) return 0;
      let n = 0;
      for (const r of list) {
        const there = fs.get(r.path);
        if (there && (there.kind === 'blob' || there.kind === 'aioli')) continue;
        try {
          await idb.delIf(r.path, r.id);
          this.known.delete(r.path);
          n++;
        } catch (e) {
          /* no storage */
        }
      }
      return n;
    },
    /** While saving is paused (a command of the AI agent is under way), a file that the student saves in the
        editor is still written to the browser's storage – that one file, into the state kept before the command. */
    saveOne(fs, path) {
      const e = fs.entries.get(path);
      const snap = savedState();
      if (!e || e.kind !== 'text' || !snap || !Array.isArray(snap.entries) || !path.startsWith(HOME + '/') || e.text.length > MAX_TEXT) return;
      const rec = { k: 't', p: path, t: e.text, m: e.mtime, x: e.mode === 'x' ? 1 : 0, r: e.readonly ? 1 : 0 };
      const i = snap.entries.findIndex((x) => x.p === path);
      if (i >= 0) snap.entries[i] = rec;
      else {
        for (let d = MG.path.dirname(path); d.startsWith(HOME + '/'); d = MG.path.dirname(d)) if (!snap.entries.some((x) => x.p === d)) snap.entries.push({ k: 'd', p: d });
        snap.entries.push(rec);
      }
      writeState(snap);
    },

    /** a .zip of a folder (default: the project) */
    async zip(root, opts = {}) {
      const fs = MG.app.fs;
      if (!window.JSZip) await loadScript('assets/vendor/jszip/jszip.min.js');
      const zip = new window.JSZip();
      const top = root.split('/').pop();
      const skip = opts.skip || /(^|\/)(__pycache__)(\/|$)/;
      let n = 0;
      for (const [p, e] of fs.entries) {
        if (!p.startsWith(root + '/')) continue;
        const rel = p.slice(root.length + 1);
        if (skip.test(rel) || (opts.only && !opts.only.test(rel))) continue;
        if (e.kind === 'dir') {
          zip.folder(top + '/' + rel);
          continue;
        }
        if (e.kind === 'virtual') continue;
        const bytes = await fs.readBytes(p);
        zip.file(top + '/' + rel, bytes, { date: new Date(e.mtime || Date.now()), unixPermissions: 0o100000 | (e.mode === 'x' ? (e.readonly ? 0o555 : 0o755) : e.readonly ? 0o444 : 0o644) });
        n++;
      }
      for (const [name, text] of Object.entries(opts.extra || {})) zip.file(top + '/' + name, text);
      const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 }, platform: 'UNIX' });
      return { blob, n };
    },
    async download(root, filename, opts) {
      const fs = MG.app.fs;
      if (!fs.isDir(root)) {
        toast(`There is no folder ${esc(fs.pretty(root))} yet.`, 'warn');
        return null;
      }
      const { blob, n } = await this.zip(root, opts);
      MG.downloadBlob(blob, filename);
      toast(`Saved <b>${esc(filename)}</b> (${n} files, ${MG.humanSize(blob.size)}B).`);
      bus.emit('project:download', { root, filename, files: n, size: blob.size });
      return blob;
    }
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Could not load ' + src));
      document.head.appendChild(s);
    });
  }
  // a read from programs that were stopped by force never ends: do not wait for it
  bus.on('wasm:killed', () => project._giveUp());
  MG.loadScript = loadScript;
  MG.project = project;
})();
