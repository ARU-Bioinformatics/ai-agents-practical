# Third-party software, data and source provenance

This practical bundles independently licensed programs and libraries. Each keeps its own licence: the MIT licence of the Biowasm build framework does **not** relicense the programs it compiled, and none of the licences below applies to the practical's own text and code. Keep each component's notices and licence files when copying or redistributing its files.

## Command-line programs (WebAssembly, run in the browser)

These are the real programs, compiled to WebAssembly. They run on the student's own computer, inside the web page. Each folder `assets/vendor/biowasm/NAME/VERSION/` holds the program (`.wasm`, its JavaScript loader, sometimes a `.data` file), its licence, a `NOTICE.txt` (origin and local changes) and `SHA256SUMS`. (The folder of the base module has a notice and checksums only: its licence is the Biowasm licence in `assets/vendor/biowasm/LICENSE.txt`. The four files at the top of `assets/vendor/biowasm/` – the runner, its licence and the two descriptions of the local changes – have a `SHA256SUMS` of their own there.)

| Program | Version | Licence | Folder | Upstream source |
| --- | --- | --- | --- | --- |
| fastp | 0.20.1 | MIT | [fastp/0.20.1](assets/vendor/biowasm/fastp/0.20.1/) | [OpenGene/fastp](https://github.com/OpenGene/fastp/tree/v0.20.1) |
| minimap2 | 2.22 | MIT | [minimap2/2.22](assets/vendor/biowasm/minimap2/2.22/) | [lh3/minimap2](https://github.com/lh3/minimap2/tree/v2.22) |
| **Bowtie 2** (`bowtie2-align-s`, `bowtie2-build-s`) – compiled for this practical | 2.4.2 | **GPL version 3**; contains zlib 1.3.2 (zlib licence) | [bowtie2/2.4.2](assets/vendor/biowasm/bowtie2/2.4.2/) | [BenLangmead/bowtie2](https://github.com/BenLangmead/bowtie2/tree/v2.4.2); source, patch and build script are [included](assets/vendor/licenses/) |
| SAMtools | 1.17 | MIT/Expat | [samtools/1.17](assets/vendor/biowasm/samtools/1.17/) | [samtools](https://github.com/samtools/samtools/tree/1.17) |
| BCFtools (with its built-in HTSlib 1.10) | 1.10 | MIT/Expat (GPL only if built with the GNU Scientific Library, which it is not); HTSlib: MIT/Expat and modified 3-clause BSD | [bcftools/1.10](assets/vendor/biowasm/bcftools/1.10/) | [bcftools](https://github.com/samtools/bcftools/tree/1.10) |
| HTSlib utilities `bgzip`, `tabix` | 1.17 | MIT/Expat and modified 3-clause BSD | [htslib/1.17](assets/vendor/biowasm/htslib/1.17/) | [htslib](https://github.com/samtools/htslib/tree/1.17) |
| bedtools | 2.31.0 | MIT | [bedtools/2.31.0](assets/vendor/biowasm/bedtools/2.31.0/) | [arq5x/bedtools2](https://github.com/arq5x/bedtools2/tree/v2.31.0) |
| seqtk | 1.4 | MIT | [seqtk/1.4](assets/vendor/biowasm/seqtk/1.4/) | [lh3/seqtk](https://github.com/lh3/seqtk/tree/v1.4) |
| jq | 1.7 | MIT (documentation CC BY 3.0; parts under other permissive licences, see its `COPYING`); contains the regular-expression library Oniguruma (2-clause BSD, `ONIGURUMA-COPYING`) | [jq/1.7](assets/vendor/biowasm/jq/1.7/) | [jqlang/jq](https://github.com/jqlang/jq/tree/jq-1.7) |
| **GNU coreutils**: `cat comm cut date fold head join md5sum paste seq shuf sort tail tee tr uniq wc` | 8.32 | **GPL version 3 or later** | [coreutils/8.32](assets/vendor/biowasm/coreutils/8.32/) | [release source](https://ftp.gnu.org/gnu/coreutils/coreutils-8.32.tar.xz), [included](assets/vendor/licenses/sources/) |
| **GNU Awk** (`gawk`, also as `awk`) | 5.1.0 | **GPL version 3 or later** | [gawk/5.1.0](assets/vendor/biowasm/gawk/5.1.0/) | [release source](https://ftp.gnu.org/gnu/gawk/gawk-5.1.0.tar.xz), [included](assets/vendor/licenses/sources/) |
| **GNU grep** | 3.7 | **GPL version 3 or later** | [grep/3.7](assets/vendor/biowasm/grep/3.7/) | [release source](https://ftp.gnu.org/gnu/grep/grep-3.7.tar.xz), [included](assets/vendor/licenses/sources/) |
| **GNU grep with PCRE2**, for `grep -P` – compiled for this practical | grep 3.11, PCRE2 10.42 | grep: **GPL version 3 or later**; PCRE2: 3-clause BSD with the PCRE2 exemption (`PCRE2-LICENCE`) | [grep/3.11](assets/vendor/biowasm/grep/3.11/) | [grep release source](https://ftp.gnu.org/gnu/grep/grep-3.11.tar.xz), [PCRE2 release source](https://github.com/PCRE2Project/pcre2/releases/tag/pcre2-10.42); both sources and the build script are [included](assets/vendor/licenses/) |
| **GNU sed** | 4.8 | **GPL version 3 or later** | [sed/4.8](assets/vendor/biowasm/sed/4.8/) | [release source](https://ftp.gnu.org/gnu/sed/sed-4.8.tar.xz), [included](assets/vendor/licenses/sources/) |
| **GNU diffutils**: `diff`, `cmp` – compiled for this practical | 3.10 | **GPL version 3 or later** | [diffutils/3.10](assets/vendor/biowasm/diffutils/3.10/) | [release source](https://ftp.gnu.org/gnu/diffutils/diffutils-3.10.tar.xz); source, patch and build script are [included](assets/vendor/licenses/) |
| Biowasm base module and the Aioli runner (`aioli.js`, which includes Comlink) | base 1.0.0; Aioli from the Biowasm CDN, series 3 | MIT. Comlink: Apache 2.0 (Copyright 2019 Google LLC) | [notice and MIT licence](assets/vendor/biowasm/LICENSE.txt); [Apache 2.0](assets/vendor/licenses/Apache-2.0.txt) | [biowasm](https://github.com/biowasm/biowasm), [aioli](https://github.com/biowasm/aioli), [comlink](https://github.com/GoogleChromeLabs/comlink) |

Every `.wasm` file also contains parts of the Emscripten runtime and its C and C++ libraries (musl, libc++, compiler-rt: MIT; Apache 2.0 with LLVM exception), and, where compressed files are read, zlib (HTSlib-based programs also bzip2 and liblzma). The licence texts of these libraries are in [assets/vendor/licenses/runtime-libraries/](assets/vendor/licenses/runtime-libraries/).

**Where the builds came from.** All programs except Bowtie 2, `diff`, `cmp` and the grep that carries out `grep -P` are builds of the [Biowasm](https://biowasm.com) project, downloaded from `https://biowasm.com/cdn/v3/NAME/VERSION/` on 30 September and 1–2 October 2026 (each `NOTICE.txt` has the date). The two Bowtie 2 programs, `diff` and `cmp` of GNU diffutils, and GNU grep 3.11 with PCRE2 10.42 were compiled for this practical with Emscripten 6.0.10 – Bowtie 2 and `cmp` from their release sources with a small patch, grep and PCRE2 from theirs unchanged; they are not Biowasm builds.

**Local changes** – all listed in [assets/vendor/biowasm/RUNTIME-PATCHES.txt](assets/vendor/biowasm/RUNTIME-PATCHES.txt):

- The JavaScript loaders of the programs record each program's exit status. The Aioli runner has two added methods: `execIO` runs a program with real standard input, output and error, and `statTree` lists the shared file system in one answer; [execio-source.txt](assets/vendor/biowasm/execio-source.txt) is their readable source.
- In each of the 17 **coreutils** programs and in **grep**, **one byte** of the `.wasm` file is changed, which makes the C library's standard output unbuffered. Unchanged, these builds lose output that does not end with a newline (`tr`, `head -c`, `fold` …; `grep -lZ`, `grep -z`). The byte, the reason and the checksums of the files as downloaded are in the [coreutils notice](assets/vendor/biowasm/coreutils/8.32/NOTICE.txt) and the [grep notice](assets/vendor/biowasm/grep/3.7/NOTICE.txt); the script that makes the change is [unbuffer-stdout.py](assets/vendor/licenses/local-patches/unbuffer-stdout.py).
- In the loaders of **date** and **gawk** the day of the year is counted in calendar days ([fix-day-of-year.py](assets/vendor/licenses/local-patches/fix-day-of-year.py)): as downloaded, `date -d 2024-07-15` printed “invalid date” in zones with summer time.
- All other `.wasm` and `.data` files from Biowasm are unmodified.

**Source code of the GPL programs.** [assets/vendor/licenses/](assets/vendor/licenses/) – see its [README.txt](assets/vendor/licenses/README.txt) – holds:

- the full text of the GPL version 3 ([GPL-3.0.txt](assets/vendor/licenses/GPL-3.0.txt)) and of the Apache License 2.0 ([Apache-2.0.txt](assets/vendor/licenses/Apache-2.0.txt), for Comlink);
- the release sources of the five GNU packages (coreutils, diffutils, gawk, grep 3.7 and 3.11, sed), of Bowtie 2 2.4.2 and of PCRE2 10.42 in [sources/](assets/vendor/licenses/sources/), with origins and SHA-256 values in [source-archives.json](assets/vendor/licenses/source-archives.json);
- for Bowtie 2: the patch, the build script and instructions in [bowtie2-build/](assets/vendor/licenses/bowtie2-build/);
- for `diff` and `cmp`: the patch (one line of `cmp.c`), the build script and instructions in [diffutils-build/](assets/vendor/licenses/diffutils-build/);
- for the grep that carries out `grep -P`: the build script, the one function added at link time and instructions in [grep-perl-build/](assets/vendor/licenses/grep-perl-build/);
- for the Biowasm builds: the recipes (scripts and patches) of the programs used here, from one pinned commit ([`97bb232`](https://github.com/biowasm/biowasm/tree/97bb23225892ba5cc59ba0deac8b212b957db66a)), in [biowasm-build/](assets/vendor/licenses/biowasm-build/), listed with checksums in [biowasm-build-manifest.json](assets/vendor/licenses/biowasm-build-manifest.json). The commit and toolchain of the original CDN builds are not known, so this is a pinned recipe for inspection and rebuilding, **not** a claim that rebuilding gives identical binaries;
- the licence texts of the libraries inside the programs (Emscripten's runtime, musl, LLVM's libraries, zlib, bzip2, liblzma) in [runtime-libraries/](assets/vendor/licenses/runtime-libraries/);
- the scripts of the two local changes to downloaded files in [local-patches/](assets/vendor/licenses/local-patches/).

The GPL's terms for distributing compiled programs and their Corresponding Source are in its section 6. Whoever hosts this site should keep `assets/vendor/licenses/` and this file with it. Copyright statements of the programs and of the code they include remain in their source releases; a licence label in the table above does not replace the notices in individual source files.

## JavaScript libraries (bundled)

| Library | Version | Licence | Files |
| --- | --- | --- | --- |
| CodeMirror 5 (the editor, with the shell and Markdown modes and three add-ons) | 5.65.18 | MIT | [assets/vendor/codemirror/](assets/vendor/codemirror/) |
| JSZip (zip downloads; includes pako) | 3.10.1 | MIT or GPL version 3 (pako: MIT) | [assets/vendor/jszip/](assets/vendor/jszip/) |
| plotly.js, “basic” bundle (the plots in fastp's HTML report, which asks for plotly from a CDN; the report viewer gives it this copy instead) | 4.1.1 | MIT | [assets/vendor/plotly/](assets/vendor/plotly/) |

## Loaded at run time, not bundled

Nothing is loaded from other sites, with one exception: the **AI service** that the student chooses and connects with their own API key (Google Gemini, Anthropic, or an OpenAI-compatible service). The student's messages, and the agent's commands and their output, go from the student's browser to that service. No AI model or service is part of the site.

## Written for this practical

The page itself, including:

- the **shell** (`assets/js/shell-lang.js`, `shell.js`, `shell-extra.js`): a subset of bash in JavaScript, the commands that work on the page's folders (`ls`, `cp`, `find`, `xargs`, `stat` …) and a few small tools (`bc`, `od`, `split`, `base64` …). They contain no code from bash or the GNU programs: they are new code that follows what those programs do (their manuals, and their output on Linux, with which the tests compare them), so that what students learn transfers. (`diff` and `cmp` are not among them: those are the GNU programs themselves, see above.)
- the **AI panel** (`assets/js/assistant.js`): the chat, the agent's loop, the record of a run.

## Data

| Data | Source | Terms |
| --- | --- | --- |
| `data/NA12878_R1.fastq`, `data/NA12878_R2.fastq` | NA12878 exome reads (run SRR098401), reconstructed from the [1000 Genomes phase 3 exome alignment](https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/phase3/data/NA12878/exome_alignment/) of NA12878 | open data of the 1000 Genomes Project, distributed by the International Genome Sample Resource ([IGSR disclaimer](https://www.internationalgenome.org/IGSR_disclaimer), [data use FAQ](https://www.internationalgenome.org/faq/do-i-need-permission-to-use-igsr-data-in-my-own-scientific-research/)); NA12878 is the widely used public reference sample (Coriell cell line GM12878) |
| `data/reference.fa` | two slices of the UCSC hg19 human reference (chr10) | [UCSC Genome Browser conditions of use](https://genome.ucsc.edu/conditions.html) |

How the reads and the reference were extracted – addresses, hashes, counts and limitations – is recorded in [data/provenance.json](data/provenance.json) and summarised in [data/README.md](data/README.md). The reads are real sequencing data; none are simulated.
