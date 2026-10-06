"""The numbers the instructions quote, from the programs as they run in the page."""
import sys, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8841
CMDS = [
    'ls -l data',
    'cat data/README.md',
    'wc -l data/*.fastq',
    'echo $(( $(wc -l < data/NA12878_R1.fastq) / 4 ))',
    'head -4 data/NA12878_R1.fastq',
    "awk 'NR % 4 == 2 { n[length($0)]++ } END { for (l in n) print l, n[l] }' data/NA12878_R1.fastq",
    'cd data && md5sum -c MD5SUMS; cd ..; cat data/MD5SUMS',
    "grep '>' data/reference.fa",
    'samtools faidx data/reference.fa && cat data/reference.fa.fai',
    'fastp --version; minimap2 --version; bowtie2 --version | head -1; samtools --version | head -2; bcftools --version | head -2; bgzip --version | head -1; seqtk 2>&1 | head -3; bedtools --version; jq --version; awk --version | head -1; grep --version | head -1; sed --version | head -1; sort --version | head -1',
    'fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o trimmed_R1.fastq -O trimmed_R2.fastq -h fastp.html -j fastp.json',
    'jq .summary fastp.json',
    'jq .filtering_result fastp.json',
    'jq .duplication.rate fastp.json; jq .insert_size.peak fastp.json; jq ".adapter_cutting | {adapter_trimmed_reads, adapter_trimmed_bases}" fastp.json; jq .command fastp.json',
    'md5sum fastp.json trimmed_R1.fastq; wc -l trimmed_R1.fastq',
    'fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o trimmed_R1.fastq -O trimmed_R2.fastq -h fastp.html -j fastp.json 2>/dev/null; md5sum fastp.json trimmed_R1.fastq; jq .duplication.rate fastp.json; jq .insert_size.peak fastp.json',
    'grep -c "at 20" fastp.html; grep -o "fastp report</title>" fastp.html; grep -o "<script src=[^>]*>" fastp.html',
    # minimap2
    'minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam 2> minimap2.log; tail -3 minimap2.log',
    'samtools sort -o mapped.bam mapped.sam && samtools index mapped.bam && samtools flagstat mapped.bam',
    'samtools idxstats mapped.bam',
    'bcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz && bcftools index variants.vcf.gz; ls -l variants.vcf.gz*',
    'bcftools view -H variants.vcf.gz | wc -l; bcftools view -H -i "QUAL>=30" variants.vcf.gz | wc -l; bcftools view -H -i "QUAL>=20" variants.vcf.gz | wc -l',
    'bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz',
    "bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL\\t%DP\\t[%GT]\\n' -r human_CYP2C19:11616 variants.vcf.gz",
    'bcftools view -h variants.vcf.gz | grep -i -E "date|Command|Version"',
    'md5sum mapped.bam variants.vcf.gz; bcftools view -H variants.vcf.gz | md5sum',
    'bcftools stats variants.vcf.gz | grep "^SN"',
    'samtools depth -r human_CYP2C19:11616-11616 mapped.bam; samtools view -c mapped.bam human_CYP2C19:11616-11616',
    'bcftools view -H variants.vcf.gz | cut -f 1 | sort | uniq -c',
    # a second run of the same commands
    'mkdir again && cd again && minimap2 -ax sr ../data/reference.fa ../data/NA12878_R1.fastq ../data/NA12878_R2.fastq > mapped.sam 2> minimap2.log && samtools sort -o mapped.bam mapped.sam && samtools index mapped.bam && bcftools mpileup -f ../data/reference.fa mapped.bam 2>/dev/null | bcftools call -mv -Oz -o variants.vcf.gz 2>/dev/null; md5sum mapped.bam variants.vcf.gz; bcftools view -H variants.vcf.gz | md5sum; cd ..',
    'samtools view -H mapped.bam; samtools view -H again/mapped.bam | tail -2',
    'sleep 2; mkdir again2 && cp -r data again2/ && cd again2 && minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam 2> minimap2.log && samtools sort -o mapped.bam mapped.sam && samtools index mapped.bam && bcftools mpileup -f data/reference.fa mapped.bam 2>/dev/null | bcftools call -mv -Oz -o variants.vcf.gz 2>/dev/null; md5sum mapped.bam variants.vcf.gz; bcftools view -H variants.vcf.gz | md5sum; cd ..',
    'zcat variants.vcf.gz > a.vcf; zcat again2/variants.vcf.gz > b.vcf; diff a.vcf b.vcf',
    # bowtie2
    'bowtie2-build data/reference.fa reference > bt2-build.log 2>&1; ls reference*; tail -1 bt2-build.log',
    'bowtie2 -x reference -1 data/NA12878_R1.fastq -2 data/NA12878_R2.fastq -S bt2.sam',
    'samtools sort -o bt2.bam bt2.sam && samtools index bt2.bam && samtools flagstat bt2.bam | head -9',
    'bcftools mpileup -f data/reference.fa bt2.bam 2>/dev/null | bcftools call -mv -Oz -o bt2.vcf.gz 2>/dev/null; bcftools index bt2.vcf.gz; bcftools view -H bt2.vcf.gz | wc -l; bcftools view -H -i "QUAL>=30" bt2.vcf.gz | wc -l; bcftools view -H -r human_CYP2C19:11616 bt2.vcf.gz',
    # trimmed reads
    'minimap2 -ax sr data/reference.fa trimmed_R1.fastq trimmed_R2.fastq 2>/dev/null | samtools sort -o tmm.bam && samtools index tmm.bam && samtools flagstat tmm.bam | head -8 | tail -2; bcftools mpileup -f data/reference.fa tmm.bam 2>/dev/null | bcftools call -mv -Oz -o tmm.vcf.gz 2>/dev/null; bcftools index tmm.vcf.gz; bcftools view -H tmm.vcf.gz | wc -l; bcftools view -H -i "QUAL>=30" tmm.vcf.gz | wc -l; bcftools view -H -r human_CYP2C19:11616 tmm.vcf.gz',
    'bowtie2 -x reference -1 trimmed_R1.fastq -2 trimmed_R2.fastq 2> tbt.log | samtools sort -o tbt.bam && samtools index tbt.bam; tail -1 tbt.log; bcftools mpileup -f data/reference.fa tbt.bam 2>/dev/null | bcftools call -mv -Oz -o tbt.vcf.gz 2>/dev/null; bcftools index tbt.vcf.gz; bcftools view -H tbt.vcf.gz | wc -l; bcftools view -H -i "QUAL>=30" tbt.vcf.gz | wc -l; bcftools view -H -r human_CYP2C19:11616 tbt.vcf.gz',
    'for f in variants bt2 tmm tbt; do echo "$f: $(bcftools view -H $f.vcf.gz | wc -l) variants; at 11616: $(bcftools query -f "%REF>%ALT QUAL=%QUAL DP=%DP [%GT]" -r human_CYP2C19:11616 $f.vcf.gz)"; done',
    'bcftools isec -n=2 -c none variants.vcf.gz bt2.vcf.gz 2>&1 | wc -l',
    'du -sh .; ls',
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
            print(f'$ {c}\n  -> exit {r["code"]} ({time.time()-t0:.1f} s)\n' + '\n'.join('     ' + l[:400] for l in r['text'].rstrip().split('\n')[-45:]) + '\n', flush=True)
        print('\n'.join(l for l in logs if 'PAGEERROR' in l)[:2000])
        b.close()
    finally:
        srv.terminate()
