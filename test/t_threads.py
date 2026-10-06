import sys, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8823
CMDS = [
    'minimap2 -t 4 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mm.sam 2> mm.log; tail -1 mm.log; ls -l mm.sam',
    'samtools sort -@ 4 -o mm.bam mm.sam && samtools index -@ 2 mm.bam && samtools flagstat -@ 2 mm.bam | head -3',
    'bcftools mpileup --threads 2 -Ou -f data/reference.fa mm.bam | bcftools call --threads 2 -mv -Oz -o v.vcf.gz; bcftools index v.vcf.gz; ls -l v.vcf.gz*',
    'bcftools view -H -r human_CYP2C19:11616 v.vcf.gz | cut -f1-6,10',
    'echo "Variants: $(bcftools view -H v.vcf.gz | wc -l), PASS at QUAL>=30: $(bcftools view -H -i "QUAL>=30" v.vcf.gz | wc -l)"',
    'cd data && md5sum -c MD5SUMS; cd ..',
    'md5sum data/reference.fa; md5sum < data/reference.fa; samtools view mm.bam | md5sum',
    'date; date +%F; date -u +%Y-%m-%dT%H:%M:%SZ',
    'gzip -c mm.sam > mm.sam.gz; ls -l mm.sam.gz; zcat mm.sam.gz | head -1 | cut -c1-30; gunzip -c mm.sam.gz | wc -l; zgrep -c "^@SQ" mm.sam.gz',
    'cp mm.sam copy.sam && gzip copy.sam && ls copy.sam* && gunzip copy.sam.gz && ls copy.sam*',
    'sed -i "s/A/C/" data/reference.fa; echo "exit $?"; md5sum data/reference.fa',
    'echo x > data/reference.fa; echo "exit $?"',
    'seqtk seq -A data/NA12878_R1.fastq > data/NA12878_R1.fastq; echo "exit $?"; head -c 20 data/NA12878_R1.fastq; echo',
    'fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o data/NA12878_R1.fastq -O x2.fq -h f.html -j f.json 2>&1 | tail -2; echo "exit $?"; md5sum data/NA12878_R1.fastq',
    'samtools faidx data/reference.fa; ls data',
    'for f in data/*.fastq; do n=$(( $(wc -l < "$f") / 4 )); echo "$(basename "$f"): $n reads"; done',
    'tree -L 1 | tail -4; find . -name "*.bam" -size +100k -exec ls -l {} \; | wc -l; stat -c %s mm.bam',
    'python3 --version; bwa mem; fastqc x; wget http://x; conda install bwa',
    'time samtools view -c mm.bam; nproc; uname -a; which samtools; type cd',
    'printf "a\\tb\\n1\\t2\\n" > t.tsv && cat t.tsv && column -t t.tsv',
    'ls; ls -F | head -3; ls -l data | head -3',
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
            print(f'$ {c}\n  -> exit {r["code"]} ({time.time()-t0:.1f} s)\n' + '\n'.join('     ' + l[:200] for l in txt.split('\n')[-9:]) + '\n', flush=True)
        print('\n'.join(l for l in logs if 'PAGEERROR' in l)[:2000])
        b.close()
    finally:
        srv.terminate()
