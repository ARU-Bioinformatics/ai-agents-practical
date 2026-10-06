"""Every program of the terminal really runs in the browser, on the course data. Prints what each did."""
import sys, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8821
CMDS = [
    'help',
    'cd ~ && ls -l data',
    'head -4 data/NA12878_R1.fastq',
    'fastp --version',
    'fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o trimmed_R1.fastq -O trimmed_R2.fastq -h fastp.html -j fastp.json',
    'ls -l fastp.html fastp.json trimmed_R1.fastq',
    'jq .summary.before_filtering fastp.json',
    "jq -r '.filtering_result | to_entries[] | \"\\(.key)\\t\\(.value)\"' fastp.json",
    'bowtie2-build --version | head -2',
    'bowtie2-build data/reference.fa reference',
    'ls reference*',
    'bowtie2 -x reference -1 data/NA12878_R1.fastq -2 data/NA12878_R2.fastq -S bt2.sam',
    'bowtie2 -x reference -1 data/NA12878_R1.fastq -2 data/NA12878_R2.fastq | samtools sort -o bt2.bam',
    'samtools index bt2.bam && samtools flagstat bt2.bam | head -5',
    'grep -v "^@" bt2.sam | md5sum',
    'minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq | samtools sort -o mm2.bam',
    'samtools index mm2.bam && bcftools mpileup -f data/reference.fa mm2.bam | bcftools call -mv -Oz -o mm2.vcf.gz',
    'bcftools view -H mm2.vcf.gz | wc -l',
    'bcftools view -H mm2.vcf.gz | grep -w 11616',
    'bcftools view mm2.vcf.gz > mm2.vcf; ls -l mm2.vcf; grep -c "^#" mm2.vcf',
    'seqtk fqchk data/NA12878_R1.fastq | head -3',
    'bedtools --version',
    'bedtools genomecov -ibam mm2.bam -bg | head -3',
    'shuf -n 2 -o shuf.txt --random-source=data/reference.fa data/MD5SUMS; seq 5 | shuf --random-source=data/reference.fa | fold -w 3 | head -3',
    'bowtie2 --bogus-option',
    # the programs not used above: bgzip, tabix, and the rest of the GNU tools
    'bgzip -c data/reference.fa > ref.fa.gz && zcat ref.fa.gz | head -1 && tabix -p vcf mm2.vcf.gz && tabix mm2.vcf.gz human_CYP2C19:11616-11616 | cut -f 1,2,4,5',
    'cat data/MD5SUMS | tail -2 | cut -c 1-8 | tr a-f A-F | tee tee.txt | paste -sd, -; cat tee.txt | wc -l',
    'grep -v "^#" mm2.vcf | cut -f 1 | sort | uniq -c',
    "sed -n '1p' data/reference.fa; awk 'NR % 4 == 2 { n += length($0) } END { print n, NR / 4 }' data/NA12878_R1.fastq",
    "printf 'a 1\\nb 2\\n' > j1.txt; printf 'a x\\nc y\\n' > j2.txt; join j1.txt j2.txt; comm -12 j1.txt j1.txt | wc -l; comm -3 j1.txt j2.txt | wc -l",
    'date +%Y-%m-%d | grep -c "^20"',
]
with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        for c in CMDS:
            t0 = time.time()
            r = term(page, c)
            txt = r['text'].strip()
            print(f'$ {c}\n  -> exit {r["code"]} ({time.time()-t0:.1f} s)\n' + '\n'.join('     ' + l for l in txt.split('\n')[-12:]) + '\n', flush=True)
        print(page.evaluate("JSON.stringify(Array.from(MG.app.fs.entries).filter(([k, e]) => k.startsWith('/home/student/') && e.kind !== 'dir' && !e.protected).map(([k, e]) => [k.slice(14), e.kind, MG.app.fs.size(e)]))"))
        print('\n'.join(l for l in logs if 'PAGEERROR' in l or 'rror' in l)[:2000])
        b.close()
    finally:
        srv.terminate()
