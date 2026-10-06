"""Output that does not end with a newline must not be lost (and nothing else changed).
Each command runs in the page and in real bash with native tools; the outputs must be equal."""
import sys, subprocess, os
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8862
NATIVE = os.environ.get('NATIVE_TOOLS', '')   # folders with native samtools 1.17, bcftools 1.10, jq …, separated by ':' (default: the PATH)
WORK = OUT_DIR + '/partial'
SETUP = [
    'minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq 2>/dev/null | samtools sort -o s.bam && samtools index s.bam',
    'bcftools mpileup -f data/reference.fa s.bam 2>/dev/null | bcftools call -mv -Oz -o v.vcf.gz 2>/dev/null; bcftools index v.vcf.gz',
]
CMDS = [
    "printf 'a b' | tr ' ' '_'",
    # diff and cmp (GNU diffutils): the same bytes as the native programs print
    "bcftools view -H v.vcf.gz | head -n 20 > v20.txt; bcftools view -H v.vcf.gz | sed -n '3,22p' > v22.txt; diff v20.txt v22.txt | md5sum; diff -u v20.txt v22.txt | tail -n +3 | md5sum; cmp -s v20.txt v22.txt; echo $?",
    "diff <(samtools view s.bam | cut -f 1-4 | head -n 3000) <(samtools view s.bam | cut -f 1-4 | sed -n '2,3001p'); echo $?",
    "diff data/NA12878_R1.fastq data/NA12878_R2.fastq | md5sum; diff -y --suppress-common-lines -W 60 data/NA12878_R1.fastq data/NA12878_R2.fastq | head -n 3; cmp data/NA12878_R1.fastq data/NA12878_R2.fastq | sed 's/char/byte/'",
    "printf 'hello' | fold -w 2",
    "printf 'hello' | head -c 3",
    "printf 'hello' | tail -c 3",
    "printf 'a\\tb' | cut -f2",
    "printf 'a\\nb' | paste -sd, -",
    "printf 'b\\na' | sort",
    "printf 'a\\na' | uniq -c",
    "printf 'x' | tee t.txt; printf '|'; cat t.txt",
    "printf 'a b' | wc -w",
    "seq -s, 3",
    "printf 'x' | md5sum",
    "printf 'abc' | grep -o b",
    "printf 'abc' | grep b",
    "echo '{\"a\":\"x\"}' | jq -j .a",
    "jq -n -j '\"x\",\"y\"'",
    "jq -n -r '\"x\"'",
    "awk 'BEGIN{ORS=\"\"; print \"x\"}'",
    "awk 'BEGIN{printf \"%s|%d\", \"a\", 3}'",
    "printf 'abc' | sed s/b/B/",
    "bcftools query -f '%POS' -r human_CYP2C19:11616 v.vcf.gz",
    "bcftools query -f '[%GT]' -r human_CYP2C19:11616 v.vcf.gz | tr '/' '|'",
    "samtools view -c s.bam | tr -d '\\n'",
    "printf 'abc' | bgzip -c | bgzip -dc",
    "date +%Y | tr -d '\\n' | wc -c",
    "printf '%s' abc | tr a-z A-Z; echo '|'",
    "x=$(printf 'a\\nb\\nc' | tr '\\n' ','); echo \"[$x]\"",
    "echo \"$(seq 3 | tr '\\n' ' ')|\"",
    "grep -v '>' data/reference.fa | head -1 | tr -d '\\n' | wc -c",
    "grep -v '>' data/reference.fa | tr -d '\\n' | head -c 20",
    "grep -v '>' data/reference.fa | tr -d '\\n' | fold -w 60 | head -2",
    "grep -v '>' data/reference.fa | tr -d '\\n' | wc -c",
    "cut -f1,2 data/reference.fa.fai | tr '\\t' '=' | tr '\\n' ';'",
    "head -c 100 data/reference.fa | tail -c 10",
    "printf 'a,b,c' | tr ',' '\\n' | wc -l",
    "printf 'one\\ntwo' | tr a-z A-Z | tail -n 1",
    "printf 'x y' | tr ' ' '\\n' | sort -r | tr '\\n' ' '",
    "seq 5 | paste -sd+ - | tr -d '\\n'; echo ' = 15'",
    "printf 'k\\tv' | awk -F'\\t' '{printf \"%s=%s\", $1, $2}' | tr = :",
    "printf '3\\n1\\n2' | sort -n | head -c 3 | tr '\\n' '-'",
    "echo -n abc | wc -c; echo -n abc | tr -d b | wc -c",
    "samtools faidx data/reference.fa human_CYP2C19:11610-11620 | tail -1 | tr -d '\\n' | tr ACGT TGCA",
    # speed with an unbuffered stdout: the whole of a FASTQ file through each program
    "sort data/NA12878_R1.fastq | md5sum",
    "cut -c1-10 data/NA12878_R1.fastq | md5sum",
    "tr ACGT TGCA < data/NA12878_R1.fastq | md5sum",
    "grep -v '>' data/reference.fa | tr -d '\\n' | fold -w 1 | sort | uniq -c",
    "head -n 8000 data/NA12878_R1.fastq | tail -n 4000 | md5sum",
    "paste - - - - < data/NA12878_R1.fastq | cut -f 2 | sort | uniq -c | sort -k1,1nr | head -3",
    "seq 1 20000 | wc -l; seq 1 20000 | shuf --random-source=data/reference.fa | sort -n | tail -1",
    "cat data/NA12878_R1.fastq data/NA12878_R2.fastq | wc -l; tee copy.fq < data/NA12878_R1.fastq | md5sum; md5sum copy.fq",
    "comm -12 data/MD5SUMS data/MD5SUMS | wc -l; join data/reference.fa.fai data/reference.fa.fai | wc -l; date +%Y | wc -c",
    "awk 'NR%4==2' data/NA12878_R1.fastq | fold -w 38 | wc -l",
    # a program starts afresh each time, as a process does: an option of one run must not be at work in the next
    # (minimap2 kept the read group of -R and wrote it into every later alignment)
    "minimap2 -ax sr -R '@RG\\tID:lane1\\tSM:NA12878' data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq 2>/dev/null | grep -c 'RG:Z:lane1'; minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq 2>/dev/null | grep -v '^@PG' | md5sum",
    "samtools view -h -o rg.sam s.bam && samtools view -c -f 4 rg.sam && samtools view -c rg.sam && samtools flagstat s.bam | head -1 && samtools view -H s.bam | grep -c '^@SQ'",
    "bcftools view -H -i 'QUAL>100' v.vcf.gz | wc -l; bcftools view -H v.vcf.gz | wc -l; bcftools query -f '%POS\\n' v.vcf.gz | head -2",
]
import shutil
missing = [t for t in ('bash', 'minimap2', 'samtools', 'bcftools', 'bgzip', 'jq', 'awk') if not shutil.which(t, path=(NATIVE + ':' if NATIVE else '') + os.environ['PATH'])]
if missing:
    print('This test compares the page with native programs, and these were not found: ' + ', '.join(missing) + '.\nGive their folders as NATIVE_TOOLS=dir1:dir2 (versions as in the page: minimap2 2.22, samtools 1.17, bcftools 1.10, jq 1.7).')
    sys.exit(2)
os.makedirs(WORK, exist_ok=True)
subprocess.run(f'rm -rf "{WORK}"/* && cp -r "{ROOT}/data" "{WORK}/"', shell=True, check=True)
env = dict(os.environ, PATH=(NATIVE + ':' if NATIVE else '') + os.environ['PATH'], LC_ALL='C')
def native(c):
    r = subprocess.run(['bash', '-c', c], cwd=WORK, env=env, capture_output=True, text=True)
    return r.stdout + r.stderr
for c in SETUP:
    native(c)
bad = 0
with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        for c in SETUP:
            term(page, c)
        import time
        for c in CMDS:
            t0 = time.time()
            got = term(page, c)['text']
            dt = time.time() - t0
            want = native(c)
            ok = got.rstrip('\n') == want.rstrip('\n')   # the terminal ends the last line itself
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + f'{dt:4.1f}s ' + c + ('' if ok else f'\n       page:   {got!r}\n       native: {want!r}'), flush=True)
        print(f'\n{bad} BAD of {len(CMDS)}')
        b.close()
    finally:
        srv.terminate()
