/* =====================================================================
   The AI of this practical. It is always a real model, called from the
   browser with a key the student enters (kept in this browser tab only).

   Chat   an assistant that answers questions. The student reads the
          answer and runs the commands.
   Agent  a model that carries out a task itself. It replies with
          commands; the page runs them in the student's terminal and
          sends back what they printed, until the model reports.
          Four ways of working:
            ask     approve each step before it runs
            plan    the agent writes a plan first; then it works alone
            auto    the agent works alone
            script  the agent writes one script, and gets it to run

   Each agent run has a folder of its own, ~/runs/N-mode, that starts
   with a copy of the data. The page – not the model – writes the record
   of the run there: RUN.md (to read) and run.json (the same, as data).
   ===================================================================== */
(function () {
  'use strict';
  const MG = window.MG;
  const { h, esc, bus, toast, store } = MG;
  const CFG = MG.config || {};
  const KEY_NAME = 'agents-ai-key';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const HOME = () => (MG.app && MG.app.HOME) || '/home/student';

  /* ------------------------------------------------------------------
     a small markdown renderer: paragraphs, lists, headings, tables,
     code blocks, inline code, bold, italics, links. Text is escaped.
     ------------------------------------------------------------------ */
  function inline(s) {
    const codes = [];
    let t = esc(s).replace(/`([^`]+)`/g, (m, c) => {
      codes.push(c);
      return '\u0000' + (codes.length - 1) + '\u0000';
    });
    t = t.replace(/\\\*/g, '\u0001');
    t = t.replace(/(^|[^\w*])\*\*((?:[^*]|\*(?!\*))+?)\*\*(?![\w*])/g, '$1<b>$2</b>');
    t = t.replace(/(^|[^*\w])\*([^*\s](?:[^*]*[^*\s])?)\*(?![\w*])/g, '$1<i>$2</i>');
    t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    t = t.replace(/\u0001/g, '*');
    return t.replace(/\u0000(\d+)\u0000/g, (m, k) => '<code>' + codes[+k] + '</code>');
  }
  function renderMarkdown(md) {
    const out = [];
    const lines = String(md || '').replace(/\r/g, '').split('\n');
    let i = 0, list = null, para = [];
    const closeList = () => {
      if (list) out.push({ html: `<${list.type}>${list.items.map((x) => `<li>${inline(x)}</li>`).join('')}</${list.type}>` });
      list = null;
    };
    const closePara = () => {
      if (para.length) out.push({ html: `<p>${inline(para.join(' '))}</p>` });
      para = [];
    };
    while (i < lines.length) {
      const L = lines[i];
      const fence = /^\s*```\s*([^\s`]*)\s*(.*)$/.exec(L);
      if (fence) {
        closePara();
        closeList();
        const code = [];
        i++;
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) code.push(lines[i++]);
        i++;
        const info = fence[1].toLowerCase();
        const file = /^file[:=](.+)$/.exec(fence[1]);
        out.push({ code: code.join('\n'), lang: file ? 'file' : info || 'text', file: file ? file[1] : fence[2].trim().split(/\s+/)[0] || null });
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(L) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        closePara();
        closeList();
        const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
        const head = cells(L);
        i += 2;
        const body = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) body.push(cells(lines[i++]));
        out.push({ html: `<div class="ai-tablewrap"><table class="ai-table"><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr>${body.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</table></div>` });
        continue;
      }
      const hd = /^(#{1,4})\s+(.*)$/.exec(L);
      const ul = /^\s*[-*•]\s+(.*)$/.exec(L);
      const ol = /^\s*\d+[.)]\s+(.*)$/.exec(L);
      if (hd) {
        closePara();
        closeList();
        out.push({ html: `<h5>${inline(hd[2])}</h5>` });
      } else if (/^\s*([-*_])\1{2,}\s*$/.test(L)) {
        closePara();
        closeList();
        out.push({ html: '<hr>' });
      } else if (ul || ol) {
        closePara();
        const type = ul ? 'ul' : 'ol';
        if (!list || list.type !== type) {
          closeList();
          list = { type, items: [] };
        }
        list.items.push((ul || ol)[1]);
      } else if (!L.trim()) {
        closePara();
        closeList();
      } else if (list && /^\s{2,}\S/.test(L)) {
        list.items[list.items.length - 1] += ' ' + L.trim();
      } else {
        closeList();
        para.push(L.trim());
      }
      i++;
    }
    closePara();
    closeList();
    return out;
  }

  /* ------------------------------------------------------------------
     the services
     ------------------------------------------------------------------ */
  const DEFAULTS = {
    provider: CFG.liveProvider || 'gemini',
    model: CFG.anthropicModel || 'claude-sonnet-5-5',
    geminiModel: CFG.geminiModel || 'gemini-3.8-flash',
    baseURL: 'https://api.openai.com/v1',
    openaiModel: ''
  };
  /* An empty model in the saved settings means "the site's model" (config.js): a model changed
     there, when one is retired, reaches every student who has not chosen one of their own. */
  const geminiModelOf = (s) => (s.geminiModel || DEFAULTS.geminiModel).trim().replace(/^models\//, '');
  const anthropicModelOf = (s) => (s.model || DEFAULTS.model).trim();
  const modelOf = (s) => (s.provider === 'gemini' ? geminiModelOf(s) : s.provider === 'anthropic' ? anthropicModelOf(s) : s.openaiModel || 'model');
  const serviceOf = (s) => (s.provider === 'gemini' ? 'Google Gemini API' : s.provider === 'anthropic' ? 'Anthropic API' : 'OpenAI-compatible service at ' + (s.baseURL || '').replace(/^https?:\/\//, '').replace(/\/.*$/, ''));
  /** Gemini and Anthropic always need a key; an OpenAI-compatible server (a local one, say) may not */
  const needsKey = (s) => s.provider !== 'openai';
  /* A Gemini model can be busy (HTTP 503 "high demand"), give no answer at all, or be over one
     of its limits (429) – on the free tier each model has limits of its own, per minute and per
     day. Then the next model of this list is asked; the answer says which one replied.
     The page remembers what a model said, and does not ask it again before that can have
     changed: a busy model after two minutes (then four, eight … if it is busy again), a silent
     one after one minute, a model over a limit when the service says the limit is over (a limit
     per day: not before tomorrow), a model that was not found not at all. That saves time –
     "busy" can take twenty seconds to arrive – and requests, of which the free tier allows few:
     on 6 October 2026, 20 a day for each of the four larger models, and a request that was
     answered "busy" counted as one of them. The memory belongs to one key – another key is
     another project, with limits of its own – and lasts until the page is loaded again. */
  const FALLBACK_DEFAULT = ['gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'];
  const FALLBACKS = (Array.isArray(CFG.geminiFallbackModels) ? CFG.geminiFallbackModels : FALLBACK_DEFAULT).map((m) => String(m).trim().replace(/^models\//, '')).filter(Boolean);
  const BUSY = [500, 502, 503, 504, 529];
  const BUSY_REST = 120, SILENT_REST = 60; // seconds
  const RETRY = 20; // seconds after which it is worth asking busy or silent models again
  /* how long a Gemini model may say nothing – before its answer begins, or in the middle of it – until the request is given up */
  const WAIT = () => (+CFG.aiWaitSeconds > 0 ? Math.max(1, +CFG.aiWaitSeconds) : 60);
  const REST = new Map(); // model → { model, why: 'busy' | 'noanswer' | 'limit' | 'notfound', at, until (ms), daily, limit, n, status, text }
  let restKey = null;
  const resting = (model) => {
    const r = REST.get(model);
    return r && r.until > Date.now() ? r : null;
  };
  const hhmm = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  /** what kept a model from answering: in a word or two (under an answer, in the bar) … */
  const skipWord = (x) => (x.why === 'notfound' ? 'not found' : x.why === 'limit' ? (x.daily ? 'over its limit for today' : 'over its limit') : x.why === 'noanswer' ? 'gave no answer' : x.why === 'broke' ? 'broke off' : 'busy');
  /** … and as part of a sentence – with the numbers that the service gave, unless short */
  const told = (x, short) =>
    x.why === 'notfound'
      ? 'was not found'
      : x.why === 'limit'
        ? x.daily
          ? 'is over its limit for today' + (short ? '' : (x.limit != null ? `: ${x.limit} requests a day` : '') + (isFinite(x.until) ? `, again after ${hhmm(x.until)}` : ''))
          : 'is over its limit per minute'
        : x.why === 'noanswer'
          ? 'gave no answer'
          : 'is busy';
  /** the error when no Gemini model answered: what each one said. .status: 429 (limits), 503 (busy), 404, or not set
      (no answer came); .retryIn: after how many seconds asking again can help – 0 when it cannot today */
  function noAnswer(all, connection) {
    const some = (f) => all.some(f);
    const waits = all.filter((x) => x.why === 'limit' && !x.daily).map((x) => Math.min(90, Math.max(1, Math.ceil((x.until - Date.now()) / 1000))));
    if (some((x) => x.why === 'busy' || x.why === 'noanswer')) waits.push(RETRY);
    const retryIn = waits.length ? Math.min(...waits) : 0;
    // one model only (no fallback models): its own words
    if (all.length === 1) return Object.assign(new Error(all[0].text), { status: all[0].status, network: all[0].why === 'noanswer', retryIn });
    let status, lead;
    // (a model that answered within the last two minutes, if only with "busy" or "over its limit": the service can be reached)
    const heard = some((x) => x.status && Date.now() - x.at < 120000);
    if (connection || (some((x) => x.why === 'noanswer') && !some((x) => x.why === 'busy'))) lead = heard ? 'No answer came from the Gemini API, though it can be reached: try again in a moment.' : 'Could not reach the Gemini API: no answer came. Check the internet connection, and try again.';
    else if (some((x) => x.why === 'busy')) (status = 503), (lead = 'HTTP 503. Google’s servers are busy (“high demand”). That is on Google’s side, not a problem with your key: wait a minute and try again.');
    else if (waits.length) (status = 429), (lead = 'HTTP 429. Too many requests: the free tier allows only a few requests per minute – wait a minute and try again.');
    else if (some((x) => x.why === 'limit')) (status = 429), (lead = 'HTTP 429. No requests are left for today: every model that this page asks is over its limit for this key. The free tier allows each model a number of requests per day, counted per project. Go on when the service takes requests again, or use a key from another person or project.');
    else (status = 404), (lead = 'HTTP 404. None of the models was found – check the model in the AI settings (⚙).');
    return Object.assign(new Error(`${lead} (${all.map((x) => x.model + ' ' + told(x)).join('; ')}.)`), { status, network: !status, retryIn });
  }
  /** a pause that the Stop button can cut short */
  const pause = (ms, signal) =>
    new Promise((resolve, reject) => {
      const t = setTimeout(resolve, ms);
      const stop = () => {
        clearTimeout(t);
        reject(new DOMException('Stopped', 'AbortError'));
      };
      if (signal && signal.aborted) stop();
      else if (signal) signal.addEventListener('abort', stop, { once: true });
    });
  const stopped = () => new DOMException('Stopped', 'AbortError');

  /* ------------------------------------------------------------------
     what every model is told about this place
     ------------------------------------------------------------------ */
  const V = () => (MG.wasm && MG.wasm.versions) || {};
  function environment(dataDir) {
    const v = V();
    return [
      `Files: ${dataDir}/NA12878_R1.fastq and ${dataDir}/NA12878_R2.fastq – paired-end Illumina reads (76 bases, 3,519 pairs) from exome sequencing of the human reference sample NA12878; only the reads from around two neighbouring genes, CYP2C19 and CYP2C9. ${dataDir}/reference.fa – two pieces of human chromosome 10 (genome build hg19), named human_CYP2C19 (30,000 bases) and human_CYP2C9 (26,000 bases); positions are counted within each piece. The files in ${dataDir}/ are read-only.`,
      `Programs: fastp ${v.fastp} (quality control and trimming; writes an HTML and a JSON report), minimap2 ${v.minimap2} and bowtie2 ${v.bowtie2} with bowtie2-build (read mapping), samtools ${v.samtools}, bcftools ${v.bcftools}, bgzip and tabix (htslib ${v.htslib}), seqtk ${v.seqtk}, bedtools ${v.bedtools}, jq ${v.jq}; GNU coreutils ${v.coreutils} (cat head tail wc sort uniq cut tr tee paste join comm seq fold shuf md5sum date), grep ${v.grep} (also egrep, fgrep), sed ${v.sed}, awk (gawk ${v.gawk}), diff and cmp (GNU diffutils ${v.diffutils}), gzip gunzip zcat zgrep. Written for this terminal, after the programs of the same names: ls cd pwd mkdir rmdir cp mv rm touch tree find xargs du stat file chmod basename dirname realpath readlink mktemp env printenv timeout sleep getopt, sha256sum sha1sum sha384sum sha512sum, split truncate tac rev nl column expand unexpand, od hexdump xxd base64, expr and bc (the calculator, with -l) – these print what the originals print but do not have every option: NAME --help lists the options of each. The shell's own commands (echo printf test read …) are as in bash.`,
      'Not installed, and nothing can be installed: bwa, GATK, FreeBayes, Picard, FastQC, MultiQC, Trimmomatic, cutadapt, Python, R, perl, tar, zip, conda, git, wget, curl. There is no network. bcftools has no plugins (+fill-tags …); bowtie2 has no --un/--al options.',
      'The shell is bash-like: pipes, && || ;, redirection (> >> < 2> 2>&1), variables and arrays, $( ), $(( )), if / for / while / case, [ ] and [[ ]], functions, getopts, here-documents, process substitution <( ), scripts (bash script.sh, set -euo pipefail, trap). Not available: background jobs (&), sudo. The commands of a pipeline run one after the other, so a command that never ends (yes, cat /dev/urandom) must not feed a pipe.',
      'Everything runs inside a web browser, on one thread: thread options (-t, -@, --threads, -p) are of no use. The data is small; each program takes a few seconds at most.'
    ];
  }

  /* ---- the agent ---- */
  const MODES = {
    ask: { label: 'Approve each step', word: 'approve', does: 'The agent proposes one step at a time. Nothing runs until you allow it – you can change a command first, or refuse it.' },
    plan: { label: 'Plan first', word: 'plan', does: 'The agent writes a plan and waits. You approve it, or ask for changes; then it carries the plan out on its own.' },
    auto: { label: 'Autonomous', word: 'auto', does: 'The agent runs commands on its own until it reports that the task is done. You watch – and can stop it.' },
    script: { label: 'Write a script', word: 'script', does: 'The agent writes one script, analysis.sh, runs it and repairs it until it works. What you get is the script.' }
  };
  const MAX_STEPS = Math.max(4, CFG.agentMaxSteps || 20);
  const OUT_CHARS = Math.max(500, CFG.agentOutputChars || 3000);
  // a command of the agent that has not ended after this long is stopped (config: agentCommandSeconds)
  const commandTimeout = () => Math.max(5, +CFG.agentCommandSeconds || 150) * 1000;
  const INPUTS = () => (MG.app && MG.app.INPUTS) || ['NA12878_R1.fastq', 'NA12878_R2.fastq', 'reference.fa'];
  /* what a command printed, as the model gets it: long output keeps its beginning and its end */
  const shown = (out) => {
    if (out.length <= OUT_CHARS) return out;
    const head = Math.round(OUT_CHARS / 3), tail = OUT_CHARS - head;
    return `${out.slice(0, head)}\n[… ${out.length - OUT_CHARS} of ${out.length} characters left out here …]\n${out.slice(-tail)}`;
  };
  /* commands of the page itself, which make no sense for an agent */
  const NOT_FOR_AGENTS = {
    sudo: 'sudo is not available (and not needed).',
    clear: 'clear, history and download are commands for the person at the terminal.',
    history: 'clear, history and download are commands for the person at the terminal.',
    download: 'clear, history and download are commands for the person at the terminal.',
    less: 'less and more need a person at the terminal: use head, tail or grep.',
    more: 'less and more need a person at the terminal: use head, tail or grep.'
  };
  ['nano', 'vi', 'vim', 'emacs', 'edit', 'code', 'gedit', 'pico', 'open', 'xdg-open'].forEach((k) => (NOT_FOR_AGENTS[k] = `${k} opens a window for a person. To write a file use a \`\`\`file:NAME block; to look at one use cat, head or grep.`));
  /** why the agent may not run this text ('' if it may) */
  function refusal(text) {
    let names;
    try {
      names = MG.shellLang.commandNames(text);
    } catch (e) {
      return '';
    }
    for (const n of names) if (NOT_FOR_AGENTS[n]) return NOT_FOR_AGENTS[n];
    return '';
  }
  /** what a reply of the agent asks for: { say, file: {name, text}, bash, final, open } */
  function parseReply(text) {
    text = String(text).replace(/\r\n/g, '\n');
    // A reply that marks its code with tildes (~~~bash) and has no ``` at all: read the tildes as fences.
    if (!/```/.test(text)) text = text.replace(/^([ \t]*)~~~/gm, '$1```');
    // A file may itself hold code fences – a README that shows commands. They are part of the file: they must
    // neither end the block nor be run. So, before the blocks are taken, the end of each ```file: block is found:
    //   - a block that is opened with four backticks, or with tildes, ends with the same;
    //   - inside the block a fence with a name (```bash) opens a block of the file, which the next bare fence closes;
    //   - in a Markdown file (README, *.md) a bare fence may open such a block, too: the file then ends at the last
    //     fence after which the rest of the reply still pairs up.
    // The fences inside the file are marked, and put back when the file's text is taken.
    const FENCE = '\u0001';
    let cut = false;
    if (/(```|~~~)[ \t]*(?:\S+[ \t]+)?file[ \t]*[:=]/i.test(text)) {
      const L = text.split('\n'), inFile = [];
      let tildes = false;
      for (let i = 0; i < L.length; i++) {
        const o = /^[ \t]*(`{3,}|~{3,})[ \t]*(?:\S+[ \t]+)?file[ \t]*[:=](.*)$/i.exec(L[i]);
        if (!o) continue;
        const ch = o[1][0], n = o[1].length;
        const fenceAt = (k) => {
          const f = (ch === '`' ? /^[ \t]*(`{3,})[ \t]*([^`]*)$/ : /^[ \t]*(~{3,})[ \t]*(.*)$/).exec(L[k]);
          return f && f[1].length >= n ? { line: k, bare: f[2].trim() === '' } : null;
        };
        const F = [];
        for (let k = i + 1; k < L.length; k++) {
          const f = fenceAt(k);
          if (f) F.push(f);
        }
        // pairs of an opening fence (bare or with a name) and a bare closing one
        const paired = (list) => list.length % 2 === 0 && list.every((f, k) => k % 2 === 0 || f.bare);
        let end = -1;
        if (/\.(md|markdown|mdown|mkd|rst)\b/i.test(o[2]) || /(^|[\s/])README\b/i.test(o[2])) {
          for (let c = F.length - 1; c >= 0 && end < 0; c--) if (F[c].bare && paired(F.slice(0, c)) && paired(F.slice(c + 1))) end = F[c].line;
        }
        if (end < 0) {
          let depth = 1;
          for (const f of F) {
            if (!f.bare) depth++;
            else if (--depth === 0) {
              end = f.line;
              break;
            }
          }
        }
        if (end < 0) {
          // The block never ends: the reply was cut off, or a closing fence is missing. No file is written from a
          // part of it, and nothing that stands in it is run: from here on the reply has no blocks.
          for (let k = i; k < L.length; k++) L[k] = L[k].replace(/`{3,}|~{3,}/g, (f) => FENCE.repeat(f.length));
          cut = true;
          break;
        }
        for (let k = i + 1; k < end; k++) if (/^[ \t]*`{3,}/.test(L[k])) L[k] = L[k].replace(/`/g, FENCE);
        if (ch === '~' || n > 3) {
          L[i] = L[i].replace(/`{3,}|~{3,}/, '```');
          L[end] = L[end].replace(/`{3,}|~{3,}/, '```');
        }
        if (ch === '~') tildes = true;
        inFile.push([i, end]);
        i = end;
      }
      // a reply that fences its file with tildes fences its commands with tildes too (~~~bash): outside the files
      // they are read as fences – also when a file's own text holds backticks
      if (tildes && !cut) for (let k = 0; k < L.length; k++) if (!inFile.some(([x, y]) => k >= x && k <= y)) L[k] = L[k].replace(/^([ \t]*)~{3,}/, '$1```');
      text = L.join('\n');
    }
    const blocks = [];
    const re = /```([^\n`]*)\n([\s\S]*?)\n?```/g;
    let m;
    while ((m = re.exec(text))) {
      let body = m[2];
      // a block inside a list item is indented: its lines lose that indentation (a here-document's end must be at the start of its line)
      const ind = text.slice(text.lastIndexOf('\n', m.index - 1) + 1, m.index);
      if (ind && /^[ \t]+$/.test(ind)) body = body.split('\n').map((l) => (l.startsWith(ind) ? l.slice(ind.length) : l.replace(/^[ \t]+/, (w) => (w.length <= ind.length ? '' : w)))).join('\n');
      blocks.push({ info: m[1].trim(), body: body.split(FENCE).join('`') });
    }
    const rest = text.replace(re, '');
    const open = cut || /```/.test(rest); // a block that never closes: the reply was cut off
    let file = null, bash = null, more = 0, unlabelled = 0, moreFiles = 0;
    const other = []; // blocks in another language (python, r …), which are not run
    for (const b of blocks) {
      const f = /^file\s*[:=]\s*(.+)$/i.exec(b.info) || /^\S+\s+(?:file\s*[:=]\s*)(.+)$/i.exec(b.info);
      if (f) {
        // the name is the rest of the line ("my notes.txt" is one name, and not a plain one); a language after it is dropped
        const lang = /^(\S+)\s+\(?(?:bash|sh|shell|text|txt|json|yaml|yml|md|markdown|python|py|r|awk|tsv|csv)\)?$/i.exec(f[1].trim());
        if (!file) file = { name: (lang ? lang[1] : f[1].trim()).replace(/^\.\//, ''), text: b.body.replace(/\s+$/, '') + '\n' };
        else moreFiles++; // (one file per reply: the model is told – see the agent's loop)
        continue;
      }
      if (/^(bash|sh|shell|zsh|console)$/i.test(b.info.split(/\s+/)[0])) {
        if (bash == null) bash = b.body.split('\n').map((l) => l.replace(/^\s*\$\s+/, '')).join('\n').trim();
        else more++;
      } else if (!b.info) unlabelled++;
      else if (/^(python|python3|py|r|perl|ruby|awk|sql|javascript|js)$/i.test(b.info.split(/\s+/)[0])) other.push(b.info.split(/\s+/)[0].toLowerCase());
    }
    // the report: a line that starts with REPORT (also "## REPORT", "**Final report**:") with no code block before it
    const at = REPORT_LINE.exec(text);
    const final = !!at && !/```/.test(text.slice(0, at.index));
    let say = rest.replace(/```[\s\S]*$/, '').replace(new RegExp(FENCE + '{3,}[\\s\\S]*$'), '').replace(/\n{3,}/g, '\n\n').trim().split(FENCE).join('`');
    // A report in the same reply as a step: the word REPORT, alone on its line, after the step's block – written
    // before the step has run, so with results that the model expects, not ones it has seen. It is not the report
    // (see final), and it is kept apart from what the agent said about the step.
    let early = '';
    if (!final && (file || bash != null)) {
      const e = /^[ \t]*(?:[#*_>]+[ \t]*)*(?:FINAL[ \t]+)?REPORT[ \t]*[:*_]*[ \t]*$/m.exec(say);
      if (e) {
        early = cleanReport(say.slice(e.index));
        say = say.slice(0, e.index).trim();
      }
    }
    return { say, file, bash, final, open, more, unlabelled, other, moreFiles, early };
  }
  // REPORT in capitals at the start of a line; or "Report" / "Final report" alone on a line.
  // (Not the name of a file: "REPORT.md is not there yet", "REPORT-1.txt", "REPORT/" begin a sentence about a file.)
  const REPORT_LINE = /^[ \t]*(?:[#*_>]+[ \t]*)*(?:(?:FINAL[ \t]+)?REPORT(?!\w|\/|[.\-]\w)|(?:[Ff]inal[ \t]+)?[Rr]eport[ \t]*[:*_]*[ \t]*$)/m;
  /** the report without the word REPORT, and without what the model said before it */
  const cleanReport = (text) => {
    const at = REPORT_LINE.exec(text);
    let t = (at ? text.slice(at.index + at[0].length).replace(/^[:*_ \t-]*/, '') : text).trim();
    // a model that says the word twice (REPORT, an empty line, REPORT – seen with a real model): the second one, alone on its line, goes too
    for (let k = 0; k < 2; k++) {
      const again = /^[ \t]*(?:[#*_>]+[ \t]*)*(?:(?:FINAL|[Ff]inal)[ \t]+)?(?:REPORT|Report)[ \t]*[:*_]*[ \t]*(?:\n|$)/.exec(t);
      if (!again) break;
      t = t.slice(again[0].length).trim();
    }
    return t;
  };
  const inside = (k, root) => k === root || k.startsWith(root + '/');
  /** the script of a "Write a script" run: analysis.sh in the run's folder – or in a folder below it (the nearest one). → its path, or null */
  const scriptOf = (fs, run) => {
    if (fs.exists(run + '/analysis.sh')) return run + '/analysis.sh';
    const found = Array.from(fs.entries.keys()).filter((k) => k.startsWith(run + '/') && k.endsWith('/analysis.sh') && fs.entries.get(k).kind !== 'dir');
    return found.sort((a, b) => a.split('/').length - b.split('/').length || a.localeCompare(b))[0] || null;
  };
  // the agent's own folder, and /tmp, where programs keep temporary files
  const agentMay = (k, root) => inside(k, root) || inside(k, '/tmp');
  /* What a command of the agent changes outside the agent's folder is put back. The page's file system is a
     map of entries, so a copy of the map (outsideSnapshot) is enough for text files and the course data.
     A file that a program wrote (BAM, a large SAM, .gz …) has its bytes in the programs' memory only: of those
     MG.wasm keeps a copy before the command runs (keep) and writes it back afterwards (putBack). */
  function outsideSnapshot(fs, root) {
    const m = new Map();
    for (const [k, v] of fs.entries) if (!agentMay(k, root)) m.set(k, v);
    return m;
  }
  /* What a command of the agent left behind INSIDE its folder and in its shell. A command that ended with another
     status than 0 but wrote a file, or set a variable, is part of what the run did: the commands after it may
     build on that. (diff a b > d ends with 1 when the files differ; n=$(grep -c x f) with 1 when the count is 0.)
     The script that the page makes from the run keeps such a command; one that failed and left nothing is left out. */
  function folderMarks(fs, root) {
    const m = new Map();
    // (the folder of the run, and /tmp – which is open to the agent: diff a b > /tmp/d.txt leaves something, too)
    for (const [k, v] of fs.entries) if ((k !== root && inside(k, root)) || (k !== '/tmp' && inside(k, '/tmp') && !/^\/tmp\/\.(psub-|pipes)/.test(k))) m.set(k, v.kind === 'dir' ? 'dir' : `file:${v.size}:${v.mtime}`);
    return m;
  }
  /** → { wrote: the paths that are new or changed, removed: those that are gone } – written from the folder (those in /tmp in full) */
  function marksChanged(before, after, root) {
    const name = (k) => (inside(k, root) ? k.slice(root.length + 1) : k);
    const wrote = [], removed = [];
    for (const [k, v] of after) if (before.get(k) !== v) wrote.push(k);
    for (const k of before.keys()) if (!after.has(k)) removed.push(k);
    return { wrote: wrote.sort().map(name), removed: removed.sort().map(name) };
  }
  const QUIET_VARS = new Set(['_', 'PWD', 'OLDPWD', 'PIPESTATUS', 'BASH_REMATCH', 'RANDOM', 'SRANDOM', 'SECONDS', 'LINENO', 'BASH_COMMAND', 'FUNCNAME', 'BASH_LINENO', 'BASH_SOURCE', 'EPOCHSECONDS', 'EPOCHREALTIME', 'BASHPID']);
  function shellMark(shell) {
    try {
      const st = shell._top();
      const flags = Object.keys(st.flags).filter((k) => !['se', 'su', 'sl'].includes(k) && st.flags[k]).sort();
      const vars = new Map();
      for (const k of Object.keys(st.vars)) if (!QUIET_VARS.has(k)) vars.set(k, JSON.stringify(st.vars[k] instanceof Map ? Array.from(st.vars[k]) : st.vars[k] === undefined ? null : st.vars[k]));
      return { vars, rest: JSON.stringify([flags, st.shopt || null, st.traps || null, st.args || []]), funcs: Object.assign({}, st.funcs) };
    } catch (e) {
      return null;
    }
  }
  /** what differs between two marks of the shell: the names of the variables and functions, and "a setting of the
      shell" for its options, traps and arguments. (No mark: nothing is known – taken as "no difference".) */
  function markDiff(a, b) {
    if (!a || !b) return [];
    const out = [];
    for (const [k, v] of b.vars) if (a.vars.get(k) !== v) out.push(k);
    for (const k of a.vars.keys()) if (!b.vars.has(k)) out.push(k);
    for (const k of Object.keys(b.funcs)) if (a.funcs[k] !== b.funcs[k]) out.push(k + '()');
    for (const k of Object.keys(a.funcs)) if (!(k in b.funcs)) out.push(k + '()');
    out.sort();
    if (a.rest !== b.rest) out.push('a setting of the shell');
    return out;
  }
  /** → { changed: paths that were put back or removed again, lost: paths whose contents could not be put back, killed }
      saved: Map of path → the entry the student saved in the editor while the command ran (that version stays);
      gen: MG.wasm.gen before the command; since: when it started */
  async function undoOutside(fs, root, snap, saved, gen, since) {
    const W = MG.wasm, changed = [], lost = [], gone = [];
    // the programs were stopped by force while the command ran: what lived in their memory is gone
    const killed = !!W && W.gen !== gen;
    // (the folders of the files that the student saved meanwhile stay, also if they are new)
    const savedDirs = new Set();
    for (const k of saved.keys()) for (let d = MG.path.dirname(k); d && d !== '/'; d = MG.path.dirname(d)) savedDirs.add(d);
    // 1. what the command made outside the folder goes
    for (const k of Array.from(fs.entries.keys())) {
      if (!agentMay(k, root) && !snap.has(k) && !saved.has(k) && !savedDirs.has(k)) {
        fs.entries.delete(k);
        changed.push(k);
      }
    }
    // 2. files that the command copied or moved – and that stay – get their own bytes: putting a file back must not change its copies
    if (W && W.ready && !killed) {
      try {
        await W.settle(fs);
      } catch (e) {
        console.error(e);
      }
    }
    // 3. what was there before is put back
    const back = []; // files that must come back from the browser's storage (IndexedDB), where they were written just before the command
    for (const [k, v] of snap) {
      if (saved.has(k)) continue;
      const now = fs.entries.get(k);
      if (v.kind === 'aioli' && killed) {
        // whatever is there now is not the student's file (a file the command wrote, or an older copy): it goes,
        // and the copy that was kept in the browser's storage just before the command comes back (below)
        if (now) {
          fs.entries.delete(k);
          if (now.kind !== 'blob' || !(MG.project && MG.project.kept && MG.project.kept.get(k) === now)) changed.push(k);
        } else if ((W.lostEntries || new Map()).get(k) !== v) changed.push(k); // (it was not the student's file any more when the programs were stopped)
        back.push(k);
        continue;
      }
      if (now === v) continue;
      fs.entries.set(k, v);
      changed.push(k);
      if (v.kind !== 'aioli') continue;
      let ok = false;
      try {
        ok = await W.putBack(k, v, since);
      } catch (e) {
        console.error(e);
      }
      if (!ok) {
        // its bytes cannot be had from the programs' memory any more: the copy in the browser's storage comes back
        fs.entries.delete(k);
        back.push(k);
      }
    }
    // 4. a file that the student saved in the editor meanwhile is the student's: that version stays, whatever the command did to it afterwards
    for (const [k, e] of saved) {
      if (agentMay(k, root) || fs.entries.get(k) === e) continue;
      for (const d of Array.from(fs.entries.keys())) if (d.startsWith(k + '/')) fs.entries.delete(d); // a folder the command put in its place
      try {
        fs.mkdirp(MG.path.dirname(k));
      } catch (x) {
        continue; // a file of the student's is where its folder was: the text is still in the editor
      }
      fs.entries.set(k, e);
      e.dirty = true;
      changed.push(k);
    }
    changed.forEach((k) => fs._changed(k, !fs.entries.has(k) ? 'remove' : fs.entries.get(k).kind === 'dir' ? 'mkdir' : 'write'));
    // the copies in the browser's storage (IndexedDB) of these files are written again
    if (MG.project && MG.project.kept) changed.forEach((k) => MG.project.kept.delete(k));
    if ((killed || back.length) && MG.project && MG.project.restoreBinary) {
      // After a forced stop: the files that were lost with the programs, outside the folder and inside it, as they
      // were before the command – also the ones in the agent's folder that the command had removed or moved.
      const only = new Set(back.concat(killed ? Array.from((W.lostTimes || new Map()).keys()) : []));
      try {
        await MG.project.restoreBinary(fs, { only, under: killed ? root : null });
      } catch (e) {
        /* no storage */
      }
      back.forEach((k) => {
        if (!fs.entries.has(k)) lost.push(k);
      });
    }
    // … and in the agent's own folder: what programs had written there during the command (or what the command had
    // put in the place of an ordinary file) is gone with them
    if (killed) for (const k of (W.lostEntries || new Map()).keys()) if (inside(k, root) && !fs.entries.has(k)) gone.push(k);
    return { changed, lost, killed, gone };
  }
  /** the words of a shell text that lead out of the folder it runs in (MG.shellLang.reach): the home folder, another
      absolute path, enough ".." to climb out, a cd that leaves – but not /dev/null, /tmp or the course data
      (which nobody can change). depth: how many folders below the run's folder the text starts in */
  function outsideWords(text, depth = 0, scripts, top) {
    try {
      return MG.shellLang.reach(text, { depth, home: HOME(), allow: ['~/data'], top: top || '$RUN_FOLDER', scripts });
    } catch (e) {
      return ['?']; // (reach does not throw – but if it ever did, the text counts as leading out)
    }
  }
  /** Of the paths that the shell worked out while a command of the agent ran (terminal.js: touched), the ones outside
      the agent's folder – also the folders above it (ls .., find "$PWD/.."). Not counted: /tmp and /dev, the
      programs' own folders, the course data (which nobody can change), and the root folder itself. */
  function reachedOutside(paths, root) {
    const data = MG.app.DATA;
    return Array.from(paths || []).filter((p) => !agentMay(p, root) && !(data && inside(p, data)) && !/^\/(dev|usr|bin|opt|proc|shared|keep)(\/|$)/.test(p) && p !== '/');
  }
  /* A command of the agent is "under way" from before it starts until what it changed outside the agent's
     folder has been put back. What the student does to files in that time (a new file or folder in the Files
     tab, a file made by a button of the instructions, a script made from an earlier run) waits for the end of
     the command – otherwise it would be taken for the agent's doing and undone. Saving in the editor does not wait. */
  MG.app = MG.app || {};
  MG.app.agentBusy = null;
  MG.app.agentRoot = null; // the folder of the run whose command is under way
  MG.app.agentWaiting = 0; // how many actions of the student are waiting
  MG.app.whenAgentIdle = async (quiet) => {
    let told = null;
    MG.app.agentWaiting++;
    try {
      while (MG.app.agentBusy) {
        if (!told && !quiet) told = setTimeout(() => toast('The agent’s command is still running – this follows as soon as it has finished.', null, 2500), 400);
        await MG.app.agentBusy;
      }
    } finally {
      MG.app.agentWaiting--;
      clearTimeout(told);
    }
  };
  const clock = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
  const took = (secs) => (secs >= 60 ? `${Math.floor(secs / 60)} min ${Math.round(secs % 60)} s` : secs >= 10 ? `${Math.round(secs)} s` : `${secs.toFixed(1)} s`);
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

  /* ------------------------------------------------------------------
     the panel
     ------------------------------------------------------------------ */
  class Assistant {
    constructor(root) {
      this.root = root;
      this.threads = {};
      this.msgs = [];
      this.busy = false;
      this.tab = 'chat';
      this.agentMode = store.get('ai:agentMode', 'ask');
      if (!MODES[this.agentMode]) this.agentMode = 'ask';
      this.settings = Object.assign({}, DEFAULTS, store.get('ai:settings', {}));
      this.runs = (store.get('ai:runs', []) || []).filter((r) => r && r.folder);
      try {
        this.key = window.sessionStorage.getItem(KEY_NAME) || '';
      } catch (e) {
        this.key = '';
      }
      // connected: a test with this service worked, and the key is still here
      this.ok = !!store.get('ai:ok', false) && (!!this.key || !needsKey(this.settings));
      this._build();
      this.refresh();
      bus.on('term:ask', (d) => this.askAboutError(d));
    }
    connected() {
      return this.ok;
    }

    _build() {
      const R = this.root;
      R.classList.add('ai');
      const tabs = h('div.ai-tabs', { role: 'tablist' });
      this.tabBtns = {};
      [['chat', 'Chat', 'sparkle'], ['agent', 'Agent', 'robot']].forEach(([k, label, ic]) => {
        const b = h('button.ai-tab', { type: 'button', role: 'tab', html: MG.icon(ic) + '<span>' + label + '</span>' });
        b.addEventListener('click', () => this.showTab(k));
        tabs.appendChild(b);
        this.tabBtns[k] = b;
      });
      this.statusEl = h('button.ai-status', { type: 'button', title: 'The AI service and model – click to change' });
      this.statusEl.addEventListener('click', () => this.settingsDialog());
      const newBtn = h('button.tbtn', { type: 'button', title: 'Start a new conversation (the chat forgets what was said)', html: MG.icon('reset') + '<span>New chat</span>' });
      newBtn.addEventListener('click', () => {
        if (this.busy) return toast('Wait until the AI has finished.', 'warn');
        this.msgs = [];
        this.threads.chat.innerHTML = '';
        this.welcome('chat');
        this.showTab('chat');
      });
      this.newBtn = newBtn;
      const setBtn = h('button.tbtn', { type: 'button', title: 'AI service, model and key', 'aria-label': 'AI settings', html: MG.icon('gear') });
      setBtn.addEventListener('click', () => this.settingsDialog());
      const body = h('div.ai-threads');
      ['chat', 'agent'].forEach((k) => {
        const t = h('div.ai-thread', { role: 'log', 'aria-live': 'polite', dataset: { tab: k } });
        this.threads[k] = t;
        body.appendChild(t);
      });
      this.connectEl = h('div.ai-connect');
      body.appendChild(this.connectEl);
      // the agent's ways of working
      this.modesEl = h('div.ai-modes', { role: 'radiogroup', 'aria-label': 'How the agent works' });
      this.modeBtns = {};
      Object.entries(MODES).forEach(([k, m]) => {
        const b = h('button.ai-modebtn', { type: 'button', role: 'radio', title: m.does, dataset: { mode: k } }, m.label);
        b.addEventListener('click', () => this.setMode(k));
        this.modesEl.appendChild(b);
        this.modeBtns[k] = b;
      });
      this.modeNote = h('div.ai-modenote');
      this.input = h('textarea.ai-input', { rows: 2, 'aria-label': 'Message to the AI' });
      this.sendBtn = h('button.btn.primary.ai-send', { type: 'button', title: 'Send (Enter)', html: MG.icon('send') + '<span>Send</span>' });
      this.sendBtn.addEventListener('click', () => (this._abort ? this.stop() : this.send()));
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (!this._abort) this.send();
        }
      });
      this.foot = h('div.ai-foot', h('div.ai-modebox', this.modesEl, this.modeNote), h('div.ai-inrow', this.input, this.sendBtn));
      R.append(h('div.ai-bar', h('span.ai-title', { html: MG.icon('sparkle') + ' AI' }), tabs, this.statusEl, h('span.grow'), newBtn, setBtn), body, this.foot);
      this.welcome('chat');
      this.welcome('agent');
      this.setMode(this.agentMode, true);
      this.showTab('chat', true);
    }
    /** show what fits the state: the connect form, or the conversation */
    refresh() {
      const on = this.ok;
      this.root.classList.toggle('offline', !on);
      this.connectEl.hidden = on;
      Object.entries(this.threads).forEach(([n, t]) => (t.hidden = !on || n !== this.tab));
      this.foot.hidden = !on;
      this.showStatus();
      if (!on) this.connectForm(this.connectEl, { inline: true });
    }
    /** the bar: the chosen model – and, while that model is at rest (busy, silent, over a limit), that another one answers */
    showStatus() {
      const on = this.ok;
      const model = modelOf(this.settings);
      const r = on && this.settings.provider === 'gemini' && restKey === this.key ? resting(model) : null;
      this.statusEl.innerHTML = on ? `<span class="kdot ${r ? 'rest' : 'ok'}"></span> ${esc(model)}${r ? ` <small class="ai-rest">${esc(r.why === 'limit' ? 'over its limit' : skipWord(r))}</small>` : ''}` : '<span class="kdot"></span> not connected';
      this.statusEl.title = r ? `${model} ${told(r)}. Until that is over, the next model of the list answers – every answer names its model. Click to change the service or the model.` : 'The AI service and model – click to change';
    }
    showTab(k, quiet) {
      this.tab = k;
      Object.entries(this.tabBtns).forEach(([n, b]) => {
        b.classList.toggle('on', n === k);
        b.setAttribute('aria-selected', String(n === k));
      });
      Object.entries(this.threads).forEach(([n, t]) => (t.hidden = !this.ok || n !== k));
      this.root.classList.toggle('agent', k === 'agent');
      this.newBtn.hidden = k !== 'chat';
      this.input.placeholder = k === 'agent' ? 'Give the agent a task – what you want done, with which files, and what you want back' : 'Ask a question – for example, how to do something with the programs here';
      if (!quiet) bus.emit('ai:tab', { tab: k });
    }
    setMode(k, quiet) {
      if (!MODES[k]) return;
      this.agentMode = k;
      store.set('ai:agentMode', k);
      Object.entries(this.modeBtns).forEach(([n, b]) => {
        b.classList.toggle('on', n === k);
        b.setAttribute('aria-checked', String(n === k));
      });
      this.modeNote.textContent = MODES[k].does;
      if (!quiet) bus.emit('agent:mode', { mode: k });
    }
    welcome(tab) {
      if (tab === 'agent') {
        this.addBubble('assistant', 'I am an **AI agent**: give me a task and I carry it out myself, by running commands in your terminal. Each task gets a folder of its own under `~/runs`, with a copy of the data.\n\nChoose below how much I may do without asking you. The page keeps a record of every run – what I was asked, each command and the end of what it printed – in `RUN.md` in the run’s folder. I do not write that record, and I cannot change it.', { intro: true, tab: 'agent' });
        this.pastRuns();
        return;
      }
      this.addBubble('assistant', 'I am an **AI assistant**: a language model that answers questions. I know which programs this terminal has, and the names of your files – but I cannot run anything, and I do not see what your commands print unless you send it to me.\n\nSo check what I tell you: run it, read the output, look at `--help`.', { intro: true, tab: 'chat' });
    }
    /** offer a prompt from the instructions: it goes into the box, for the student to read, change and send */
    offerPrompt(text, tab, mode) {
      if (!this.ok) {
        toast('Connect the AI first: it needs an API key.', 'warn', 5000);
        return;
      }
      if (this.busy) return toast('The AI is still busy – wait until it has finished.', 'warn');
      this.showTab(tab === 'agent' ? 'agent' : 'chat');
      if (mode) this.setMode(mode);
      this.input.value = text;
      this.input.focus();
      this.input.classList.add('flash');
      setTimeout(() => this.input.classList.remove('flash'), 1200);
      this.input.style.height = 'auto';
      this.input.style.height = Math.min(220, this.input.scrollHeight + 4) + 'px';
      bus.emit('ai:offer', { tab: this.tab, mode: mode || '' });
    }

    /* ---------------- messages ---------------- */
    addBubble(role, md, meta = {}) {
      const tab = meta.tab || this.tab;
      const b = h('div.ai-msg.' + role + (meta.intro ? '.intro' : ''));
      const body = h('div.ai-body');
      if (role === 'user') body.textContent = md;
      else this.fill(body, md);
      b.appendChild(body);
      if (meta.badge) b.appendChild(h('div.ai-badge', { html: meta.badge }));
      this.threads[tab].appendChild(b);
      this.scroll(tab);
      return b;
    }
    scroll(tab) {
      const t = this.threads[tab || this.tab];
      t.scrollTop = t.scrollHeight;
    }
    /** opts.plain: code blocks without buttons (the agent's own text) */
    fill(body, md, opts = {}) {
      body.innerHTML = '';
      renderMarkdown(md).forEach((blk) => {
        if (blk.html) body.insertAdjacentHTML('beforeend', blk.html);
        else body.appendChild(opts.plain ? h('pre.ai-code.plain', h('code', blk.code)) : this.codeBox(blk));
      });
    }
    codeBox(blk) {
      const pre = h('pre.ai-code', h('code', blk.code));
      const acts = h('div.ai-code-acts');
      const btn = (icon, label, fn, primary) => {
        const b = h('button.btn.small' + (primary ? '.primary' : ''), { type: 'button', html: (icon ? MG.icon(icon) : '') + '<span>' + esc(label) + '</span>' });
        b.addEventListener('click', async () => {
          b.disabled = true;
          try {
            await fn(b);
          } catch (e) {
            console.error(e);
            toast(esc(e.message || String(e)), 'error');
          } finally {
            b.disabled = false;
          }
        });
        return b;
      };
      const shell = /^(bash|sh|shell|console|zsh)$/.test(blk.lang);
      const script = shell && /^#!/.test(blk.code.trim());
      if (shell && !script) {
        // the commands go to the terminal one at a time, for the student to run
        let cmds = [];
        try {
          cmds = MG.shellLang.statements(blk.code.split('\n').map((l) => l.replace(/^\s*\$\s+/, '')).join('\n'), MG.app.term && MG.app.term.shell ? { extglob: MG.shellLang.extglobOn(MG.app.term.shell._top()) } : undefined);
          // a command that is only spread over lines with \ at the line ends fits the prompt as one line
          cmds = cmds.map((c) => {
            const one = c.replace(/[ \t]*\\\n[ \t]*/g, ' ');
            return one.includes('\n') ? c : one;
          });
        } catch (e) {
          cmds = [];
        }
        if (cmds.length) {
          let k = 0;
          // a block of several lines (a loop, a here-document) does not fit the one-line prompt: it is run as it is
          const label = () => (cmds[k].includes('\n') ? 'Run this block' : 'Put ' + (cmds.length === 1 ? 'it' : `command ${k + 1} of ${cmds.length}`)) + (cmds.length > 1 && cmds[k].includes('\n') ? ` (${k + 1} of ${cmds.length})` : '') + ' in the terminal';
          acts.appendChild(btn('terminal', label(), async (b) => {
            await this.toTerminal(cmds[k]);
            k = (k + 1) % cmds.length;
            b.querySelector('span').textContent = label();
          }, true));
        }
      }
      if (blk.lang === 'file' || script || (blk.file && /\.\w+$/.test(blk.file))) acts.appendChild(btn('save', 'Save as a file…', () => this.saveAs(blk.file || (script ? 'script.sh' : 'file.txt'), blk.code), !shell || script));
      acts.appendChild(btn('copy', 'Copy', async () => ((await MG.copyText(blk.code)) ? toast('Copied.') : toast('Could not copy.', 'error'))));
      return h('div.ai-codebox', blk.lang === 'file' && blk.file ? h('div.ai-code-file', blk.file) : null, pre, acts);
    }
    async saveAs(suggested, code) {
      const fs = MG.app.fs;
      const base = fs.cwd.startsWith(HOME()) ? fs.pretty(fs.cwd) : '~';
      const name = window.prompt('Save as (a path in your home folder):', (base === '~' ? '~/' : base + '/') + suggested.replace(/^.*\//, ''));
      if (!name) return;
      const path = fs.resolve(name);
      if (!inside(path, HOME()) || path === HOME()) return toast('Files can only be saved in your home folder.', 'warn');
      const e = fs.get(path);
      if (e && (e.kind === 'dir' || e.readonly || e.protected)) return toast(esc(fs.pretty(path)) + (e.kind === 'dir' ? ' is a folder.' : ' is read-only.'), 'error');
      if (e && !window.confirm(`${fs.pretty(path)} already exists. Replace it?`)) return;
      await MG.app.whenAgentIdle();
      fs.mkdirp(MG.path.dirname(path));
      fs.writeText(path, code.replace(/\s+$/, '') + '\n');
      await MG.app.editFile(path, { line: 1 });
      toast(`Saved <b>${esc(fs.pretty(path))}</b>.`, null, 3000);
      bus.emit('ai:insert', { target: 'file', path, name: path.split('/').pop() });
    }
    async toTerminal(line) {
      const T = MG.app.term;
      if (T.locked) return toast('The agent is using the terminal – wait until it has finished.', 'warn');
      MG.app.showWorkbench('terminal');
      if (line.includes('\n')) {
        // a block (a loop, a here-document): typed as it is and run
        await T._submit(line);
      } else await T.type(line, false);
      bus.emit('ai:insert', { target: 'terminal' });
    }

    /* ---------------- sending ---------------- */
    setBusy(on) {
      this.busy = on;
      this.sendBtn.innerHTML = on ? MG.icon('stop') + '<span>Stop</span>' : MG.icon('send') + '<span>Send</span>';
      this.sendBtn.title = on ? 'Stop' : 'Send (Enter)';
      Object.values(this.modeBtns).forEach((b) => (b.disabled = on));
      Object.values(this.tabBtns).forEach((b) => (b.disabled = on));
    }
    stop() {
      if (this._abort) this._abort.abort();
      // a program that is running is asked to stop as well
      if (this._agentRunning && MG.app.term.busy) MG.app.term.stop();
    }
    async send() {
      const q = this.input.value.trim();
      if (!q) return;
      if (!this.ok) return toast('Connect the AI first.', 'warn');
      if (this.busy) return toast('The AI is still busy – wait for it to finish, or press Stop.', 'warn');
      this.input.value = '';
      this.input.style.height = '';
      bus.emit('ai:ask', { text: q, tab: this.tab, mode: this.tab === 'agent' ? this.agentMode : '', source: 'typed' });
      if (this.tab === 'agent') return this.agent(q, this.agentMode);
      this.addBubble('user', q);
      this.msgs.push({ role: 'user', content: q });
      return this.chat();
    }

    /* ---------------- chat ---------------- */
    chatPrompt() {
      return [
        'You are an AI assistant in a browser-based practical for MSc bioinformatics students about using AI assistants and AI agents in bioinformatics, and about making an analysis reproducible. The student works in a Linux-like terminal that runs inside the web page.',
        '',
        'The terminal:',
        ...environment('~/data').map((l) => '- ' + l),
        '',
        'How to answer:',
        '- Be brief and plain. Give commands in ```bash code blocks, one command per line, with real file names and relative paths where you can; the student runs them.',
        '- You cannot run anything, and you see only what the student sends you. Never write as if you had run a command or seen a file: say what the student should look for instead.',
        '- Use only options that exist in the versions listed. If you are not sure of an option, say so and point to PROGRAM --help.',
        '- If the student sends an error message, say what it means and what to change.'
      ].join('\n');
    }
    /** what is sent with a question: where the student is and which files are there (names only) */
    context(extra) {
      const fs = MG.app.fs;
      let ctx = `The student is in the folder ${fs.pretty(fs.cwd)}.`;
      const names = [];
      const walk = (dir, depth) => {
        for (const c of fs.list(dir)) {
          if (c.name.startsWith('.') || names.length >= 60) continue;
          names.push(fs.pretty(c.path) + (c.entry.kind === 'dir' ? '/' : ''));
          if (c.entry.kind === 'dir' && depth < 2 && c.name !== 'runs') walk(c.path, depth + 1);
        }
      };
      walk(HOME(), 0);
      ctx += ` Their files: ${names.join(', ') || '(none)'}.\n\n`;
      if (extra && extra.error) ctx += `The command that failed: \`${extra.error.line}\` (run in ${fs.pretty(extra.error.cwd)}). The end of what it printed:\n\`\`\`text\n${(extra.error.output || '').slice(-3000)}\n\`\`\`\n\n`;
      return ctx;
    }
    async chat(extra) {
      this.setBusy(true);
      this._abort = new AbortController();
      const b = this.addBubble('assistant', '', { tab: 'chat' });
      const body = b.querySelector('.ai-body');
      body.innerHTML = '<span class="ai-typing"><i></i><i></i><i></i></span>';
      const hist = this.msgs.slice(-14).map((m) => ({ role: m.role, content: m.content }));
      while (hist.length && hist[0].role !== 'user') hist.shift();
      if (hist.length) hist[hist.length - 1] = { role: 'user', content: this.context(extra) + hist[hist.length - 1].content };
      let text = '';
      const t0 = performance.now();
      try {
        const res = await this.stream(hist, (d) => {
          text += d;
          this.fill(body, text + ' ▍');
          this.scroll('chat');
        }, this._abort.signal, { system: this.chatPrompt(), onReset: () => (text = '') }, (note) => {
          if (!text) body.innerHTML = `<div class="ai-wait">${esc(note)}</div><span class="ai-typing"><i></i><i></i><i></i></span>`;
        });
        // a reply with nothing in it is not kept as a turn of the conversation: it is reported, and the question can be asked again
        if (!text.trim()) throw Object.assign(new Error(`${res.model} sent an empty reply. Ask again – a second try usually gets an answer.`), { empty: true });
        this.fill(body, text);
        const via = res.skipped.length ? ` (${res.skipped.map((x) => x.model + ' ' + skipWord(x)).join(', ')})` : '';
        b.appendChild(h('div.ai-badge', `${res.model}${via} · ${((performance.now() - t0) / 1000).toFixed(1)} s`));
        this.msgs.push({ role: 'assistant', content: text });
        bus.emit('ai:answer', { tab: 'chat', model: res.model });
      } catch (e) {
        if (e.name === 'AbortError') {
          this.fill(body, (text || '') + '\n\n*(stopped)*');
          if (text) this.msgs.push({ role: 'assistant', content: text });
        } else {
          this.fill(body, (e.empty ? '' : '**The AI service returned an error.**\n\n') + e.message);
          b.classList.add('err');
          // the question stays in the conversation only if it was answered
          if (this.msgs.length && this.msgs[this.msgs.length - 1].role === 'user') this.msgs.pop();
        }
      } finally {
        this._abort = null;
        this.setBusy(false);
        this.scroll('chat');
      }
    }
    /** "Ask the AI about this error", from a failed command in the terminal */
    async askAboutError(d) {
      MG.app.showWorkbench('assistant');
      if (!this.ok) return toast('Connect the AI first: it needs an API key.', 'warn', 5000);
      if (this.busy) return toast('The AI is still busy – try again in a moment.', 'warn');
      this.showTab('chat');
      const err = (d.error || d.output || '').trim();
      const q = `My command failed:\n$ ${d.line}\n${err.split('\n').slice(-12).join('\n')}`;
      this.addBubble('user', q);
      this.msgs.push({ role: 'user', content: 'My command failed. What does the error mean, and what should I change?' });
      bus.emit('ai:ask', { text: q, tab: 'chat', mode: '', source: 'terminal' });
      return this.chat({ error: d });
    }

    /* ---------------- the agent ---------------- */
    agentPrompt(mode) {
      const how = [
        'You are an AI agent in a practical for MSc bioinformatics students. You carry out the user’s task by running shell commands in a Linux-like terminal. You can do nothing except through commands, and you know about the files only what commands show you.',
        '',
        'How you work:',
        '- In each reply, first say in one or two short sentences what you are about to do and why. Then give ONE step:',
        '    a ```bash code block with the command to run – a few closely related commands may share a block, one per line; they run in order, and the first one that fails stops the rest of the block;',
        '    or, to write a text file (a script, a table, notes), a block that starts with ```file:NAME and holds the complete contents of the file. NAME is a plain name in your folder (letters, digits and . _ - /). A file block may be followed by a ```bash block in the same reply (the file is written first).',
        '  Then stop. You will be sent the exit status and the output of each command.',
        '- Decide the next step from what the output shows. If a command fails, read its message and change your approach; do not send the same failing command again.',
        '- Do not ask the user questions: nobody will answer. Decide, say what you decided, and go on.',
        '- Every step starts in your folder; a cd lasts until the end of that step only. Use relative paths. Changes to files outside your folder are undone.',
        `- You have at most ${MAX_STEPS} steps. Of long output you get only the beginning and the end (${OUT_CHARS} characters in all), so write long output to a file and look at part of it (head, tail, grep, wc).`,
        '- When the task is done – or cannot be done – send your last reply. It starts with the word REPORT on a line of its own and has no ```bash block. It is your report to the user: what you did (the main commands and options), the files you made, and the result, with the numbers that support it. Report only what the outputs showed. Never invent output, file names, numbers or versions; if something did not work, or you are not sure, say so.'
      ];
      const extra = {
        ask: ['', 'The user sees each of your steps before it runs. They may run it, change it or refuse it, and you will be told which. If a step is refused, do not try the same thing by another route: take the user’s reason into account.'],
        plan: ['', 'Start with a plan, and run nothing yet. Your first reply is a short numbered plan: for each step the program and its main options, the files it makes, and at the end how you will check the result. No code blocks. The user will approve the plan or ask for changes. After the approval, carry the plan out step by step as described above; if you have to depart from the plan, say so and say why.'],
        auto: [],
        script: ['', 'What the user wants from you is ONE bash script, analysis.sh, that does the whole analysis from the files in data/ when it is run with `bash analysis.sh` in your folder – a script that someone else can run again and get the same result. Start it with `#!/usr/bin/env bash` and `set -euo pipefail`, put a comment before each step, and let it print the answer to the task at the end. You may look at the data first. Then write the script with a ```file:analysis.sh block, run it with `bash analysis.sh`, read what it prints, and repair it – send the whole file again – until it runs without an error. In your report say what the script does and what it printed.']
      }[mode];
      return how.concat(extra, ['', 'Your environment:'], environment('data').map((l) => '- ' + l)).join('\n');
    }
    /** one turn: the model's reply. When no model answers and waiting can help – a limit per minute, servers that
        are busy, a connection that gave no answer: the error says after how many seconds (retryIn, 5–90) – the page
        waits and asks again, up to three times for one reply; then the run ends with that error. When waiting cannot
        help (every model over its limit for today, a key that is not accepted), the run ends at once. */
    async agentAsk(hist, system, signal, note, onText) {
      for (let waited = 0; ; waited++) {
        let text = '';
        try {
          const res = await this.stream(hist, (d) => {
            text += d;
            onText(text);
          }, signal, { system, onReset: () => {
            text = '';
            onText('');
          } }, note);
          return { text, model: res.model };
        } catch (e) {
          const wait = e.name !== 'AbortError' && e.retryIn > 0 ? Math.round(Math.min(90, Math.max(5, e.retryIn))) : 0;
          if (wait && waited >= 3) e.message += (e.status === 429 ? ' The page waited three times and the limit is still reached – a key that many people are using at once, perhaps.' : e.status ? ' The page waited three times and asked again: the service is still busy.' : ' The page waited three times and asked again: still no answer.') + ' Go on later' + (e.status ? ', or use a key from another person or project (limits are counted per project, not per key)' : '') + '; what the agent has done so far is in its folder and in the record.';
          if (!wait || waited >= 3) throw e;
          for (let t = wait; t > 0; t--) {
            note(`${e.status === 429 ? 'The service allows only a few requests per minute' : e.status ? 'The service is busy' : 'No answer came from the service'} – waiting ${t} s, then asking again (Stop ends the task)…`);
            await pause(1000, signal);
          }
          note('');
        }
      }
    }
    /** run a command in the student's terminal and get what it printed */
    async termRun(cmd, timeout) {
      const T = MG.app.term;
      for (let i = 0; i < 600 && T.busy; i++) await sleep(100);
      const before = T.outEl.children.length;
      let timedOut = false, again = null;
      const timer = timeout
        ? setTimeout(() => {
            timedOut = true;
            T.stop();
            T.stop(true);
            // a program that was only just being started is not yet "running" at that moment: stop again until the command has ended
            again = setInterval(() => T.stop(true), 500);
          }, timeout)
        : null;
      let code;
      try {
        code = await T.exec(cmd, { agent: true });
      } finally {
        clearTimeout(timer);
        clearInterval(again);
      }
      const els = Array.from(T.outEl.children).slice(before + 1);
      const text = els.filter((x) => !x.classList.contains('ask')).map((x) => x.textContent + (x.classList.contains('note') ? '\n' : '')).join('');
      return { code, text, timedOut };
    }
    agentCard(title) {
      const card = h('div.ai-msg.assistant.ag');
      const head = h('div.ag-head', { html: MG.icon('robot') + '<b></b><span class="ag-where"></span>' });
      head.querySelector('b').textContent = title;
      const steps = h('ol.ag-steps');
      const noteEl = h('div.ai-wait');
      card.append(head, steps, noteEl);
      this.threads.agent.appendChild(card);
      this.scroll('agent');
      return { card, head, steps, noteEl };
    }

    async agent(task, mode) {
      const fs = MG.app.fs, T = MG.app.term;
      if (!T || !fs.exists(MG.app.DATA + '/' + INPUTS()[0])) return this.addBubble('assistant', 'The terminal is not ready yet – try again in a moment.', { tab: 'agent' });
      if (T.busy) return toast('The terminal is busy – wait until its command has finished.', 'warn');
      this.addBubble('user', task, { tab: 'agent' });
      this.setBusy(true);
      this._agentRunning = true;
      this._abort = new AbortController();
      const signal = this._abort.signal;
      // a folder of its own, with a read-only copy of the data
      // (a number is not given twice: not that of a folder that is there, whatever its way of working)
      let n = this.runs.reduce((a, r) => Math.max(a, r.id), 0) + 1;
      const taken = () => fs.isDir(HOME() + '/runs') && fs.list(HOME() + '/runs').some((c) => c.name.startsWith(n + '-'));
      while (taken()) n++;
      const run = `${HOME()}/runs/${n}-${MODES[mode].word}`;
      fs.mkdirp(run + '/data');
      INPUTS().forEach((f) => {
        fs.copy(MG.app.DATA + '/' + f, run + '/data/' + f);
        fs.chmod(run + '/data/' + f, { readonly: true });
      });
      const back = fs.cwd;
      const started = new Date();
      const t0 = performance.now();
      const R = { id: n, mode, modeLabel: MODES[mode].label, task, folder: fs.pretty(run), started: started.toISOString(), service: serviceOf(this.settings), models: [], requests: 0, plan: null, planRounds: 0, steps: [], report: '', outcome: 'done', error: '' };
      const ui = this.agentCard(`Run ${n} · ${MODES[mode].label.toLowerCase()}`);
      ui.head.querySelector('.ag-where').textContent = fs.pretty(run);
      ui.card.classList.add('live');
      const note = (t) => {
        ui.noteEl.textContent = t || '';
        this.scroll('agent');
      };
      const system = this.agentPrompt(mode);
      const hist = [{ role: 'user', content: task }];
      const ask = async (li) => {
        const say = li.querySelector('.ag-say');
        for (let empty = 1; ; empty++) {
          const res = await this.agentAsk(hist, system, signal, note, (t) => {
            say.textContent = parseReply(t).say || 'thinking…';
            this.scroll('agent');
          });
          note('');
          R.requests++;
          if (!R.models.includes(res.model)) R.models.push(res.model);
          // A reply with nothing in it – a model can end one before it has begun. It is not a turn of the
          // conversation: the same question is asked again.
          if (res.text.trim()) return res.text;
          if (empty >= 3) throw new Error(`${res.model} sent an empty reply, three times in a row. Start the task again; if it happens again, choose another model in the AI settings (⚙).`);
          note(`${res.model} sent an empty reply – asking again…`);
        }
      };
      const newStep = () => {
        const li = h('li.ag-step.run', h('span.ag-ic', { html: '<span class="spinner small"></span>' }), h('div.ag-main', h('div.ag-say.muted', 'thinking…')));
        ui.steps.appendChild(li);
        this.scroll('agent');
        return li;
      };
      bus.emit('agent:start', { mode, run: n, folder: fs.pretty(run) });
      // the agent works in a new shell: no variables, functions or options of the student's – and none of its own are left behind
      const shellState = T.shell.saveState();
      T.shell.freshState();
      // (the script that the page makes from the run has set -eu; the commands here run without. The shell notes
      // where the two would differ – see nounset in shell-lang.js)
      this._shadow = { e: 0, u: [] };
      Object.assign(T.shell._top().flags, { se: true, su: true, sl: this._shadow });
      // (… and, like a script, it reads the pattern groups !(a|b), +(a|b) only after  shopt -s extglob : what the
      // agent's commands do here, the script made from them must be able to do)
      T.shell._top().shopt = Object.assign({}, T.shell._top().shopt, { extglob: false });
      T.lock(`The agent (run ${n}) is using the terminal.`);
      T.note(`AI agent · run ${n} (${MODES[mode].label.toLowerCase()}) starts in ${fs.pretty(run)} – its commands follow.`);
      try {
        fs.cwd = run;
        T._renderPrompt();
        if (mode === 'plan') await this.planPhase(R, hist, ui, ask, newStep, signal, run);
        let asking = mode === 'ask', nudges = 0, askedForScript = false;
        for (;;) {
          const li = newStep();
          const main = li.querySelector('.ag-main');
          const text = await ask(li);
          const P = parseReply(text);
          const say = li.querySelector('.ag-say');
          say.classList.remove('muted');
          if (!P.final && !P.file && P.bash == null && !P.open && nudges < 2) {
            // neither a step nor a report (a model thinking aloud, or commands in a block without "bash"): say so, once or twice
            nudges++;
            li.remove();
            hist.push({ role: 'assistant', content: text }, { role: 'user', content: 'That reply had no step and was not a report. ' + (P.other.length ? `A block marked ${P.other[0]} is not run: there is only the shell here (awk, sed, grep, jq … inside a \`\`\`bash block). ` : P.unlabelled ? 'A command must be in a code block that starts with ```bash. ' : '') + 'If the task is done, send your report: it starts with the word REPORT. If not, send the next step now, as a ```bash block.' });
            continue;
          }
          if (P.final || (!P.file && P.bash == null && !P.open)) {
            if (mode === 'script' && !askedForScript && !scriptOf(fs, run) && R.steps.length < MAX_STEPS - 1) {
              // "Write a script" – and there is no script: the model worked step by step. Ask for the script, once.
              askedForScript = true;
              li.remove();
              hist.push({ role: 'assistant', content: text }, { role: 'user', content: 'There is no file analysis.sh in your folder. What the user asked for is one script that does the whole analysis. Write it now with a ```file:analysis.sh block – the commands that worked, in order, with a comment before each step – and run it with `bash analysis.sh` in the same reply. Send your report after it has run without an error.' });
              continue;
            }
            li.remove();
            R.report = cleanReport(text);
            break;
          }
          nudges = 0;
          say.textContent = P.say || '(no explanation)';
          const step = { n: R.steps.length + 1, say: P.say, file: null, commands: [], approval: null, comment: '' };
          if (P.early) step.early = P.early;
          let result = '';
          if (P.open && !P.file && P.bash == null) {
            R.steps.push(step);
            step.note = 'The reply ended inside a code block that was not closed – nothing was run.';
            result = 'Your reply ended inside a code block that was not closed – it was cut off, or a closing ``` is missing – so nothing was written or run. Send that step again; if it was long, make it shorter.';
            this.stepDone(li, false);
            main.appendChild(h('small.ag-note', step.note));
          } else {
            const deny = P.bash != null ? refusal(P.bash) : '';
            let allowed = true;
            if (asking && !deny) {
              // nothing runs until the student has decided (Stop ends the run here, before the step counts)
              const d = await this.approve(main, P, signal);
              step.approval = d.choice;
              step.comment = d.comment;
              bus.emit('agent:approve', { choice: d.edited ? 'edited' : d.choice, run: n });
              if (d.choice === 'all') asking = false;
              if (d.choice === 'refused') {
                allowed = false;
                result = 'The user did not allow this step, so nothing was run.' + (d.comment ? ` Their reason: ${d.comment}` : '');
                step.commands = (P.bash ? [P.bash] : []).map((cmd) => ({ cmd, code: null, secs: 0, output: '', skipped: 'refused by the user' }));
                if (P.file) step.file = { name: P.file.name, bytes: 0, skipped: 'refused by the user' };
              } else if (d.edited) {
                result = 'The user changed this step before it ran; what ran is shown below.' + (d.comment ? ` Their comment: ${d.comment}` : '') + '\n';
                step.edited = { bash: P.bash, file: P.file ? P.file.text : null };
                P.bash = d.bash;
                if (P.file) P.file.text = d.fileText;
              } else if (d.comment) result = `The user allowed this step, with a comment: ${d.comment}\n`;
            }
            R.steps.push(step);
            if (!allowed) this.stepDone(li, false, '⛔');
            else {
              let ok = true;
              if (P.file) {
                const r = this.agentWrite(run, P.file, step, main);
                result += r.text;
                ok = r.ok;
              }
              if (P.bash != null && ok) {
                const r = await this.agentRun(run, P.bash, step, main, signal, deny);
                result += r.text;
                ok = r.ok;
              }
              this.stepDone(li, ok);
            }
          }
          // a report in the same reply as the step: it was written before the step had run
          if (P.early) {
            result += '\n(You wrote a report in the same reply as this step. It was not taken as your report: the step had not run when you wrote it. When the task is done, send the report in a reply of its own – it starts with REPORT and has no code block – and put into it only what the commands really printed.)';
            main.appendChild(h('small.ag-note', 'In the same reply the agent wrote a report – before this step had run. It was not taken as the report, and the agent was told so. The record (RUN.md) has what it wrote.'));
          }
          if (P.more) result += `\n(Your reply had ${P.more + 1} bash blocks. Only the first one of a reply is run: send the others one at a time.)`;
          // a second file in the same reply is not written: the model is told, and the card says so
          if (P.moreFiles) {
            result += `\n(Your reply had ${P.moreFiles + 1} file blocks. Only the first file of a reply is written${P.file ? ` – ${P.file.name}` : ''}: the other${P.moreFiles > 1 ? 's were' : ' was'} NOT written. Send each further file in a reply of its own.)`;
            step.note = `The reply held ${P.moreFiles + 1} files: only the first one was written, and the agent was told to send the other${P.moreFiles > 1 ? 's' : ''} again.`;
            main.appendChild(h('small.ag-note', step.note));
          }
          // a block that was never closed, after a step that was taken: say so – a file may be incomplete
          if (P.open && (P.file || P.bash != null)) {
            result += '\n(Your reply ended inside a code block that was never closed – it was probably cut off, and that part was not used. Check what was written, and send what is missing again.)';
            step.note = 'The reply ended inside a code block that was not closed: that part was not used.';
            main.appendChild(h('small.ag-note', step.note));
          }
          if (signal.aborted) throw stopped();
          const left = MAX_STEPS - R.steps.length;
          if (left <= 0) {
            // the limit: one more turn, for the report
            hist.push({ role: 'assistant', content: text }, { role: 'user', content: result + `\n\nYou have used all ${MAX_STEPS} steps. Send your report now (start with REPORT, no bash block): what you did, the files you made, the result – and what is not finished.` });
            const li2 = newStep();
            const last = await ask(li2);
            li2.remove();
            R.report = cleanReport(parseReply(last).final ? last : parseReply(last).say || last);
            R.outcome = 'limit';
            break;
          }
          hist.push({ role: 'assistant', content: text }, { role: 'user', content: result + (left <= 3 ? `\n\n(${plural(left, 'step')} left.)` : '') });
        }
      } catch (e) {
        R.outcome = e.name === 'AbortError' ? 'stopped' : 'error';
        R.error = R.outcome === 'error' ? e.message : '';
        ui.card.querySelectorAll('.ag-approve').forEach((x) => x.remove());
        ui.steps.querySelectorAll('li.run').forEach((li) => {
          if (li.querySelector('.ag-cmd, .ag-file')) this.stepDone(li, false, '–');
          else li.remove();
        });
        if (R.outcome === 'error') console.error(e);
      } finally {
        note('');
        T.unlock();
        if (MG.wasm && MG.wasm.dropKept) MG.wasm.dropKept().catch(() => {});
        // (the agent's shell does not end like a script: a trap … EXIT that it set never runs here – the script says so)
        try {
          if (T.shell._top().traps && T.shell._top().traps.EXIT) R.exitTrap = true;
        } catch (e) {
          /* no trap */
        }
        this._shadow = null;
        T.shell.restoreState(shellState);
        if (fs.isDir(back)) fs.cwd = back;
        T._renderPrompt();
        T.note(`AI agent · run ${n} ${R.outcome === 'done' ? 'finished' : R.outcome === 'limit' ? 'stopped at its limit of steps' : R.outcome === 'stopped' ? 'was stopped' : 'ended with an error'}. The record is ${fs.pretty(run)}/RUN.md`);
        R.finished = new Date().toISOString();
        R.seconds = Math.round((performance.now() - t0) / 100) / 10;
        this._abort = null;
        this._agentRunning = false;
        try {
          await this.record(R, run);
        } catch (e) {
          console.error(e);
          toast('The record of the run could not be written: ' + esc(e.message), 'error');
        }
        this.finishCard(ui, R, run);
        const cmds = R.steps.reduce((a, s) => a + s.commands.filter((c) => !c.skipped).length, 0);
        const failed = R.steps.reduce((a, s) => a + s.commands.filter((c) => c.code).length, 0);
        this.runs.push({ id: n, mode, outcome: R.outcome, folder: fs.pretty(run), task: task.slice(0, 200), started: R.started, steps: R.steps.length, commands: cmds, model: R.models.join(', ') });
        store.set('ai:runs', this.runs);
        this.setBusy(false);
        this.scroll('agent');
        bus.emit('agent:done', { mode, ok: R.outcome === 'done', outcome: R.outcome, run: n, steps: R.steps.length, commands: cmds, failed, folder: fs.pretty(run) });
      }
    }
    stepDone(li, ok, mark) {
      li.classList.remove('run');
      li.classList.toggle('bad', !ok);
      li.querySelector('.ag-ic').textContent = mark || (ok ? '✓' : '✗');
    }
    /** plan first: the model's plan, the student's verdict – until the plan is approved */
    async planPhase(R, hist, ui, ask, newStep, signal, run) {
      for (;;) {
        const li = newStep();
        const main = li.querySelector('.ag-main');
        const text = await ask(li);
        R.planRounds++;
        const say = li.querySelector('.ag-say');
        say.classList.remove('muted');
        say.textContent = R.planRounds === 1 ? 'The agent’s plan:' : `The agent’s plan, version ${R.planRounds}:`;
        const body = h('div.ai-body.ag-plan');
        this.fill(body, text, { plain: true });
        main.appendChild(body);
        li.classList.remove('run');
        li.querySelector('.ag-ic').textContent = '☰';
        this.scroll('agent');
        const d = await new Promise((resolve, reject) => {
          const comment = h('textarea.ag-comment', { rows: 2, placeholder: 'What should be different? For example: “trim the reads first”, “use Bowtie 2”, “also give me a table of the variants”', 'aria-label': 'Changes to the plan' });
          const okBtn = h('button.btn.primary.small', { type: 'button' }, 'Approve the plan');
          const chBtn = h('button.btn.small', { type: 'button' }, 'Ask for changes');
          const box = h('div.ag-approve', comment, h('div.ag-approve-acts', okBtn, chBtn));
          main.appendChild(box);
          this.scroll('agent');
          const done = (choice) => {
            const c = comment.value.trim();
            if (choice === 'change' && !c) {
              comment.focus();
              return toast('Write what should change.', 'warn');
            }
            box.remove();
            main.appendChild(h('small.ag-note', choice === 'approve' ? 'You approved this plan.' : 'You asked for changes: ' + c));
            resolve({ choice, comment: c });
          };
          okBtn.addEventListener('click', () => done('approve'));
          chBtn.addEventListener('click', () => done('change'));
          signal.addEventListener('abort', () => reject(stopped()), { once: true });
        });
        bus.emit('agent:plan', { choice: d.choice, run: R.id, round: R.planRounds });
        hist.push({ role: 'assistant', content: text });
        if (d.choice === 'approve') {
          R.plan = text;
          MG.app.fs.writeText(run + '/PLAN.md', `# Plan of run ${R.id}\n\nWritten by the AI model (${R.models.join(', ')}) and approved by the user${R.planRounds > 1 ? ` after ${plural(R.planRounds - 1, 'round')} of changes` : ''}.\n\n${text.trim()}\n`);
          hist.push({ role: 'user', content: 'The user approved this plan. Carry it out now, one step per reply.' });
          return;
        }
        (R.planChanges = R.planChanges || []).push(d.comment);
        hist.push({ role: 'user', content: `The user asks you to change the plan: ${d.comment}\nSend the whole plan again, changed (no code blocks).` });
      }
    }
    /** approve each step: the student's decision on one step → { choice: run | all | refused, edited, bash, fileText, comment } */
    approve(main, P, signal) {
      return new Promise((resolve, reject) => {
        const box = h('div.ag-approve');
        let fta = null, ta = null;
        if (P.file) {
          box.appendChild(h('div.ag-approve-t', { html: `The agent wants to <b>write the file ${esc(P.file.name)}</b>:` }));
          fta = h('textarea.ag-edit', { rows: Math.min(14, P.file.text.split('\n').length), spellcheck: 'false', 'aria-label': 'Contents of the file' });
          fta.value = P.file.text;
          box.appendChild(fta);
        }
        if (P.bash != null) {
          box.appendChild(h('div.ag-approve-t', { html: P.file ? 'and then to <b>run</b>:' : 'The agent wants to <b>run</b>:' }));
          ta = h('textarea.ag-edit', { rows: Math.min(10, P.bash.split('\n').length), spellcheck: 'false', 'aria-label': 'The commands' });
          ta.value = P.bash;
          box.appendChild(ta);
        }
        const comment = h('input.ag-comment', { type: 'text', placeholder: 'A word for the agent (optional) – say why, if you refuse', 'aria-label': 'Comment for the agent' });
        const runBtn = h('button.btn.primary.small', { type: 'button' }, P.bash != null ? 'Run it' : 'Write it');
        const allBtn = h('button.btn.small', { type: 'button', title: 'Run this step, and all later steps of this run without asking' }, 'Run, and stop asking');
        const noBtn = h('button.btn.small.danger', { type: 'button' }, 'Refuse');
        box.append(comment, h('div.ag-approve-acts', runBtn, allBtn, noBtn, h('span.muted.small', 'You can change the text above before you run it.')));
        main.appendChild(box);
        this.scroll('agent');
        const done = (choice) => {
          const bash = ta ? ta.value.trim() : null, fileText = fta ? fta.value.replace(/\s+$/, '') + '\n' : null;
          const edited = choice !== 'refused' && ((ta && bash !== P.bash) || (fta && fileText !== P.file.text));
          if (choice !== 'refused' && ta && !bash) return toast('There is no command left to run – refuse the step instead.', 'warn');
          const c = comment.value.trim();
          box.remove();
          const told = { run: 'You allowed this step.', all: 'You allowed this step, and all later ones.', refused: 'You refused this step' + (c ? ': ' + c : '.') }[choice];
          main.appendChild(h('small.ag-note', edited ? 'You changed this step before it ran' + (choice === 'all' ? ', and allowed all later ones.' : '.') : told));
          resolve({ choice, edited, bash, fileText, comment: c });
        };
        runBtn.addEventListener('click', () => done('run'));
        allBtn.addEventListener('click', () => done('all'));
        noBtn.addEventListener('click', () => done('refused'));
        signal.addEventListener('abort', () => reject(stopped()), { once: true });
      });
    }
    /** write a file the agent asked for (inside its folder only) */
    agentWrite(run, file, step, main) {
      const fs = MG.app.fs;
      const path = fs.resolve(file.name, run);
      const row = h('div.ag-file', { html: MG.icon('text') });
      const fail = (why) => {
        step.file = { name: file.name, bytes: 0, skipped: why };
        row.append(h('code', file.name), h('small.muted', ' not written: ' + why));
        main.appendChild(row);
        return { ok: false, text: `The file ${file.name} was NOT written: ${why}\n` };
      };
      if (!/^[A-Za-z0-9._+=@,\/-]+$/.test(file.name) || /(^|\/)\.\.?(\/|$)/.test(file.name)) return fail('use a plain name in your folder (letters, digits and . _ - /).');
      if (!inside(path, run) || path === run) return fail('it is outside your folder.');
      for (let d = MG.path.dirname(path); inside(d, run) && d !== run; d = MG.path.dirname(d)) {
        if (fs.entries.has(d) && fs.entries.get(d).kind !== 'dir') return fail(`${fs.pretty(d).slice(fs.pretty(run).length + 1)} is a file, not a folder.`);
      }
      const e = fs.get(path);
      if (e && (e.kind === 'dir' || e.readonly || e.protected)) return fail(e.kind === 'dir' ? 'that is a folder.' : 'that file is read-only.');
      if (inside(path, run + '/data') && INPUTS().includes(path.split('/').pop())) return fail('the input files are read-only.');
      fs.mkdirp(MG.path.dirname(path));
      fs.writeText(path, file.text, e && e.mode ? { mode: e.mode } : {});
      const lines = file.text.split('\n').length - 1;
      step.file = { name: fs.pretty(path).slice(fs.pretty(run).length + 1), bytes: new Blob([file.text]).size, lines, text: file.text, replaced: !!e };
      const open = h('button.btn.small', { type: 'button' }, 'Open');
      open.addEventListener('click', () => MG.app.editFile(path, {}));
      row.append(h('span', e ? 'rewrote ' : 'wrote '), h('code', step.file.name), h('small.muted', ` ${plural(lines, 'line')}`), open);
      main.appendChild(row);
      this.scroll('agent');
      return { ok: true, text: `The file ${step.file.name} was written (${plural(lines, 'line')}).\n` };
    }
    /** run the commands of one step, one after the other, until one fails */
    async agentRun(run, bashText, step, main, signal, deny) {
      const fs = MG.app.fs, T = MG.app.term;
      let cmds;
      const refuse = (why, cls) => {
        step.commands.push({ cmd: bashText, code: null, secs: 0, output: '', skipped: why });
        main.append(h('div.ag-cmd.bad', h('code', bashText)), h('small.ag-note' + (cls || ''), 'not run: ' + why));
        return { ok: false, text: `Not run: ${why}\n` };
      };
      if (deny) return refuse(deny);
      try {
        cmds = MG.shellLang.statements(bashText, { extglob: MG.shellLang.extglobOn(T.shell._top()) });
      } catch (e) {
        return refuse('bash: ' + e.message);
      }
      if (!cmds.length) return refuse('the code block was empty.');
      let text = '', ok = true;
      // a step starts in the run's folder; a cd in it lasts until the end of the step
      let cwd = run;
      const where = (dir) => (dir === run ? '' : inside(dir, run) ? dir.slice(run.length + 1) + '/' : fs.pretty(dir));
      for (let k = 0; k < cmds.length; k++) {
        const cmd = cmds[k];
        const row = h('div.ag-cmd.run', h('code', cmd));
        main.appendChild(row);
        this.scroll('agent');
        const saved = new Map(); // path → the entry the student saved in the editor while this command ran
        const off = bus.on('editor:save', (d) => fs.entries.has(d.path) && saved.set(d.path, fs.entries.get(d.path)));
        let r, t0 = performance.now(), undo = { changed: [], lost: [], killed: false, gone: [] };
        T.shell.exitTyped = false;
        T.shell.endedBy = null;
        const ranIn = where(cwd);
        const marks = folderMarks(fs, run), shellWas = shellMark(T.shell), shadow = this._shadow || { e: 0, u: [] };
        const putBack = (MG.wasm && MG.wasm.deniedN) || 0; // changes of programs to the course data that the page undid, so far
        shadow.e = 0;
        shadow.u = [];
        MG.hereLog = []; // (what this terminal turned out not to have: see notHere in shell.js)
        // (had the run begun with set -eu, would -e and -u be on at this point? The agent's own set commands decide.
        // And are they on in earnest – did the agent switch them on itself?)
        const F0 = T.shell._top().flags, opt0 = [!!F0.se, !!F0.su, !!F0.e, !!F0.u];
        const strict = opt0[0];
        let idle;
        MG.app.agentBusy = new Promise((res) => (idle = res));
        MG.app.agentRoot = run;
        try {
          // The state of the files before the command: program output is written to the browser's storage now
          // (if the command has to be stopped by force, that is where it comes back from), and nothing more is
          // written there until what the command changed outside the folder has been put back.
          if (MG.project && MG.project.flush) await MG.project.flush(fs);
          if (MG.project && MG.project.pause) MG.project.pause();
          const snap = outsideSnapshot(fs, run);
          const gen = MG.wasm ? MG.wasm.gen : 0, since = Date.now();
          try {
            try {
              if (MG.wasm && MG.wasm.keep) await MG.wasm.keep(snap);
            } catch (e) {
              console.error(e); // without the copies, only files that the command leaves alone can be put back
            }
            t0 = performance.now();
            if (fs.cwd !== cwd) fs.cwd = cwd;
            T._renderPrompt();
            r = await this.termRun(cmd, commandTimeout());
          } finally {
            try {
              // what a command changed outside the agent's folder is put back
              undo = await undoOutside(fs, run, snap, saved, gen, since);
            } finally {
              if (MG.project && MG.project.resume) MG.project.resume(fs);
            }
          }
        } finally {
          off();
          MG.app.agentBusy = null;
          MG.app.agentRoot = null;
          idle();
        }
        // what the student did meanwhile, and which waited for the end of this command, gets its turn before the next one
        if (MG.app.agentWaiting) await sleep(0);
        const secs = Math.round((performance.now() - t0) / 100) / 10;
        const undone = undo.changed, lost = undo.lost, gone = undo.gone || [];
        // the paths outside its folder that the command used (whether or not it changed anything there)
        const reached = reachedOutside(T.touched, run).map((x) => fs.pretty(x));
        // "exit" at the top of a command: in a script it would end the script. Here it ends the block of commands.
        // The same for what else ends a script: the agent's own set -e or set -u, ${NAME:?}, exec.
        const ended = T.shell.exitTyped ? 'exit' : T.shell.endedBy || null;
        const exited = !!T.shell.exitTyped || ended === 'exec';
        T.shell.exitTyped = false;
        const F1 = T.shell._top().flags, opt1 = [!!F1.se, !!F1.su];
        if (!fs.isDir(run)) fs.mkdirp(run);
        cwd = fs.isDir(fs.cwd) ? fs.cwd : run;
        if (cwd !== run) step.cd = true;
        T._renderPrompt();
        const out = r.text.replace(/\s+$/, '');
        const bad = r.code !== 0 || undone.length > 0;
        // what the script made from this run has to know (see makeScript): a command inside this one failed where
        // set -e ends a script; names without a value were used; and, of a command that did not end with 0, was
        // undone or was ended where a script ends, what it left in the folder (and in /tmp) and whether it changed
        // the shell (a variable, a function, an option)
        const inner = r.code === 0 && shadow.e > 0;
        const unset = shadow.u.slice(0, 8);
        // (a program tried to change the course data, and the page put the file back)
        const tried = ((MG.wasm && MG.wasm.deniedN) || 0) > putBack;
        // (the command failed for want of something that this terminal does not have)
        const here = (MG.hereLog || []).slice(0, 4);
        const left = bad || tried || ended ? marksChanged(marks, folderMarks(fs, run), run) : { wrote: [], removed: [] };
        const wrote = left.wrote, removed = left.removed;
        const state = r.code !== 0 || ended ? markDiff(shellWas, shellMark(T.shell)).slice(0, 8) : [];
        row.classList.remove('run');
        row.classList.toggle('bad', bad);
        const L = out.split('\n');
        row.appendChild(h('details.ag-out', h('summary', `exit status ${r.code} · ${took(secs)}${out ? ' · ' + plural(L.length, 'line') + ' printed' : ' · nothing printed'}`), h('pre', (L.length > 40 ? ['…'].concat(L.slice(-40)) : L).join('\n') || '(nothing)')));
        if (undone.length) row.appendChild(h('small.ag-note', 'Changes outside its folder were undone: ' + undone.slice(0, 4).map((x) => fs.pretty(x)).join(', ') + (undone.length > 4 ? ' …' : '')));
        if (lost.length) row.appendChild(h('small.ag-note.bad', 'Lost with the programs that were stopped: ' + lost.slice(0, 4).map((x) => fs.pretty(x)).join(', ') + (lost.length > 4 ? ' …' : '') + ' – make ' + (lost.length === 1 ? 'it' : 'them') + ' again.'));
        if (r.timedOut) row.appendChild(h('small.ag-note', `Stopped by the page after ${Math.round(commandTimeout() / 1000)} s.`));
        const goneNames = gone.map((x) => x.slice(run.length + 1));
        if (undo.killed) row.appendChild(h('small.ag-note', 'The programs had to be started afresh: what programs wrote during this command is gone' + (goneNames.length ? ' (' + goneNames.slice(0, 4).join(', ') + (goneNames.length > 4 ? ' …' : '') + ')' : '') + '. Their earlier files are back as they were before the command – unless the command had written text in their place.'));
        step.commands.push({ cmd, code: r.code, secs, output: out.slice(-4000), cut: out.length > 4000, undone: undone.map((x) => fs.pretty(x)), lost: lost.length ? lost.map((x) => fs.pretty(x)) : undefined, timedOut: r.timedOut, restarted: undo.killed || undefined, gone: goneNames.length ? goneNames : undefined, cwd: ranIn || undefined, after: where(cwd), outside: reached.length ? reached.slice(0, 8) : undefined, exited: exited || undefined, inner: inner || undefined, unset: unset.length ? unset : undefined, wrote: wrote.length ? wrote.slice(0, 12) : undefined, removed: removed.length ? removed.slice(0, 12) : undefined, state: state.length ? state : undefined, tried: tried || undefined, ended: ended || undefined, here: here.length ? here : undefined, sh: opt0.concat(opt1).map((x) => (x ? 1 : 0)).join(''), loose: strict ? undefined : true });
        text += `$ ${cmd}\n[exit status ${r.code}, ${took(secs)}${ranIn ? ', in ' + ranIn : ''}]${r.timedOut ? ' [stopped: it ran for too long]' : ''}${undo.killed ? ` [the programs had to be restarted: what programs wrote during this command is gone${goneNames.length ? ' (' + goneNames.slice(0, 6).join(', ') + ')' : ''}]` : ''}${undone.length ? ` [your changes outside your folder were undone: ${undone.slice(0, 6).map((x) => fs.pretty(x)).join(', ')}]` : ''}\n${shown(out) || '(no output)'}\n`;
        this.scroll('agent');
        if (bad) {
          ok = false;
          const rest = cmds.slice(k + 1);
          if (rest.length) {
            text += `[not run, because the command before failed: ${rest.join(' ; ')}]\n`;
            rest.forEach((c) => {
              step.commands.push({ cmd: c, code: null, secs: 0, output: '', skipped: 'the command before it failed' });
              main.appendChild(h('div.ag-cmd.skip', h('code', c), h('small.muted', ' not run')));
            });
          }
          break;
        }
        if (exited) {
          const rest = cmds.slice(k + 1);
          if (rest.length) {
            const by = ended === 'exec' ? 'exec' : 'exit';
            text += `[${by} ended this block of commands; not run: ${rest.join(' ; ')}]\n`;
            rest.forEach((c) => {
              step.commands.push({ cmd: c, code: null, secs: 0, output: '', skipped: by + ' ended the block' });
              main.appendChild(h('div.ag-cmd.skip', h('code', c), h('small.muted', ` not run: ${by} ended the block`)));
            });
          }
          break;
        }
        if (signal.aborted) throw stopped();
      }
      if (fs.cwd !== run) {
        fs.cwd = run;
        T._renderPrompt();
        if (ok) text += '(The next step starts in your folder again.)\n';
      }
      return { ok, text };
    }

    /* ---------------- the record of a run ---------------- */
    /** which of the terminal's programs a run used, with their versions */
    programsUsed(R) {
      const v = V();
      const of = { fastp: v.fastp, minimap2: v.minimap2, bowtie2: v.bowtie2, 'bowtie2-build': v.bowtie2, samtools: v.samtools, bcftools: v.bcftools, bgzip: v.htslib, tabix: v.htslib, gzip: v.htslib, gunzip: v.htslib, zcat: v.htslib, seqtk: v.seqtk, bedtools: v.bedtools, jq: v.jq, awk: v.gawk, gawk: v.gawk, grep: v.grep, egrep: v.grep, sed: v.sed };
      const pkg = { bgzip: 'htslib', tabix: 'htslib', gzip: 'bgzip of htslib', gunzip: 'bgzip of htslib', zcat: 'bgzip of htslib', awk: 'gawk', egrep: 'grep' };
      const core = ['cat', 'head', 'tail', 'wc', 'sort', 'uniq', 'cut', 'tr', 'tee', 'paste', 'join', 'comm', 'seq', 'fold', 'shuf', 'md5sum', 'date'];
      const seen = new Set();
      const scan = (text) => {
        try {
          MG.shellLang.commandNames(text).forEach((x) => seen.add(x));
        } catch (e) {
          /* not shell text */
        }
      };
      R.steps.forEach((s) => {
        s.commands.forEach((c) => !c.skipped && scan(c.cmd));
        if (s.file && s.file.text && /\.(sh|bash)$/.test(s.file.name)) scan(s.file.text);
      });
      const out = [];
      Object.keys(of).forEach((k) => seen.has(k) && out.push({ program: k, version: of[k], note: pkg[k] || '' }));
      const usedCore = core.filter((k) => seen.has(k));
      if (usedCore.length) out.push({ program: usedCore.join(', '), version: v.coreutils, note: 'GNU coreutils' });
      return out;
    }
    async filesOf(run) {
      const fs = MG.app.fs;
      const inputs = [], outputs = [];
      const paths = Array.from(fs.entries.keys()).filter((k) => k.startsWith(run + '/') && fs.entries.get(k).kind !== 'dir').sort();
      for (const p of paths) {
        const rel = p.slice(run.length + 1);
        if (rel === 'RUN.md' || rel === 'run.json') continue;
        let md5 = '';
        try {
          md5 = MG.md5(await fs.readBytes(p));
        } catch (e) {
          md5 = '(could not be read)';
        }
        const item = { path: rel, bytes: fs.size(fs.entries.get(p)), md5 };
        if (rel.startsWith('data/') && INPUTS().includes(rel.slice(5))) inputs.push(item);
        else outputs.push(item);
      }
      return { inputs, outputs };
    }
    async record(R, run) {
      const fs = MG.app.fs;
      if (!fs.isDir(run)) fs.mkdirp(run);
      R.programs = this.programsUsed(R);
      Object.assign(R, await this.filesOf(run));
      R.record = { writtenBy: 'the page (assets/js/assistant.js), not the AI model', page: document.title, browser: navigator.userAgent };
      const outcome = { done: 'finished: the agent sent its report', limit: `stopped at the limit of ${MAX_STEPS} steps`, stopped: 'stopped by the user', error: 'ended with an error of the AI service' }[R.outcome];
      const ran = R.steps.reduce((a, s) => a + s.commands.filter((c) => !c.skipped).length, 0);
      const failed = R.steps.reduce((a, s) => a + s.commands.filter((c) => c.code).length, 0);
      const fence = (t) => '```text\n' + String(t).replace(/```/g, "'''") + '\n```';
      const quote = (t) => String(t).trim().split('\n').map((l) => '> ' + l).join('\n');
      const md = [
        `# Run ${R.id}: an AI agent, ${MODES[R.mode].label.toLowerCase()}`,
        '',
        'This record was written by the page from what really happened – not by the AI model.',
        '',
        '| | |',
        '|---|---|',
        `| Way of working | ${MODES[R.mode].label}: ${MODES[R.mode].does} |`,
        `| Model | ${R.models.join(', ') || modelOf(this.settings)} (${R.service}), ${plural(R.requests, 'request')} |`,
        `| Started | ${clock(new Date(R.started))} (local time) |`,
        `| Took | ${took(R.seconds)} |`,
        `| Outcome | ${outcome} |`,
        `| Steps | ${R.steps.length}; ${plural(ran, 'command')} run${failed ? `, ${failed} of them failed` : ''} |`,
        `| Folder | ${R.folder} |`,
        '',
        '## The task, as it was given',
        '',
        quote(R.task),
        ''
      ];
      if (R.plan) {
        md.push('## The plan', '', R.planRounds > 1 ? `The agent wrote a plan; the user asked for changes ${R.planRounds - 1} time${R.planRounds > 2 ? 's' : ''} (${(R.planChanges || []).map((c) => '“' + c + '”').join('; ')}) and approved this version:` : 'The agent wrote this plan, and the user approved it:', '', quote(R.plan), '');
      }
      md.push('## What the agent did', '');
      if (!R.steps.length) md.push('Nothing was run.', '');
      R.steps.forEach((s) => {
        md.push(`### Step ${s.n}`, '');
        if (s.say) md.push('The agent: ' + s.say.replace(/\n+/g, ' '), '');
        if (s.note) md.push(s.note, '');
        if (s.approval) md.push((s.edited ? 'The user changed this step before it ran' + (s.approval === 'all' ? ', and allowed all later steps without asking.' : '.') : { run: 'The user allowed this step.', all: 'The user allowed this step, and all later steps without asking.', refused: 'The user refused this step.' }[s.approval]) + (s.comment ? ` Comment: “${s.comment}”` : ''), '');
        if (s.edited && s.edited.bash != null) md.push('What the agent had proposed:', '', '```bash\n' + s.edited.bash + '\n```', '', 'What ran:', '');
        if (s.file) md.push(s.file.skipped ? `File ${s.file.name}: not written (${s.file.skipped})` : `Wrote the file \`${s.file.name}\` (${plural(s.file.lines, 'line')}).`, '');
        s.commands.forEach((c) => {
          md.push('```bash\n' + c.cmd + '\n```');
          if (c.skipped) md.push(`Not run: ${c.skipped}`, '');
          else {
            md.push(`exit status ${c.code} · ${took(c.secs)}${c.cwd ? ' · in ' + c.cwd : ''}${c.timedOut ? ' · stopped by the page: it ran for too long' : ''}${c.undone && c.undone.length ? ' · changes outside the folder were undone: ' + c.undone.join(', ') : ''}${c.outside && c.outside.length && !(c.undone && c.undone.length) ? ' · it used paths outside the folder: ' + c.outside.join(', ') : ''}${c.restarted ? ' · the programs were started afresh: what they wrote during this command is gone' + (c.gone && c.gone.length ? ' (' + c.gone.join(', ') + ')' : '') + '; their earlier files are as they were before it, unless the command had written text in their place' : ''}${c.lost && c.lost.length ? ' · lost when the programs were stopped: ' + c.lost.join(', ') : ''}`, '');
            if (c.output) {
              const L = c.output.split('\n');
              md.push((c.cut || L.length > 30 ? 'The end of what it printed:' : 'It printed:'), '', fence((L.length > 30 ? L.slice(-30) : L).join('\n')), '');
            }
          }
        });
        if (s.early) md.push('In the same reply – that is, before this step had run – the agent wrote a report. The page did not take it as the report, and told the agent so. What the agent had written:', '', quote(s.early), '');
      });
      md.push('## The agent’s report', '', R.report ? quote(R.report) : R.outcome === 'error' ? `There is no report: the AI service returned an error (${R.error}).` : R.outcome === 'stopped' ? 'There is no report: the run was stopped.' : 'There is no report: the last reply of the model was empty.', '');
      md.push('## Programs', '', R.programs.length ? R.programs.map((p) => `- ${p.program} ${p.version}${p.note ? ' (' + p.note + ')' : ''}`).join('\n') : 'None of the versioned programs was run.', '', 'All of them are WebAssembly builds that ran in the web browser, on one thread.', '');
      const table = (items) => (items.length ? ['| File | Bytes | MD5 |', '|---|---:|---|'].concat(items.map((f) => `| ${f.path} | ${f.bytes} | ${f.md5} |`)).join('\n') : 'None.');
      md.push('## Files', '', '### Inputs', '', table(R.inputs), '', '### Made in this run (as they were when the run ended)', '', table(R.outputs), '');
      fs.writeText(run + '/RUN.md', md.join('\n'));
      fs.writeText(run + '/run.json', JSON.stringify(R, null, 1) + '\n');
    }
    /** the end of a run: the report and what can be done with the run */
    finishCard(ui, R, run) {
      const fs = MG.app.fs;
      ui.card.classList.remove('live');
      ui.card.classList.toggle('err', R.outcome === 'error');
      ui.head.querySelector('b').textContent = `Run ${R.id} · ${MODES[R.mode].label.toLowerCase()} · ${{ done: 'finished', limit: 'stopped at its limit', stopped: 'stopped', error: 'error' }[R.outcome]}`;
      const body = h('div.ai-body.ag-report');
      ui.card.appendChild(body);
      this.fill(body, R.outcome === 'error' ? '**The AI service returned an error.**\n\n' + R.error : R.report || (R.outcome === 'stopped' ? '*(Stopped – there is no report.)*' : '*(The model’s last reply was empty: there is no report. What it did is in the record.)*'), { plain: true });
      const ran = R.steps.reduce((a, s) => a + s.commands.filter((c) => !c.skipped).length, 0);
      ui.card.appendChild(h('div.ai-badge', `${R.models.join(', ') || modelOf(this.settings)} · ${plural(R.steps.length, 'step')} · ${plural(ran, 'command')} · ${took(R.seconds)}`));
      const own = R.mode === 'script' ? scriptOf(fs, run) : null;
      if (R.mode === 'script' && !own) ui.card.appendChild(h('small.ag-note', 'The agent did not write the script it was asked for (analysis.sh). “Make a script from this run” writes one, rerun.sh, from the commands that it ran.'));
      else if (own && own !== run + '/analysis.sh') ui.card.appendChild(h('small.ag-note', `The agent’s script is ${own.slice(run.length + 1)} – not in the run’s folder itself, where the instructions look for it.`));
      ui.card.appendChild(this.runActions(R.id, run, R.mode));
      if (fs.exists(run + '/RUN.md')) fs.entries.get(run + '/RUN.md').fresh = true;
    }
    /** the buttons of a run. cut: a run without a record (it was interrupted) – no script can be made from it */
    runActions(id, run, mode, cut) {
      const fs = MG.app.fs;
      const btn = (icon, label, title, fn) => {
        const b = h('button.btn.small', { type: 'button', title, html: MG.icon(icon) + '<span>' + esc(label) + '</span>' });
        b.addEventListener('click', async () => {
          try {
            await fn();
          } catch (e) {
            if (!e || !e.user) console.error(e); // (an answer to the person, not a fault of the page: no script can be made from this run, say)
            toast(esc((e && e.message) || String(e)), 'error');
          }
        });
        return b;
      };
      const acts = h('div.ag-acts');
      acts.appendChild(btn('book', cut ? 'The note (RUN.md)' : 'The record (RUN.md)', cut ? 'Why this run has no record' : 'What was asked, every command and the end of what it printed, the files and their checksums', () => MG.app.editFile(run + '/RUN.md', {})));
      acts.appendChild(btn('terminal', 'Go to its folder', `cd ${fs.pretty(run)} in the terminal`, async () => {
        MG.app.showWorkbench('terminal');
        await MG.app.term.type('cd ' + fs.pretty(run) + ' && ls -l', false);
      }));
      // (a "Write a script" run has its own script, analysis.sh – unless the agent did not write one)
      if (!cut && (mode !== 'script' || !scriptOf(fs, run))) acts.appendChild(btn('code', 'Make a script from this run', 'Write rerun.sh: the commands of this run that worked, in order', () => this.makeScript(id, run)));
      acts.appendChild(btn('download', 'Download the folder', 'A .zip of the run’s folder: data, results, record', () => MG.project.download(run, `run-${id}-${MODES[mode].word}.zip`, {})));
      return acts;
    }
    /** earlier runs (after the page was loaded again) */
    pastRuns() {
      const fs = MG.app.fs;
      const list = this.runs.filter((r) => fs.isDir(fs.resolve(r.folder)));
      // A run that was under way when the page was closed or loaded again: its folder is there, but the record is
      // written when a run ends. The folder gets a note that says so.
      const cut = [];
      const words = Object.keys(MODES).map((k) => MODES[k].word);
      const top = HOME() + '/runs';
      if (fs.isDir(top)) {
        for (const c of fs.list(top)) {
          const m = /^(\d+)-([a-z]+)$/.exec(c.name);
          if (!m || !words.includes(m[2]) || c.entry.kind !== 'dir' || !fs.isDir(c.path + '/data') || this.runs.some((r) => fs.resolve(r.folder) === c.path)) continue;
          const mode = Object.keys(MODES).find((k) => MODES[k].word === m[2]);
          const rec = fs.get(c.path + '/run.json');
          if (rec) {
            // the run had ended and its record was written, but the list of runs was not saved any more: the record says what it was
            try {
              const R = JSON.parse(rec.text);
              const ran = (R.steps || []).reduce((a, st) => a + st.commands.filter((x) => !x.skipped).length, 0);
              const item = { id: +m[1], mode, outcome: R.outcome || 'done', folder: fs.pretty(c.path), task: String(R.task || '').slice(0, 200), started: R.started, steps: (R.steps || []).length, commands: ran, model: (R.models || []).join(', ') };
              this.runs.push(item);
              list.push(item);
              store.set('ai:runs', this.runs);
            } catch (e) {
              /* not a record that can be read: the folder is left as it is */
            }
            continue;
          }
          try {
            if (!fs.exists(c.path + '/RUN.md')) fs.writeText(c.path + '/RUN.md', `# Run ${m[1]}: an AI agent, ${MODES[mode].label.toLowerCase()} – interrupted\n\nThe page was closed or loaded again while this run was under way. The record of a run is written when the run ends, so there is none for this one: what the agent was asked, which commands it ran and what they printed is not known any more. The files in this folder are what it had made up to then.\n\nGive the agent the task again to get a run with a record.\n`);
          } catch (e) {
            continue;
          }
          cut.push({ id: +m[1], mode, path: c.path });
        }
      }
      if (!list.length && !cut.length) return;
      const card = h('div.ai-msg.assistant.ag.past');
      card.appendChild(h('div.ag-head', { html: MG.icon('history') + '<b>Earlier runs</b>' }));
      // in the order of their numbers, whether they have a record or not
      list.map((r) => ({ id: r.id, run: r })).concat(cut.map((r) => ({ id: r.id, cut: r }))).sort((a, b) => a.id - b.id).forEach((x) => {
        if (x.run) {
          const r = x.run;
          const row = h('div.ag-pastrow', h('b', `Run ${r.id} · ${MODES[r.mode] ? MODES[r.mode].label.toLowerCase() : r.mode}`), h('span.muted', ` · ${{ done: 'finished', limit: 'stopped at its limit', stopped: 'stopped', error: 'error' }[r.outcome] || r.outcome} · ${plural(r.commands, 'command')} · ${r.folder}`));
          card.append(row, this.runActions(r.id, fs.resolve(r.folder), r.mode));
        } else {
          const r = x.cut;
          const row = h('div.ag-pastrow', h('b', `Run ${r.id} · ${MODES[r.mode].label.toLowerCase()}`), h('span.muted', ` · interrupted: the page was closed or loaded again while it ran, so there is no record of it · ${fs.pretty(r.path)}`));
          card.append(row, this.runActions(r.id, r.path, r.mode, true));
        }
      });
      this.threads.agent.appendChild(card);
    }
    /** rerun.sh: the commands of a run that worked, in the order they ran (written by the page).
        The script is meant to run in another folder than the agent did. So:
        - where a command named the run's folder in full, the script has "$RUN_FOLDER" – the folder it runs in;
        - where the agent changed folder (cd), the script goes back to "$RUN_FOLDER" at the end of the step, as the
          agent's next step started there again;
        - a command that reaches outside the run's folder is left out, as a comment. Three checks find those: what
          the page had to put back after the command (the record's "undone"), which paths the shell worked out
          while it ran ("outside"), and a reading of the command's text (MG.shellLang.reach). */
    async makeScript(id, run) {
      const fs = MG.app.fs;
      let R;
      try {
        R = JSON.parse(await fs.readText(run + '/run.json'));
      } catch (e) {
        throw Object.assign(new Error(`The record ${fs.pretty(run)}/run.json could not be read.`), { user: true });
      }
      // the variable that stands for the run's folder: a name that the run itself does not use
      let TOP = 'RUN_FOLDER';
      const everything = JSON.stringify(R.steps || []);
      while (new RegExp('\\b' + TOP + '\\b').test(everything)) TOP += '_';
      const L = [
        '#!/usr/bin/env bash',
        `# rerun.sh – the commands of run ${R.id} that worked, in the order the AI agent ran them.`,
        '# Written by the page from the record of the run (run.json), not by the AI model.',
        '#',
        `#   Task:     ${R.task.replace(/\s+/g, ' ').slice(0, 300)}`,
        `#   Agent:    ${(R.models || []).join(', ')} (${R.service}), ${MODES[R.mode] ? MODES[R.mode].label.toLowerCase() : R.mode}, ${clock(new Date(R.started))}`,
        `#   Programs: ${(R.programs || []).map((p) => `${p.program} ${p.version}`).join('; ') || '-'}`,
        '#',
        '# Run it in a folder that holds data/ (the two FASTQ files and reference.fa):  bash rerun.sh',
        '# Tidy it first: take out the commands that only looked at things, and say in comments what each step is for.',
        '# Read it before you run it. In the agent\'s run the page put back whatever a command changed outside the',
        '# run\'s folder; when you run a script, nothing is put back.',
        '#',
        '# The script stops at the first command that fails (-e) and at a variable that was never set (-u).',
        '# As in the agent\'s run, a pipeline counts as failed only if its last command fails (no "-o pipefail").',
        'set -eu',
        ''
      ];
      let n = 0, leftOut = 0, eased = 0;
      let usesTop = false; // does the script need the variable: in a command, in a file it writes, to go back to its folder
      const eof = (text) => {
        let tag = 'END_OF_FILE';
        while (text.split('\n').includes(tag)) tag += '_';
        return tag;
      };
      // a file name as a word of the shell: quoted unless it is plain
      const shq = (w) => (/^[A-Za-z0-9._+=@,/-]+$/.test(w) ? w : "'" + String(w).replace(/'/g, "'\\''") + "'");
      // a folder of the run, written from the run's folder ('' is the folder itself, 'work/'), as the script names it
      const inTop = (rel) => `"$${TOP}"` + (rel.replace(/\/+$/, '') ? '/' + shq(rel.replace(/\/+$/, '')) : '');
      const place = { abs: run, home: fs.home };
      // from one folder of the run to a file in it, both written from the run's folder
      const fromTo = (from, to) => {
        const A = from.split('/').filter(Boolean), B = to.split('/').filter(Boolean);
        let i = 0;
        while (i < A.length && i < B.length && A[i] === B[i]) i++;
        return Array(A.length - i).fill('..').concat(B.slice(i)).join('/') || '.';
      };
      // the files that a command runs as scripts (bash NAME, source NAME, ./NAME, "$RUN_FOLDER"/NAME), written from the
      // run's folder. start: the folder the command started in ('' or 'work/'; null: a folder outside)
      const scriptsOf = (text, start, unknown) => {
        const names = [];
        for (let w of MG.shellLang.scriptsRun(text)) {
          let name = null;
          w = w.replace(/^(\$PWD|\$\{PWD\})\//, ''); // $PWD/x: a file in the folder the command is in
          if (w.startsWith('$' + TOP + '/')) name = w.slice(TOP.length + 2);
          else if (/[$`*?[{]/.test(w)) {
            // bash "$s", for s in scripts/*.sh …: which file runs is only known when the command runs
            if (unknown && !/^\//.test(w)) unknown.push(w);
          } else if (!/^[~/]/.test(w) && start != null) name = start + w;
          if (name == null) continue;
          name = MG.path.norm('/' + name).slice(1);
          if (name) names.push(name);
        }
        return names;
      };
      const startOf = (c) => (/^[~/]/.test(c.cwd || '') ? null : c.cwd || '');
      const ranAsScript = new Set();
      R.steps.forEach((s) => s.commands.forEach((c) => !c.skipped && scriptsOf(MG.shellLang.anchor(c.cmd, place, TOP).text, startOf(c)).forEach((x) => ranAsScript.add(x))));
      // … as a command that starts in the folder `start` would name them
      const scriptsFrom = (start) => new Set(Array.from(ranAsScript).flatMap((x) => [x, fromTo(start, x)]));
      // the files the agent wrote that reach outside the folder, as the run goes on: name → what leads out
      const reaching = new Map();
      // (a script that ran after a cd in the same command is known by its name alone)
      const reachingAs = (name) => (reaching.has(name) ? name : Array.from(reaching.keys()).find((k) => k.split('/').pop() === name.split('/').pop()));
      const asComment = (cmd) => cmd.replace(/\n/g, '\n#   ');
      // the functions that the run defines (in commands and in the files it wrote): their names are no programs
      const funcs = new Set();
      everything.replace(/(?:function\s+([A-Za-z_][\w-]*))|(?:(?:^|[\s;&|("]|\\n)([A-Za-z_][\w-]*)\s*\(\)\s*(?:\{|\\n))/g, (m, a, b) => funcs.add(a || b));
      // the programs a command calls that this terminal does not have (bwa … || echo "not here"): on a computer that
      // has them the command does more than it did in the run
      const notHere = (text) => {
        let names = [];
        try {
          names = MG.shellLang.commandNames(text);
        } catch (e) {
          /* not readable */
        }
        return Array.from(new Set(names.filter((x) => /^[A-Za-z0-9_.+-]+$/.test(x) && !MG.shellBuiltins[x] && !MG.shellTools[x] && !funcs.has(x))));
      };
      const why = (list) => (list[0] === '?' ? 'the page could not read it' : list.slice(0, 4).join(', '));
      R.steps.forEach((s) => {
        const lines = [];
        if (s.file && !s.file.skipped && s.file.text != null) {
          const isScript = /\.(sh|bash)$/.test(s.file.name) || /^#!/.test(s.file.text) || ranAsScript.has(s.file.name);
          // (a script in a folder of its own is mostly run there: how far ".." leads from it is left to the other checks.
          // Where it names the run's folder in full, that is the folder the script runs in: see below.)
          const out = isScript ? outsideWords(MG.shellLang.anchor(s.file.text, place, TOP).text, s.file.name.includes('/') ? null : 0, ranAsScript, '$' + TOP) : [];
          if (out.length) reaching.set(s.file.name, out);
          else reaching.delete(s.file.name);
          if (out.length) lines.push(out[0] === '?' ? '# CHECK: the page could not read this file as a shell script – read it before you run the script.' : `# CHECK: this file reaches outside the folder (${why(out)}) – read it before you run the script.`);
          if (s.file.name.includes('/')) lines.push(`mkdir -p ${shq(MG.path.dirname('/' + s.file.name).slice(1))}`);
          // A file that names the run's folder in full – a list of samples, a configuration, a script – would make the
          // re-run work in the agent's folder. It is written with $RUN_FOLDER in its place: by a here-document that
          // is expanded, in which every other $, ` and \ of the file has a backslash.
          const T = MG.shellLang.anchorText(s.file.text, place, TOP, isScript);
          if (T.n) {
            usesTop = true;
            const tag = eof(T.text);
            lines.push(`# (this file names the run's folder: it is written with $${TOP}, the folder the script runs in – so every other $, \` and \\ in it has a backslash here)`);
            lines.push(`cat > ${shq(s.file.name)} <<${tag}`, T.text.replace(/\n$/, ''), tag);
          } else {
            const tag = eof(s.file.text);
            lines.push(`cat > ${shq(s.file.name)} <<'${tag}'`, s.file.text.replace(/\n$/, ''), tag);
          }
          n++;
        }
        const cmds = [];
        const closers = new Set(), asks = new Set(); // places in cmds: a "set -e" of the page; a command that reads $? or PIPESTATUS
        let worked = 0;
        // the folder the script is in at this point of the step, written from its own folder: '' is that folder,
        // 'work/' one below it, '~/data' one outside, null: not known
        let at = '';
        s.commands.forEach((c, i) => {
          const start = c.cwd || ''; // where the command started in the run
          // … in a folder outside? In the course data and in /tmp a command may run: nothing of the student's is there
          const away = /^[~/]/.test(start), outsideStart = away && !/^(~\/data|\/tmp)(\/[\w.+-]+)*\/?$/.test(start);
          // What the script's -e and -u are before and after this command (the script begins with set -eu and holds the
          // agent's own set commands), and whether the agent had switched them on itself (then they were at work in
          // the run): se0 su0 re0 ru0 se1 su1. (A record of an earlier version has only "loose".)
          const sh = typeof c.sh === 'string' && c.sh.length === 6 ? c.sh.split('').map((x) => x === '1') : null;
          const se0 = sh ? sh[0] : !c.loose, su0 = sh ? sh[1] : !c.loose, re0 = sh ? sh[2] : false, ru0 = sh ? sh[3] : false, se1 = sh ? sh[4] : se0, su1 = sh ? sh[5] : su0;
          const wrote = c.wrote || [], removed = c.removed || [];
          // (what the command changed in the shell: names; a record of an earlier version says only that it did)
          const changed = Array.isArray(c.state) ? c.state : c.state ? ['a variable or a setting of the shell'] : [];
          const left = wrote.length > 0 || removed.length > 0 || changed.length > 0;
          // what ended the command where a script would end – exit, the agent's own set -e or set -u, ${NAME:?}, exec
          const ended = c.ended || (c.exited ? 'exit' : null);
          // A command that did not end with 0 but left something behind – a file, a variable – belongs to what the run
          // did (diff a b > d has status 1 when the files differ): the commands after it may build on that.
          // Not one that tried to change the course data (the page put it back). And not one that failed for want of
          // something this terminal does not have – python3 … > answer.txt, a plugin of bcftools –: on a computer
          // that has it the command works, and does more than it did in the run.
          const triedInput = !c.skipped && (!!c.tried || (!sh && /is read-only \((an input of this run|the course data)\): the change to it was undone/.test(c.output || '')));
          const hereFail = !c.skipped && c.code !== 0 && Array.isArray(c.here) && c.here.length > 0;
          const kept = !c.skipped && c.code !== 0 && !triedInput && !hereFail && left;
          // (exit, alone: nothing to keep)
          const idle = !c.skipped && !!ended && c.code === 0 && !left;
          const ran = !c.skipped && !triedInput && !idle && (c.code === 0 || kept);
          // the command as the script has it: the run's folder, named in full, is "$RUN_FOLDER"
          const A = ran ? MG.shellLang.anchor(c.cmd, place, TOP) : { text: c.cmd, left: false };
          const cmd = A.text;
          const out = ran && !outsideStart ? outsideWords(cmd, away ? 'out' : start.split('/').filter(Boolean).length, away ? ranAsScript : scriptsFrom(start), '$' + TOP) : [];
          // … and a command that runs a file of the agent's which reaches outside does so, too
          const byName = [];
          const runs = ran && !outsideStart ? scriptsOf(cmd, away ? null : start, byName).map(reachingAs).filter(Boolean) : [];
          const leave = (text) => {
            cmds.push(text + ': ' + asComment(c.cmd));
            leftOut++;
          };
          const some = (list, k) => list.slice(0, k).join(', ') + (list.length > k ? ' …' : '');
          const alsoLeft = wrote.length ? ` (it left ${some(wrote, 4)} behind, which a later command may need)` : '';
          if (c.skipped) cmds.push(`# not run (${c.skipped}): ${asComment(c.cmd)}`);
          else if (triedInput) cmds.push(`# ${c.code !== 0 ? `failed (exit status ${c.code}), ` : ''}left out – it tried to change the course data, which the page keeps as it is${alsoLeft}: ${asComment(c.cmd)}`);
          // (… and left something: one that left nothing is "failed, left out" like any other – a typing mistake, mostly)
          else if (hereFail && left) cmds.push(`# failed (exit status ${c.code}), left out – this terminal does not have ${some(c.here, 3)}${alsoLeft}. On a computer that has ${c.here.length === 1 ? 'it' : 'them'} the command would do more than it did in this run: ${asComment(c.cmd)}`);
          else if (c.code !== 0 && !kept) cmds.push(`# failed (exit status ${c.code}), left out: ${asComment(c.cmd)}`);
          // In the run the page put back what a command changed outside the run's folder. In a script nothing
          // does: run by a person, such a command really changes those files. So it is not part of the script –
          // and neither is a command that ran outside the folder, or that reaches outside it.
          else if ((c.undone && c.undone.length) || (c.lost && c.lost.length)) leave(`# left out – it changed files outside the run's folder (${(c.undone || []).concat(c.lost || []).slice(0, 4).join(', ')}), which the page put back${alsoLeft}`);
          else if (idle) leave(`# left out – "${ended === 'exec' ? 'exec' : 'exit'}" ended this block of the agent's commands; in a script it would end the script`);
          else if (outsideStart) leave(`# left out – it ran outside the run's folder (in ${start})`);
          else if (A.left) leave(`# left out – it names the run's folder in full (${fs.pretty(run)}) where the page cannot put "$${TOP}" for it (after a ~ inside quotes, or after another variable); write that path from the folder the script runs in, then put the command back`);
          else if (out.length) leave(`# left out – it reaches outside the folder (${why(out)}); put it back, with paths inside the folder, if the script needs it`);
          else if (runs.length) leave(`# left out – it runs ${runs[0]}, which reaches outside the folder (${why(reaching.get(runs[0]))}); change that file, then put the command back`);
          else if (c.outside && c.outside.length) leave(`# left out – when it ran it used paths outside the run's folder (${c.outside.slice(0, 4).join(', ')}); put it back, with paths inside the folder, if the script needs it`);
          else if (byName.length && reaching.size) leave(`# left out – it runs a script whose name is only known when the command runs (${byName[0]}), and a file of this run reaches outside the folder (${Array.from(reaching.keys())[0]}); change that file, then put the command back`);
          else {
            // the script is not where this command ran (a command that went there is left out, or one went to a folder outside)
            if (start !== at) {
              cmds.push(`cd ${away ? start.replace(/\/$/, '') : inTop(start)}  # added by the page: the folder in which the next command ran`);
              if (!away) usesTop = true;
            }
            if (cmd.includes('$' + TOP)) usesTop = true;
            const absent = notHere(cmd);
            (c.here || []).forEach((x) => !absent.includes(x) && absent.push(x));
            if (absent.length) cmds.push(`# CHECK: this command calls ${absent.join(', ')}, which this terminal does not have. On a computer that has ${absent.length === 1 ? 'it' : 'them'}, the command does more than it did in this run.`);
            // the course data of this page is not there on another computer
            if (away && /^~\/data/.test(start) ? at !== start : /(^|[\s"'=:(<>])(~|\$HOME|\$\{HOME\}|\/home\/student)\/data(\/|(?![\w.-]))/.test(cmd)) cmds.push('# CHECK: this uses ~/data, the course data of this page. On another computer that folder is not there: use data/ in the folder of the script.');
            const names = (c.unset || []).slice(0, 4).map((x) => (/^\d+$/.test(x) ? '$' + x : x));
            // Was the command cut short where a script ends? (Under the agent's own set -e a line of simple commands
            // is not: it ran to its end, and only then did set -e speak – "set +e" around it does the same.)
            const cut = !!ended && !(ended === 'set -e' && MG.shellLang.flat(cmd, funcs));
            if (cut) {
              // In the agent's run the command ended there, and the run went on with its next step: the page is not a
              // script. A script ends. In a subshell the command ends as it did, and the script goes on – with the
              // files it had written by then. What it had changed in the shell is lost with the subshell.
              const what = ended === 'exit' ? '"exit" ended this command in the agent\'s run' : ended === 'exec' ? '"exec" ended this command in the agent\'s run' : ended === 'unset' ? 'a name without a value ended this command in the agent\'s run (set -u, or ${NAME:?})' : `"set -e" ended this command part-way in the agent's run (exit status ${c.code})`;
              cmds.push(`# added by the page: ${what}, and the run went on with its next step.`, '# A script would end here. So the command runs in a subshell, ( … ), which ends in its place.');
              if (changed.length) cmds.push(`# CHECK: before it ended, the command had set or changed ${some(changed, 5)}. That stays in the subshell:`, '# a command below that counts on it will not find it.');
              // the script goes on whatever the status of the subshell; inside it the options are those of the run
              const tolerate = se0 && c.code !== 0;
              if (tolerate) cmds.push('set +e');
              const inside = [];
              if (re0 !== (tolerate ? false : se0)) inside.push(re0 ? 'set -e' : 'set +e');
              if (su0 && !ru0 && names.length) inside.push('set +u');
              cmds.push('(', ...inside, cmd, ')');
              const after = [];
              if (tolerate ? se1 : se1 !== se0) after.push(se1 ? 'set -e' : 'set +e');
              if (su1 !== su0) after.push(su1 ? 'set -u' : 'set +u');
              if (after.length) cmds.push(...after);
              eased++;
            } else {
              // The agent's commands ran without -e and -u; this script has both. Where the run went on although a
              // command inside failed (a grep that finds nothing in a loop), or used a name without a value, or where
              // the command itself did not end with 0, the script switches them off for this command – and says why.
              const off = [], because = [];
              if (c.code !== 0 && se0) {
                off.push('e');
                const leftText = wrote.length ? `and left ${some(wrote, 3)} behind${removed.length ? ` (${some(removed, 2)}: removed)` : ''}` : removed.length ? `after it had removed ${some(removed, 3)}` : `after it had set or changed ${some(changed, 3)}`;
                because.push(`this command ended with exit status ${c.code} in the agent's run, ${leftText}`);
              } else if (c.inner && se0 && !re0) {
                off.push('e');
                because.push("a command inside this one fails, and the agent's run went on");
              }
              if (names.length && su0 && !ru0) {
                off.push('u');
                because.push(`${names.join(', ')} ${names.length === 1 ? 'has' : 'have'} no value here, as in the agent's run`);
              }
              if (c.code !== 0 && !se0) cmds.push(`# (exit status ${c.code} in the agent's run)`);
              if (off.length) {
                cmds.push(`set +${off.join('')}  # added by the page: ${because.join('; ')}`, cmd);
                // (… and on again – unless the command itself switched the option off for good)
                const on = off.filter((x) => (x === 'e' ? se1 : su1));
                if (on.length) {
                  closers.add(cmds.length);
                  cmds.push(`set -${on.join('')}`);
                }
                eased++;
              } else {
                // (a line that asks how the command before it ended – $?, PIPESTATUS – must stand straight after it)
                if (/\$\?|\$\{?PIPESTATUS/.test(cmd)) asks.add(cmds.length);
                cmds.push(cmd);
              }
            }
            worked++;
            // where the run was after this command: where its next command started
            const next = s.commands[i + 1];
            at = next && !next.skipped ? next.cwd || '' : typeof c.after === 'string' ? c.after : s.cd ? null : start;
          }
        });
        // ($? and PIPESTATUS are those of the agent's command, not of the "set -e" that the page put behind it)
        for (let k = 0; k < cmds.length - 1; k++)
          if (closers.has(k) && asks.has(k + 1)) {
            [cmds[k], cmds[k + 1]] = [cmds[k + 1], cmds[k]];
            closers.add(k + 1);
          }
        n += worked;
        // the agent's next step started in the run's folder again
        if (worked && at !== '') {
          cmds.push(`cd "$${TOP}"  # added by the page: the agent's next step started in the run's folder again`);
          usesTop = true;
        }
        lines.push(...cmds);
        if (lines.length) L.push(`# step ${s.n}${s.say ? ': ' + s.say.replace(/\s+/g, ' ').slice(0, 160) : ''}`, ...lines, '');
      });
      // (the agent's shell does not end like a script does: a trap … EXIT of the run never ran there)
      if (R.exitTrap && n) L.push("# added by the page: the run set a trap for EXIT, which never ran in the agent's run (the agent's shell does not end", '# the way a script ends). Take this line out if the script should clean up after itself.', 'trap - EXIT', '');
      const head = L.indexOf('set -eu');
      if (usesTop)
        L.splice(head + 1, 0, '', `# ${TOP}: the folder this script runs in. It stands where a command of the agent named the run's folder in full`, `# (${fs.pretty(run)}), and where the script goes back to the folder it started in.`, `${TOP}=$PWD`);
      if (leftOut) L.splice(head, 0, `# ${plural(leftOut, 'command')} of the run that worked ${leftOut === 1 ? 'is' : 'are'} not in this script: see “left out” below.`);
      if (eased) L.splice(head, 0, "# The agent's own commands ran without -e and -u. Where its run went on past a command that fails, or past a name", '# without a value, the script does the same: see "added by the page" below.');
      if (!n) throw Object.assign(new Error(leftOut ? 'Every command of this run that worked reaches outside the run’s folder, so there is nothing to put in a script.' : 'No command of this run worked, so there is nothing to put in a script.'), { user: true });
      const path = run + '/rerun.sh';
      await MG.app.whenAgentIdle();
      const e = fs.get(path);
      if (e && e.kind === 'text' && e.text !== L.join('\n') && !window.confirm(`${fs.pretty(path)} already exists – perhaps with your changes. Replace it?`)) return;
      fs.writeText(path, L.join('\n'));
      await MG.app.editFile(path, { line: 1 });
      toast(`Wrote <b>${esc(fs.pretty(path))}</b>: ${plural(n, 'command')} of run ${R.id}.`, null, 5000);
      bus.emit('agent:script', { run: R.id, path: fs.pretty(path), commands: n });
    }

    /* ---------------- talking to the service ---------------- */
    /* Stream an answer.
       Gemini: the chosen model is asked first, then the fallback models in their order – but not a model that the
       page knows to be busy, silent or over a limit (the memory above). A model that is busy (HTTP 5xx), over a
       limit (429), not found (404) or gives no answer (the connection fails, or nothing comes for a minute) is
       noted, and the next one is asked. An answer that breaks off part-way is taken back (cfg.onReset) and the
       question goes to the next model. When no model is left that is not at rest, the two that have rested longest
       of those that were only busy or silent get another chance. Two models in a row that give no answer end the
       request: that is the connection, not the models.
       Other services: one model; if it is busy, a second try after a short pause.
       → { model, skipped }: the model that answered, and what kept others from it – the chosen model if it is at
         rest, and every model that failed in this request.
       When nothing answers, the error says what each model said. Its .status is 429 (limits), 503 (busy) or not set
       (no answer came); .retryIn is the number of seconds after which asking again can help – not set when it
       cannot (a wrong key; every model over its limit for today). */
    async stream(messages, onDelta, signal, cfg, onNote) {
      const s = (cfg && cfg.settings) || this.settings;
      const key = cfg && cfg.key != null ? cfg.key : this.key;
      const system = (cfg && cfg.system) || 'You are a helpful assistant.';
      const note = onNote || (() => {});
      const reset = cfg && cfg.onReset;
      // turns must alternate between user and assistant: join neighbours of the same role
      messages = messages.reduce((out, m) => {
        const last = out[out.length - 1];
        if (last && last.role === m.role) last.content += '\n\n' + m.content;
        else out.push({ role: m.role, content: m.content });
        return out;
      }, []);
      if (s.provider !== 'gemini') {
        const model = modelOf(s);
        for (let attempt = 1; ; attempt++) {
          let started = false;
          try {
            await this.streamOnce(s, key, model, messages, (d) => {
              started = true;
              onDelta(d);
            }, signal, system);
            return { model, skipped: [] };
          } catch (e) {
            if (e.name !== 'AbortError' && !started && BUSY.includes(e.status) && attempt === 1) {
              note(`${model} is busy – trying again…`);
              await pause(1500 + Math.random() * 1500, signal);
              continue;
            }
            if (e.status === 429 && !started) e.retryIn = Math.round(Math.min(90, Math.max(5, e.retryAfter || 30)));
            throw e;
          }
        }
      }
      const chosen = geminiModelOf(s);
      const chain = [chosen].concat(FALLBACKS.filter((m, i, a) => a.indexOf(m) === i && m !== chosen));
      if (restKey !== key) {
        // another key is another project, with limits of its own
        REST.clear();
        restKey = key;
      }
      try {
        if (navigator.onLine === false) throw Object.assign(new Error('This browser is offline. Connect it to the internet, and try again.'), { network: true, retryIn: RETRY });
        const said = new Map(); // what each model said: in this request, or when it was last asked and is still at rest
        chain.forEach((m) => resting(m) && said.set(m, REST.get(m)));
        const failed = [];
        let queue = chain.filter((m) => !said.has(m));
        let again = false, silent = 0;
        for (;;) {
          if (!queue.length && !again) {
            again = true;
            queue = chain.filter((m) => said.has(m) && !failed.includes(said.get(m)) && (said.get(m).why === 'busy' || said.get(m).why === 'noanswer')).sort((a, b) => said.get(a).until - said.get(b).until).slice(0, 2);
          }
          if (!queue.length) break;
          const model = queue.shift();
          const before = failed[failed.length - 1];
          if (before) note(`${before.model} ${before.broke ? 'broke off' : told(before, true)} – asking ${model} instead…`);
          let started = false;
          try {
            await this.streamOnce(s, key, model, messages, (d) => {
              started = true;
              onDelta(d);
            }, signal, system);
            REST.delete(model);
            const first = model !== chosen && said.get(chosen);
            return { model, skipped: (first && !failed.includes(first) ? [first] : []).concat(failed).map((x) => ({ model: x.model, why: x.broke ? 'broke' : x.why, daily: x.daily })) };
          } catch (e) {
            if (e.name === 'AbortError') throw e;
            const why = e.network ? 'noanswer' : e.status === 404 ? 'notfound' : e.status === 429 ? 'limit' : BUSY.includes(e.status) ? 'busy' : '';
            // an error of another kind (the key, the request itself) – or an answer that broke off and cannot be taken back
            if (!why || (started && !reset)) throw e;
            if (started) reset();
            const was = REST.get(model);
            const x = { model, why, broke: started, status: e.status, text: e.message, at: Date.now(), until: Infinity };
            if (why === 'limit') {
              const wait = e.retryAfter > 0 ? Math.min(86400, e.retryAfter) : e.daily ? 3600 : 60;
              x.daily = !!e.daily || wait > 900;
              x.limit = e.limit;
              x.until = Date.now() + (wait + 1) * 1000;
            } else if (why === 'busy') {
              // busy again soon after its rest: the rest is twice as long (2, 4, 8, at most 15 minutes)
              x.n = was && was.why === 'busy' && Date.now() - was.until < 600000 ? was.n + 1 : 1;
              x.until = Date.now() + Math.min(900, BUSY_REST * 2 ** (x.n - 1)) * 1000;
            } else if (why === 'noanswer') x.until = Date.now() + SILENT_REST * 1000;
            REST.set(model, x);
            said.set(model, x);
            failed.push(x);
            silent = why === 'noanswer' ? silent + 1 : 0;
            if (silent >= 2) break;
          }
        }
        throw noAnswer(chain.map((m) => said.get(m)).filter(Boolean), silent >= 2);
      } finally {
        this.showStatus();
      }
    }
    /** one request; the answer is passed to onDelta as it arrives.
        An error that the service reports carries .status – and for "too many requests" (429) .retryAfter (seconds)
        and, when the service names a limit per day, .daily and .limit. An answer that does not come – the connection
        fails or breaks off, or (Gemini) nothing arrives for a minute (aiWaitSeconds) – carries .network. */
    async streamOnce(s, key, model, messages, onDelta, signal, system) {
      const gem = s.provider === 'gemini';
      const base = (s.baseURL || '').replace(/\/+$/, '');
      if (signal && signal.aborted) throw stopped();
      // the request ends when the user presses Stop – or when the service has said nothing for too long
      const ac = new AbortController();
      const onStop = () => ac.abort();
      if (signal) signal.addEventListener('abort', onStop, { once: true });
      const quiet = gem ? WAIT() * 1000 : 0;
      let timer = null, silent = false, bytes = 0;
      const arm = () => {
        clearTimeout(timer);
        if (quiet)
          timer = setTimeout(() => {
            silent = true;
            ac.abort();
          }, quiet);
      };
      /* why the answer did not come: the user's Stop, the service's silence, or the connection */
      const lost = (e) => {
        if (signal && signal.aborted) return stopped();
        if (silent) return Object.assign(new Error(`${model} ${bytes ? 'stopped in the middle of its reply and said nothing more' : 'gave no answer'} for ${Math.round(quiet / 1000)} seconds.`), { network: true, silent: true });
        if (e.name === 'AbortError') return e;
        const where = gem ? 'the Gemini API' : s.provider === 'anthropic' ? 'the Anthropic API' : base;
        return Object.assign(new Error(bytes ? `The connection to ${where} broke off in the middle of the reply (${e.message}).` : `Could not reach ${where} (${e.message}). ${s.provider === 'openai' ? 'Check the address; the service must allow requests from web pages (CORS).' : 'Check the internet connection.'}`), { network: true });
      };
      /* an error that the service reports: as the status of its answer, or (Gemini) inside an answer that had begun */
      const refused = (status, j, statusText, retryHeader) => {
        const err = (j && j.error) || null;
        const det = err && Array.isArray(err.details) ? err.details.filter(Boolean) : [];
        const detail = j ? (err && (err.message || err.type)) || JSON.stringify(j).slice(0, 300) : statusText || '';
        const reason = err ? det.map((d) => d.reason).filter(Boolean)[0] || err.status || '' : '';
        const ri = det.find((d) => /RetryInfo$/.test(d['@type'] || ''));
        const retryAfter = (ri && parseFloat(ri.retryDelay)) || parseFloat(retryHeader) || 0;
        // a limit per day is named in the answer: quotaId "GenerateRequestsPerDayPerProjectPerModel-FreeTier", with its value
        const qf = det.find((d) => /QuotaFailure$/.test(d['@type'] || ''));
        const day = ((qf && qf.violations) || []).find((v) => v && /PerDay/i.test(v.quotaId || ''));
        const limit = day && /^\d+$/.test(String(day.quotaValue)) ? +day.quotaValue : undefined;
        const badKey = status === 401 || status === 403 || reason === 'API_KEY_INVALID';
        const why = badKey
          ? 'The API key was not accepted.'
          : status === 404
            ? `The model name (${model}) may be wrong, or the model has been retired – check it in the AI settings (⚙).`
            : status === 429
              ? gem
                ? day
                  ? `${model} is over its limit for today${limit != null ? ` (${limit} requests a day)` : ''}. The free tier allows each model a number of requests per day, counted per project: go on when the service takes requests again, use a key from another person or project, or choose another model in the AI settings (⚙).`
                  : 'Too many requests: the free tier allows only a few requests per minute and per day – wait a minute and try again.'
                : 'Too many requests, or no credit left – try again in a minute.'
              : BUSY.includes(status)
                ? gem
                  ? `Google’s servers are busy for ${model} (“high demand”). That is on Google’s side, not a problem with your key: wait a minute and try again, or choose another model in the AI settings (⚙).`
                  : 'The service is busy or had a temporary problem – try again in a minute.'
                : '';
        return Object.assign(new Error(`HTTP ${status}. ${why} ${detail}`.trim()), { status, retryAfter, daily: !!day, limit });
      };
      try {
        arm();
        let r;
        if (s.provider === 'anthropic') {
          r = await fetch('https://api.anthropic.com/v1/messages', {
            method: 'POST',
            headers: { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true' },
            body: JSON.stringify({ model, max_tokens: 4000, system, messages, stream: true }),
            signal: ac.signal
          }).catch((e) => {
            throw lost(e);
          });
        } else if (gem) {
          // Google's Gemini API (generateContent, streamed as server-sent events); the whole conversation is sent each time
          r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:streamGenerateContent?alt=sse`, {
            method: 'POST',
            headers: { 'content-type': 'application/json', 'x-goog-api-key': key },
            body: JSON.stringify({ system_instruction: { parts: [{ text: system }] }, contents: messages.map((m) => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] })) }),
            signal: ac.signal
          }).catch((e) => {
            throw lost(e);
          });
        } else {
          r = await fetch(base + '/chat/completions', {
            method: 'POST',
            headers: Object.assign({ 'content-type': 'application/json' }, key ? { authorization: 'Bearer ' + key } : {}),
            body: JSON.stringify({ model, stream: true, messages: [{ role: 'system', content: system }].concat(messages) }),
            signal: ac.signal
          }).catch((e) => {
            throw lost(e);
          });
        }
        arm();
        if (!r.ok) {
          let j = null;
          try {
            j = await r.json();
          } catch (e) {
            if (signal && signal.aborted) throw stopped();
          }
          throw refused(r.status, j, r.statusText, r.headers.get('retry-after'));
        }
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        for (;;) {
          const { value, done } = await reader.read().catch((e) => {
            throw lost(e);
          });
          if (done) break;
          arm();
          bytes += value.length;
          buf += dec.decode(value, { stream: true });
          let k;
          while ((k = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, k).trim();
            buf = buf.slice(k + 1);
            if (!line.startsWith('data:')) continue;
            const data = line.slice(5).trim();
            if (!data || data === '[DONE]') continue;
            let j;
            try {
              j = JSON.parse(data);
            } catch (e) {
              continue;
            }
            if (s.provider === 'anthropic') {
              if (j.type === 'content_block_delta' && j.delta && j.delta.type === 'text_delta') onDelta(j.delta.text);
              else if (j.type === 'error') throw Object.assign(new Error((j.error && j.error.message) || 'stream error'), { status: j.error && j.error.type === 'overloaded_error' ? 529 : undefined });
            } else if (gem) {
              if (j.error) {
                // an error in an answer that began with "200 OK": the same kinds as the errors that come instead of an answer
                const code = +j.error.code || { UNAVAILABLE: 503, RESOURCE_EXHAUSTED: 429, INTERNAL: 500, DEADLINE_EXCEEDED: 504, NOT_FOUND: 404 }[j.error.status];
                throw code ? refused(code, j) : new Error(j.error.message || 'stream error');
              }
              if (j.promptFeedback && j.promptFeedback.blockReason) throw new Error('Gemini did not answer (' + j.promptFeedback.blockReason + ').');
              const cand = (j.candidates && j.candidates[0]) || {};
              ((cand.content && cand.content.parts) || []).forEach((p) => {
                if (p.text && !p.thought) onDelta(p.text);
              });
              // A reply that the service cut off as a "malformed function call": the model had begun its ```bash block,
              // and the service took the fence for the call of a tool named bash. What it took away is in finishMessage
              // ("Malformed function call: call:bash ```", the commands, "```") – the block goes back into the reply.
              // (Seen with gemini-3.5-flash on 6 October 2026, twice in about seventy replies.)
              if (cand.finishReason === 'MALFORMED_FUNCTION_CALL' && typeof cand.finishMessage === 'string') {
                const m = /call:\s*(?:bash|sh|shell)\s*```[^\n]*\n([\s\S]*?)\n?```\s*$/.exec(cand.finishMessage);
                if (m && m[1].trim()) onDelta('\n\n```bash\n' + m[1] + '\n```\n');
              }
            } else {
              const dd = j.choices && j.choices[0] && j.choices[0].delta;
              if (dd && dd.content) onDelta(dd.content);
            }
          }
        }
      } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener('abort', onStop);
        ac.abort(); // (nothing is left to end when the answer came whole)
      }
    }

    /* ---------------- connecting ---------------- */
    /** the form: service, model, key – and Connect, which tests the connection */
    connectForm(box, opts = {}) {
      const s = this.settings;
      let remembered = true;
      try {
        remembered = !this.key || !!window.sessionStorage.getItem(KEY_NAME);
      } catch (e) {
        remembered = false;
      }
      box.innerHTML = `
<div class="ai-set">
  ${opts.inline ? `<h3>${MG.icon('sparkle')} Connect an AI model</h3><p>The assistant and the agent of this practical are a <b>real AI model</b>. It needs an API key – yours, or one your lecturer gives you. Google’s Gemini API has a free tier.</p>` : ''}
  <label>Service <select data-k="provider"><option value="gemini" ${s.provider === 'gemini' ? 'selected' : ''}>Google Gemini (has a free tier)</option><option value="anthropic" ${s.provider === 'anthropic' ? 'selected' : ''}>Anthropic (Claude)</option><option value="openai" ${s.provider === 'openai' ? 'selected' : ''}>OpenAI-compatible service</option></select></label>
  <label data-show="gemini">Model <input data-k="geminiModel" value="${esc(geminiModelOf(s))}" spellcheck="false"></label>
  <label data-show="anthropic">Model <input data-k="model" value="${esc(anthropicModelOf(s))}" spellcheck="false"></label>
  <label data-show="openai">Address <input data-k="baseURL" value="${esc(s.baseURL)}" spellcheck="false" placeholder="https://…/v1"></label>
  <label data-show="openai">Model <input data-k="openaiModel" value="${esc(s.openaiModel)}" placeholder="the model name your service uses" spellcheck="false"></label>
  <label>API key <input data-k="key" type="password" value="${esc(this.key)}" autocomplete="off" spellcheck="false" placeholder="paste the key here"></label>
  <label class="ai-cb"><input type="checkbox" data-k="remember" ${remembered ? 'checked' : ''}> Keep the key in this browser tab when the page is loaded again</label>
  <p data-show="gemini" class="muted small"><b>A Gemini key:</b> sign in with a Google account at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> and choose <i>Create API key</i> (you must be 18 or over). A key without billing is on the free tier: only a few requests per minute, and a limited number per day, are allowed – an agent uses one request for each step. On the free tier Google may use what you send to improve its products, and people may read it (for users in the UK, the EEA and Switzerland, <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noopener">Google’s terms</a> say that it does not use what they send to improve its products).</p>
  <p class="muted small"><b>What is sent, and where.</b> Your key stays in this browser tab and goes only to the service you choose – never to this website. (On a shared computer, take it out before you leave: ⚙ above, then <b>Disconnect</b>.) To that service go: what you type; a description of this terminal and the names of your files; a failed command and what it printed, when you ask about it; and, when the agent works, its commands and what each one prints – of long output the beginning and the end (this can include lines of the data). The files themselves are not sent. The data here is from a public reference sample, so that is fine. <b>Never do this with personal or patient data.</b></p>
  <div class="prompt-actions"><span class="ai-test-out muted small" role="status"></span>${this.ok && !opts.inline ? '<button class="btn" data-x="forget" type="button">Disconnect</button>' : ''}<button class="btn primary" data-x="connect" type="button">${this.ok && !opts.inline ? 'Test and save' : 'Connect'}</button></div>
</div>`;
      const val = (k) => box.querySelector(`[data-k="${k}"]`);
      const sync = () => {
        const p = val('provider').value;
        box.querySelectorAll('[data-show]').forEach((el) => (el.hidden = el.dataset.show !== p));
      };
      val('provider').addEventListener('change', sync);
      sync();
      // a model left at the site's default is saved as '' (= follow config.js)
      const own = (k, dflt) => {
        const v = val(k).value.trim().replace(/^models\//, '');
        return v && v !== dflt ? v : '';
      };
      const read = () => ({
        settings: { provider: val('provider').value, model: own('model', DEFAULTS.model), geminiModel: own('geminiModel', DEFAULTS.geminiModel), baseURL: val('baseURL').value.trim(), openaiModel: val('openaiModel').value.trim() },
        key: val('key').value.trim()
      });
      const out = box.querySelector('.ai-test-out');
      const go = box.querySelector('[data-x="connect"]');
      go.addEventListener('click', async () => {
        const r = read();
        if (!r.key && needsKey(r.settings)) {
          out.textContent = 'Paste an API key first.';
          val('key').focus();
          return;
        }
        if (r.settings.provider === 'openai' && !r.settings.openaiModel) {
          out.textContent = 'Give the name of the model.';
          val('openaiModel').focus();
          return;
        }
        go.disabled = true;
        out.textContent = 'Asking the model to answer…';
        let got = '';
        try {
          const res = await this.stream([{ role: 'user', content: 'Reply with the single word: ready' }], (d) => (got += d), undefined, { settings: r.settings, key: r.key, system: 'You are being tested for a connection. Reply with one word.', onReset: () => (got = '') }, (note) => (out.textContent = note));
          this.settings = r.settings;
          this.key = r.key;
          this.ok = true;
          store.set('ai:settings', this.settings);
          store.set('ai:ok', true);
          try {
            if (val('remember').checked && this.key) window.sessionStorage.setItem(KEY_NAME, this.key);
            else window.sessionStorage.removeItem(KEY_NAME);
          } catch (e) {
            /* storage may be blocked: the key then lasts until the page is reloaded */
          }
          toast(`Connected: ${esc(res.model)} answered “${esc(got.trim().slice(0, 30))}”.` + (res.skipped.length ? ` (${esc(res.skipped.map((x) => x.model + ' ' + skipWord(x)).join(', '))})` : ''), null, 5000);
          bus.emit('ai:connect', { ok: true, provider: this.settings.provider, model: res.model });
          if (opts.onDone) opts.onDone();
          this.refresh();
          this.showTab(this.tab, true);
        } catch (e) {
          out.textContent = '✗ ' + e.message;
          bus.emit('ai:connect', { ok: false, provider: r.settings.provider });
        } finally {
          go.disabled = false;
        }
      });
      const forget = box.querySelector('[data-x="forget"]');
      if (forget)
        forget.addEventListener('click', () => {
          this.key = '';
          this.ok = false;
          store.set('ai:ok', false);
          try {
            window.sessionStorage.removeItem(KEY_NAME);
          } catch (e) {
            /* nothing was stored */
          }
          if (opts.onDone) opts.onDone();
          this.refresh();
          toast('Disconnected: the key was removed from this browser tab.');
        });
    }
    settingsDialog() {
      if (this.busy) return toast('Wait until the AI has finished.', 'warn');
      if (!this.ok) {
        MG.app.showWorkbench('assistant');
        const k = this.connectEl.querySelector('[data-k="key"]');
        if (k) k.focus();
        return;
      }
      const m = MG.modal('The AI service', '<div class="ai-setbox"></div>');
      this.connectForm(m.box.querySelector('.ai-setbox'), { onDone: () => m.close() });
    }
  }

  MG.Assistant = Assistant;
  MG.renderMarkdown = renderMarkdown;
  MG.aiUtil = { parseReply, cleanReport, refusal, renderMarkdown, outsideWords, reachedOutside, MODES, modelMemory: REST };
})();
