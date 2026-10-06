"""What AI agents typically write for this task – explorations, quality control, mapping, calling,
checks and scripts in the idioms language models use – must run in the page's terminal.
Each case: (command, expected exit status or None, regular expression the output must match or None).
Prints every case that does not do what real bash and the real programs would do."""
import sys, time, re, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8860

R1, R2, REF = 'data/NA12878_R1.fastq', 'data/NA12878_R2.fastq', 'data/reference.fa'
CASES = [
    # ---- looking around ----
    ('mkdir -p ~/t && cd ~/t && cp -r ~/data . && ls', 0, r'^data\s*$'),
    ('pwd', 0, r'/home/student/t'),
    ('ls -la', 0, r'data'),
    ('ls -lh data/', 0, r'NA12878_R1\.fastq'),
    ('ls -1 data | wc -l', 0, r'^\s*6\s*$'),
    ('head -n 8 data/NA12878_R1.fastq', 0, r'^@'),
    ('wc -l data/*.fastq', 0, r'14076.*\n.*14076.*\n\s*28152 total'),
    ('grep -c "^>" data/reference.fa', 0, r'^2\s*$'),
    ("grep '>' data/reference.fa", 0, r'human_CYP2C19'),
    ('head -c 100 data/reference.fa', 0, r'^>human_CYP2C19'),
    ("awk 'NR%4==2 {print length($0)}' data/NA12878_R1.fastq | sort -n | uniq -c", 0, r'3519 76'),
    ('echo "Reads: $(($(wc -l < data/NA12878_R1.fastq) / 4))"', 0, r'Reads: 3519'),
    ('echo "Number of read pairs: $(( $(cat data/NA12878_R1.fastq | wc -l) / 4 ))"', 0, r'pairs: 3519'),
    ('which minimap2 bowtie2 samtools bcftools fastp', 0, r'minimap2'),
    ('command -v bwa || echo "bwa not found"', 0, r'bwa not found'),
    ('for t in fastp minimap2 bowtie2 samtools bcftools bwa gatk; do if command -v $t >/dev/null 2>&1; then echo "$t: yes"; else echo "$t: no"; fi; done', 0, r'fastp: yes\nminimap2: yes\nbowtie2: yes\nsamtools: yes\nbcftools: yes\nbwa: no\ngatk: no'),
    ('samtools --version | head -n 1', 0, r'samtools 1\.17'),
    ('bcftools --version | head -n 2', 0, r'bcftools 1\.10'),
    ('minimap2 --version', 0, r'2\.22'),
    ('bowtie2 --version | head -n 1', 0, r'version 2\.4\.2'),
    ('fastp --version 2>&1', 0, r'fastp 0\.20\.1'),
    ('samtools 2>&1 | head -5', None, r'samtools'),
    ('bcftools 2>&1 | grep -i version', None, r'[Vv]ersion'),
    ('nproc', 0, r'^\d+\s*$'),
    ('uname -a', 0, r'.'),
    ('date', 0, r'20\d\d'),
    ('date +%Y-%m-%d', 0, r'^20\d\d-\d\d-\d\d\s*$'),
    ('echo "[$(date "+%Y-%m-%d %H:%M:%S")] start"', 0, r'^\[20\d\d-\d\d-\d\d \d\d:\d\d:\d\d\] start'),
    ('du -sh data', 0, r'data'),
    ('file data/reference.fa', 0, r'.'),
    ('md5sum data/*.fastq data/reference.fa', 0, r'd2b8ddb488975fa5ef18e6e59edb5681'),
    ('cat data/MD5SUMS && (cd data && md5sum -c MD5SUMS)', 0, r'OK[\s\S]*OK[\s\S]*OK'),
    ('env | head -3; echo $HOME; echo $PWD; echo $USER', 0, r'/home/student'),
    # ---- quality control ----
    (f'fastp -i {R1} -I {R2} -o trimmed_R1.fastq -O trimmed_R2.fastq --html fastp.html --json fastp.json --thread 4', 0, r'Read1 before filtering'),
    (f'fastp -i {R1} -I {R2} -o t1.fq -O t2.fq --detect_adapter_for_pe -q 20 -l 36 -w 4 -h f2.html -j f2.json 2> fastp.log; echo "exit $?"; tail -3 fastp.log', 0, r'exit 0'),
    (f'fastp --in1 {R1} --in2 {R2} --out1 a1.fastq.gz --out2 a2.fastq.gz -j f3.json -h f3.html 2>/dev/null && ls -l a1.fastq.gz && zcat a1.fastq.gz | head -2', 0, r'^.*a1\.fastq\.gz[\s\S]*@'),
    ("jq '.summary' fastp.json", 0, r'"before_filtering"'),
    ("jq -r '.summary.after_filtering.total_reads' fastp.json", 0, r'^6170\s*$'),
    ('jq -r ".filtering_result | to_entries[] | \\"\\(.key)\\t\\(.value)\\"" fastp.json', 0, r'passed_filter_reads\t6170'),
    ("jq '.summary.before_filtering.q30_rate, .summary.after_filtering.q30_rate' fastp.json", 0, r'0\.820751\n0\.898727'),
    ('grep -A 6 "Filtering result" fastp.log', 0, r'reads passed filter'),
    ('seqtk fqchk data/NA12878_R1.fastq | head -3', 0, r'min_len: 76'),
    ('seqtk comp data/reference.fa | cut -f 1-2', 0, r'human_CYP2C19\t30000'),
    ('ls -lh trimmed_R1.fastq trimmed_R2.fastq fastp.html fastp.json', 0, r'fastp\.html'),
    # ---- mapping with minimap2 ----
    (f'minimap2 -ax sr {REF} {R1} {R2} > aligned.sam', 0, None),
    ('ls -l aligned.sam && head -3 aligned.sam', 0, r'@SQ\tSN:human_CYP2C19\tLN:30000'),
    ('samtools view -bS aligned.sam > aligned.bam && ls -l aligned.bam', 0, r'aligned\.bam'),
    ('samtools view -b -o aligned2.bam aligned.sam; samtools view -c aligned2.bam', 0, r'^70\d\d\s*$'),
    ('samtools sort aligned.bam -o sorted.bam && samtools index sorted.bam && ls sorted.bam*', 0, r'sorted\.bam\s+sorted\.bam\.bai|sorted\.bam\nsorted\.bam\.bai'),
    ('samtools sort -O bam -T tmp -o sorted2.bam aligned.bam && samtools quickcheck sorted2.bam && echo fine', 0, r'fine'),
    (f"minimap2 -t 4 -a -x sr -R '@RG\\tID:NA12878\\tSM:NA12878\\tPL:ILLUMINA' {REF} {R1} {R2} 2> minimap2.log | samtools sort -@ 4 -o rg.bam - && samtools index rg.bam && samtools view -H rg.bam | grep '^@RG'", 0, r'@RG\tID:NA12878\tSM:NA12878\tPL:ILLUMINA'),
    (f'minimap2 -ax sr {REF} {R1} {R2} 2>/dev/null | samtools view -b - | samtools sort -o piped.bam - ; samtools index piped.bam; samtools flagstat piped.bam', 0, r'6817 \+ 0 mapped \(96\.86%'),
    (f'minimap2 -ax sr {REF} {R1} {R2} | samtools view -Sb - > unsorted.bam 2> view.log; samtools sort unsorted.bam > sorted3.bam; samtools view -c sorted3.bam', 0, r'^70\d\d\s*$'),
    ('samtools flagstat sorted.bam', 0, r'properly paired \(94\.77%'),
    ('samtools flagstat sorted.bam > flagstat.txt; cat flagstat.txt | grep "mapped ("', 0, r'96\.86%'),
    ('samtools stats sorted.bam | grep ^SN | cut -f 2- | head -8', 0, r'raw total sequences:\t7038'),
    ('samtools idxstats sorted.bam', 0, r'human_CYP2C19\t30000\t\d+\t\d+'),
    ('samtools view -c -F 4 sorted.bam', 0, r'^6817\s*$'),
    ('samtools view -c -f 4 sorted.bam', 0, r'^221\s*$'),
    ('samtools view -H sorted.bam', 0, r'@HD\tVN:\S+\tSO:coordinate'),
    ('samtools view sorted.bam | head -2 | cut -f 1-6', 0, r'human_CYP2C'),
    ('samtools view sorted.bam human_CYP2C19:11616-11616 | wc -l', 0, r'^\s*1\d\d\s*$'),
    ('samtools depth -r human_CYP2C19:11616-11616 sorted.bam', 0, r'human_CYP2C19\t11616\t\d+'),
    ("samtools depth sorted.bam | awk '{sum+=$3} END {print \"Average depth:\", sum/NR}'", 0, r'Average depth: \d+'),
    ("samtools depth -a sorted.bam | awk '{s+=$3; n++} END {printf \"mean depth %.1f over %d positions\\n\", s/n, n}'", 0, r'mean depth \d+\.\d over 56000 positions'),
    ('samtools coverage sorted.bam', 0, r'#rname'),
    ('samtools faidx data/reference.fa && cat data/reference.fa.fai', 0, r'human_CYP2C19\t30000'),
    ('samtools faidx data/reference.fa human_CYP2C19:11610-11620', 0, r'>human_CYP2C19:11610-11620\n[ACGT]{11}'),
    ('samtools mpileup -f data/reference.fa -r human_CYP2C19:11616-11616 sorted.bam 2>/dev/null | cut -f 1-4', 0, r'human_CYP2C19\t11616\tG\t\d+'),
    ('samtools view -q 20 -b sorted.bam > q20.bam && samtools view -c q20.bam', 0, r'^\d+\s*$'),
    ('samtools sort -n -o namesorted.bam aligned.bam && samtools fixmate -m namesorted.bam fixmate.bam && samtools sort -o positionsorted.bam fixmate.bam && samtools markdup positionsorted.bam markdup.bam && samtools index markdup.bam && samtools flagstat markdup.bam | grep duplicates', 0, r'\d+ \+ 0 duplicates'),
    ('samtools markdup -r -s positionsorted.bam dedup.bam 2>&1 | tail -4; samtools view -c dedup.bam', 0, r'\d+'),
    # ---- mapping with Bowtie 2 ----
    ('bowtie2-build data/reference.fa ref_index > /dev/null 2>&1; echo "exit $?"; ls ref_index*', 0, r'exit 0[\s\S]*ref_index\.1\.bt2'),
    ('mkdir -p index && bowtie2-build -q data/reference.fa index/ref && ls index | wc -l', 0, r'^\s*6\s*$'),
    (f'bowtie2 -p 4 -x ref_index -1 {R1} -2 {R2} --rg-id NA12878 --rg SM:NA12878 2> bowtie2.log | samtools sort -o bt2.bam && samtools index bt2.bam; cat bowtie2.log | tail -1', 0, r'98\.00% overall alignment rate'),
    (f'bowtie2 --very-sensitive -x index/ref -1 {R1} -2 {R2} -S bt2vs.sam 2>&1 | tail -1', 0, r'overall alignment rate'),
    (f'bowtie2 --threads 2 --local -x ref_index -1 {R1} -2 {R2} -S bt2local.sam; samtools view -c -F 4 bt2local.sam', 0, r'^\d+\s*$'),
    ('bowtie2-inspect -n ref_index 2>&1 | head -3', None, r'.'),
    # ---- variant calling ----
    ('bcftools mpileup -Ou -f data/reference.fa sorted.bam | bcftools call -mv -Oz -o variants.vcf.gz && bcftools index variants.vcf.gz && ls variants.vcf.gz*', 0, r'variants\.vcf\.gz\.csi'),
    ('bcftools view -H variants.vcf.gz | wc -l', 0, r'^\s*60\s*$'),
    ('bcftools view -r human_CYP2C19:11616 variants.vcf.gz | grep -v "^##"', 0, r'human_CYP2C19\t11616\t\.\tG\tA\t222'),
    ('bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz | cut -f 1,2,4,5,6,10', 0, r'0/1:255,0,255'),
    ('bcftools mpileup --threads 4 -Ou -a AD,DP -f data/reference.fa sorted.bam 2>/dev/null | bcftools call --threads 4 -m -v -Oz -o ann.vcf.gz; bcftools index -t ann.vcf.gz; ls ann.vcf.gz.tbi', 0, r'ann\.vcf\.gz\.tbi'),
    ("bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL[\\t%GT\\t%AD\\t%DP]\\n' -r human_CYP2C19:11616 ann.vcf.gz", 0, r'human_CYP2C19\t11616\tG\tA\t\d+(\.\d+)?\t0/1\t\d+,\d+\t\d+'),
    ('tabix -p vcf -f variants.vcf.gz && tabix variants.vcf.gz human_CYP2C19:11616-11616 | cut -f 1-6', 0, r'human_CYP2C19\t11616'),
    ('bcftools stats variants.vcf.gz | grep "^SN"', 0, r'number of SNPs:\t\d+'),
    ("bcftools filter -i 'QUAL>=20 && DP>=10' -Oz -o filtered.vcf.gz variants.vcf.gz && bcftools index filtered.vcf.gz && bcftools view -H filtered.vcf.gz | wc -l", 0, r'^\s*\d+\s*$'),
    ("bcftools filter -e 'QUAL<20' variants.vcf.gz | grep -vc '^#'", 0, r'^30\s*$'),
    ("bcftools view -i 'QUAL>=30' variants.vcf.gz | grep -v '^#' | wc -l", 0, r'^\s*27\s*$'),
    ('bcftools view -v snps variants.vcf.gz | grep -v "^#" | wc -l', 0, r'^\s*\d+\s*$'),
    ('bcftools view -v indels -H variants.vcf.gz | wc -l', 0, r'^\s*\d+\s*$'),
    ('bcftools norm -f data/reference.fa -Oz -o norm.vcf.gz variants.vcf.gz 2>&1 | tail -1', 0, r'total/split/realigned/skipped'),
    ('zcat variants.vcf.gz | grep -v "^##" | head -3 | cut -f 1-5', 0, r'#CHROM\tPOS\tID\tREF\tALT'),
    ("zgrep -v '^#' variants.vcf.gz | awk '$2==11616'", 0, r'human_CYP2C19\t11616'),
    ("gunzip -c variants.vcf.gz | awk -F'\\t' '!/^#/ && $1==\"human_CYP2C19\" && $2==11616 {print $1, $2, $4, $5, $6, $10}'", 0, r'human_CYP2C19 11616 G A 222 0/1'),
    ('bcftools view -t human_CYP2C19:11616 -H variants.vcf.gz | wc -l', 0, r'^\s*1\s*$'),
    ('bcftools mpileup -f data/reference.fa -r human_CYP2C19:11616 -a AD sorted.bam 2>/dev/null | bcftools call -m | bcftools view -H | cut -f 1,2,4,5,10', 0, r'human_CYP2C19\t11616\tG\tA\t0/1'),
    ('bcftools view variants.vcf.gz > variants.vcf && bgzip -c variants.vcf > again.vcf.gz && bcftools index again.vcf.gz && bcftools view -H again.vcf.gz | wc -l', 0, r'^\s*60\s*$'),
    ('bcftools view -Oz -o v2.vcf.gz variants.vcf; bcftools view -h v2.vcf.gz | tail -1 | cut -f 10', 0, r'sorted\.bam'),
    ('bcftools view -H variants.vcf.gz | cut -f 1 | sort | uniq -c', 0, r'18 human_CYP2C19\n\s*42 human_CYP2C9'),
    ("bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL\\n' variants.vcf.gz | sort -k5,5nr | head -3", 0, r'\t22[0-9]'),
    ("bcftools query -l variants.vcf.gz", 0, r'sorted\.bam'),
    ('bcftools view -H variants.vcf.gz | md5sum', 0, r'^[0-9a-f]{32}'),
    ('bedtools genomecov -ibam sorted.bam -bg | head -2', 0, r'human_CYP2C'),
    ('bedtools bamtobed -i sorted.bam | head -2', 0, r'human_CYP2C'),
    # ---- shell idioms in the middle of a run ----
    ('GENOTYPE=$(bcftools query -f "[%GT]\\n" -r human_CYP2C19:11616 variants.vcf.gz); echo "Genotype: ${GENOTYPE}"; if [ "$GENOTYPE" = "0/1" ]; then echo heterozygous; elif [ "$GENOTYPE" = "1/1" ]; then echo homozygous; else echo other; fi', 0, r'Genotype: 0/1\nheterozygous'),
    ('N=$(bcftools view -H variants.vcf.gz | wc -l); echo "Total variants: ${N}"; [ "$N" -gt 0 ] && echo "ok"', 0, r'Total variants: 60\nok'),
    ('case "$(bcftools query -f "[%GT]" -r human_CYP2C19:11616 variants.vcf.gz)" in "0/1") echo het;; "1/1") echo hom;; *) echo other;; esac', 0, r'^het\s*$'),
    ('{ echo "# Summary"; echo "Variants: $(bcftools view -H variants.vcf.gz | wc -l)"; samtools flagstat sorted.bam | grep "mapped ("; } > report.txt; cat report.txt', 0, r'# Summary\nVariants: 60\n6817'),
    ('cat <<EOF > summary.txt\nSample: NA12878\nVariants: $(bcftools view -H variants.vcf.gz | wc -l)\nSite: $(bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz | cut -f 1,2,4,5)\nEOF\ncat summary.txt', 0, r'Sample: NA12878\nVariants: 60\nSite: human_CYP2C19\t11616\tG\tA'),
    ('printf "%s\\t%s\\n" "variants" "$(bcftools view -H variants.vcf.gz | wc -l)" | tee counts.tsv', 0, r'variants\t60'),
    ('test -s variants.vcf.gz && echo "exists and not empty"', 0, r'exists and not empty'),
    ('[[ -f variants.vcf.gz && -f variants.vcf.gz.csi ]] && echo indexed', 0, r'indexed'),
    ('ls *.bam | while read f; do echo "$f $(samtools view -c "$f")"; done | head -3', 0, r'\.bam \d+'),
    ('for f in sorted.bam bt2.bam; do echo "== $f"; samtools flagstat $f | sed -n "7p"; done', 0, r'== sorted\.bam\n.*mapped[\s\S]*== bt2\.bam'),
    ('ls nothing_here 2>/dev/null || echo "no such file"', 0, r'no such file'),
    ('samtools view -c missing.bam 2>&1; echo "status: $?"', 0, r'status: 1'),
    ('rm -f aligned.sam unsorted.bam && ls aligned.sam 2>&1 | head -1', None, r'No such file'),
    ('time samtools index sorted.bam', 0, r'real'),
    ('echo "done" && true', 0, r'done'),
    ('export THREADS=4; REFERENCE="data/reference.fa"; echo "$THREADS $REFERENCE ${REFERENCE%.fa} ${REFERENCE##*/}"', 0, r'4 data/reference\.fa data/reference reference\.fa'),
    ('grep -c . counts.tsv; sed -i "s/variants/n_variants/" counts.tsv; cat counts.tsv', 0, r'n_variants\t60'),
    ("awk 'BEGIN{OFS=\"\\t\"} !/^#/ {split($10,a,\":\"); print $1,$2,$4,$5,$6,a[1]}' variants.vcf | head -2", 0, r'human_CYP2C\d+\t\d+\t[ACGT]+\t[ACGT,]+\t[\d.]+\t[01]/[01]'),
    ('sort -k1,1 -k2,2n variants.vcf | grep -v "^#" | head -1 | cut -f 1-2', 0, r'human_CYP2C19\t\d+'),
    ('tail -n +2 counts.tsv | wc -l; head -n -1 flagstat.txt | wc -l', 0, r'\d'),
    ('find . -name "*.vcf.gz" | sort', 0, r'\./variants\.vcf\.gz'),
    ('find . -maxdepth 1 -type f -name "*.bam" -size +100k | wc -l', 0, r'^\s*\d+\s*$'),
    ('ls -lhS | head -5', 0, r'.'),
    ('tree -L 1 | tail -1', 0, r'director'),
    ('stat -c %s variants.vcf.gz 2>/dev/null || wc -c < variants.vcf.gz', 0, r'^\s*\d+\s*$'),
    ('basename data/NA12878_R1.fastq .fastq; dirname data/NA12878_R1.fastq', 0, r'NA12878_R1\ndata'),
    ('echo $((60 - 50)) $(echo "scale=2; 6817/7038*100" | awk "{print 96.86}")', 0, r'10 96\.86'),
    ("awk 'BEGIN {printf \"%.2f%%\\n\", 6817/7038*100}'", 0, r'96\.86%'),
    ('sleep 1; echo slept', 0, r'slept'),
    ('true | false; echo "pipe $?"; set -o pipefail; true | false | true; echo "pipefail $?"; set +o pipefail', 0, r'pipe 1\npipefail 1'),
    ('echo "${PIPESTATUS[0]}" >/dev/null; x=(a b c); echo "${#x[@]} ${x[1]}"', 0, r'3 b'),
    ('seq 1 3 | xargs -I{} echo "item {}"', 0, r'item 1\nitem 2\nitem 3'),
    ('ls *.vcf.gz | xargs -n 1 basename | sort | head -2', 0, r'vcf\.gz'),
    ('cut -f1 data/reference.fa.fai | paste -sd, -', 0, r'human_CYP2C19,human_CYP2C9'),
    ('cat data/reference.fa | grep -v ">" | tr -d "\\n" | wc -c', 0, r'^\s*56000\s*$'),
    ('grep -v ">" data/reference.fa | tr -d "\\n" | fold -w 1 | sort | uniq -c | sort -k1,1nr | head -4', 0, r'\d+ [ACGT]'),
    ('head -2 data/NA12878_R1.fastq | tail -1 | rev | tr ACGT TGCA', 0, r'^[ACGTN]{76}\s*$'),
    # ---- things that are not there: a clear message, quickly ----
    ('bwa mem data/reference.fa data/NA12878_R1.fastq > x.sam', 127, r'bwa'),
    ('fastqc data/NA12878_R1.fastq', 127, r'fastqc'),
    ('gatk HaplotypeCaller -R data/reference.fa', 127, r'gatk'),
    ('python3 -c "print(1)"', 127, r'python'),
    ('conda install -y bwa', 127, r'conda'),
    ('pip install pysam', 127, r'.'),
    ('apt-get install -y bwa', 127, r'.'),
    ('wget https://example.org/x', 127, r'.'),
    ('curl -sO https://example.org/x', 127, r'.'),
    ('multiqc .', 127, r'.'),
    ('freebayes -f data/reference.fa sorted.bam', 127, r'.'),
    ('picard MarkDuplicates I=sorted.bam O=x.bam', 127, r'.'),
    ('trimmomatic PE a b', 127, r'.'),
    ('igv', 127, r'.'),
    ('df -h .', None, r'.'),
    ('free -h', None, r'.'),
    ('bc <<< "scale=2; 1/3"', None, r'.'),
    ('git status', 127, r'.'),
    ('vim analysis.sh', None, r'.'),
]

SCRIPTS = {
    # the kind of script an agent writes in "Write a script" mode
    'analysis.sh': r'''#!/usr/bin/env bash
#
# Variant calling for NA12878 (CYP2C19 / CYP2C9 region)
#
set -euo pipefail

# ---- settings ----
readonly SAMPLE="NA12878"
readonly REF="data/reference.fa"
readonly R1="data/${SAMPLE}_R1.fastq"
readonly R2="data/${SAMPLE}_R2.fastq"
readonly OUT="results"
THREADS=${THREADS:-4}
SITE="human_CYP2C19:11616"

log() { echo "[$(date '+%H:%M:%S')] $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ---- checks ----
for f in "$REF" "$R1" "$R2"; do
  [[ -s "$f" ]] || die "missing input: $f"
done
for tool in fastp minimap2 samtools bcftools; do
  command -v "$tool" > /dev/null 2>&1 || die "$tool is not installed"
done
mkdir -p "$OUT"

# ---- versions ----
{
  fastp --version 2>&1
  echo "minimap2 $(minimap2 --version)"
  samtools --version | head -n 1
  bcftools --version | head -n 1
} > "$OUT/versions.txt"

# ---- 1. quality control ----
log "Step 1: fastp"
fastp -i "$R1" -I "$R2" \
      -o "$OUT/${SAMPLE}_trimmed_R1.fastq" -O "$OUT/${SAMPLE}_trimmed_R2.fastq" \
      -h "$OUT/fastp.html" -j "$OUT/fastp.json" -w "$THREADS" 2> "$OUT/fastp.log"

# ---- 2. mapping ----
log "Step 2: minimap2"
minimap2 -ax sr -t "$THREADS" -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA" "$REF" \
    "$OUT/${SAMPLE}_trimmed_R1.fastq" "$OUT/${SAMPLE}_trimmed_R2.fastq" 2> "$OUT/minimap2.log" \
  | samtools sort -@ "$THREADS" -o "$OUT/${SAMPLE}.sorted.bam" -
samtools index "$OUT/${SAMPLE}.sorted.bam"
samtools flagstat "$OUT/${SAMPLE}.sorted.bam" > "$OUT/flagstat.txt"

# ---- 3. variant calling ----
log "Step 3: bcftools"
bcftools mpileup -Ou -f "$REF" "$OUT/${SAMPLE}.sorted.bam" 2> /dev/null \
  | bcftools call -mv -Oz -o variants.vcf.gz
bcftools index -f variants.vcf.gz

# ---- 4. report ----
n_variants=$(bcftools view -H variants.vcf.gz | wc -l)
mapped=$(grep -m 1 "mapped (" "$OUT/flagstat.txt" | sed -E 's/.*\(([0-9.]+%).*/\1/')
line=$(bcftools view -H -r "$SITE" variants.vcf.gz || true)
if [[ -z "$line" ]]; then
  genotype="0/0 (no variant called)"
else
  genotype=$(echo "$line" | awk '{split($10, a, ":"); print a[1]}')
  qual=$(echo "$line" | cut -f 6)
  dp4=$(echo "$line" | grep -oE 'DP4=[0-9,]+' | cut -d= -f2)
fi

cat << EOF
===== Summary =====
Sample:        $SAMPLE
Mapped reads:  $mapped
Variants:      $n_variants
Site $SITE: genotype $genotype, QUAL ${qual:-NA}, DP4 ${dp4:-NA}
EOF
log "Done."
''',
    # a more baroque style: functions, arrays, getopts-free arg parsing, traps
    'pipeline2.sh': r'''#!/bin/bash
set -e
set -o pipefail
trap 'echo "failed at line $LINENO" >&2' ERR
trap 'rm -f tmp.*.sam' EXIT

SAMPLES=(NA12878)
REF=data/reference.fa
MAPPER="${1:-bowtie2}"
OUTDIR="out_${MAPPER}"
mkdir -p "$OUTDIR"

function map_reads() {
  local sample=$1 mapper=$2
  local sam="tmp.${sample}.sam"
  if [ "$mapper" == "bowtie2" ]; then
    [ -f "$OUTDIR/ref.1.bt2" ] || bowtie2-build -q "$REF" "$OUTDIR/ref"
    bowtie2 -x "$OUTDIR/ref" -1 "data/${sample}_R1.fastq" -2 "data/${sample}_R2.fastq" -S "$sam" 2> "$OUTDIR/${sample}.bowtie2.log"
  else
    minimap2 -ax sr "$REF" "data/${sample}_R1.fastq" "data/${sample}_R2.fastq" > "$sam" 2> "$OUTDIR/${sample}.minimap2.log"
  fi
  samtools sort -o "$OUTDIR/${sample}.bam" "$sam"
  samtools index "$OUTDIR/${sample}.bam"
}

for s in "${SAMPLES[@]}"; do
  echo ">>> $s with $MAPPER"
  map_reads "$s" "$MAPPER"
  bcftools mpileup -f "$REF" "$OUTDIR/$s.bam" 2>/dev/null | bcftools call -mv -Oz -o "$OUTDIR/$s.vcf.gz"
  bcftools index "$OUTDIR/$s.vcf.gz"
  count=$(bcftools view -H "$OUTDIR/$s.vcf.gz" | wc -l)
  printf '%-10s %-10s %5d variants\n' "$s" "$MAPPER" "$count"
  bcftools query -f '%CHROM:%POS %REF>%ALT QUAL=%QUAL [%GT]\n' -r human_CYP2C19:11616 "$OUTDIR/$s.vcf.gz"
done
i=0
while [ $i -lt 2 ]; do i=$((i + 1)); done
echo "loops: $i; left over: $(ls tmp.*.sam 2>/dev/null | wc -l)"
''',
    # a script with a mistake: must stop at the failing command, with a message, exit status not 0
    'broken.sh': r'''#!/usr/bin/env bash
set -euo pipefail
echo "before"
samtools sort -o nothing.bam does_not_exist.sam
echo "after - must not be printed"
''',
    'unset.sh': r'''#!/usr/bin/env bash
set -u
echo "start"
echo "value: $NOT_SET_ANYWHERE"
echo "after - must not be printed"
''',
}
SCRIPT_RUNS = [
    ('bash analysis.sh', 0, r'===== Summary =====\nSample:\s+NA12878\nMapped reads:\s+99\.\d+%\nVariants:\s+60\nSite human_CYP2C19:11616: genotype 0/1, QUAL 222, DP4 [\d,]+'),
    ('cat results/versions.txt', 0, r'fastp 0\.20\.1\nminimap2 2\.22-r1101\nsamtools 1\.17\nbcftools 1\.10'),
    ('chmod +x analysis.sh && ./analysis.sh > run2.log 2>&1; echo "exit $?"; tail -2 run2.log', 0, r'exit 0'),
    ('bash analysis.sh 2>&1 | tee analysis.log | tail -3', 0, r'Site human_CYP2C19:11616: genotype 0/1'),
    ('THREADS=2 bash analysis.sh 2>/dev/null | grep Variants', 0, r'Variants:\s+60'),
    ('bash pipeline2.sh', 0, r'>>> NA12878 with bowtie2\n(Note: .*\n)?NA12878\s+bowtie2\s+50 variants\nhuman_CYP2C19:11616 G>A QUAL=178\S* 0/1\nloops: 2; left over: 1'),
    ('ls tmp.*.sam 2>/dev/null | wc -l', 0, r'^\s*0\s*$'),
    ('bash pipeline2.sh minimap2 | tail -3', 0, r'60 variants\nhuman_CYP2C19:11616 G>A QUAL=222\S* 0/1'),
    ('bash broken.sh; echo "exit $?"', 0, r'before\n[\s\S]*exit [1-9]'),
    ('bash unset.sh; echo "exit $?"', 0, r'start\n[\s\S]*NOT_SET_ANYWHERE: unbound variable[\s\S]*exit 1'),
    ('bash -x broken.sh 2>&1 | head -3', None, r'\+ echo before'),
    ('bash -n analysis.sh && echo "syntax ok"', 0, r'^syntax ok$'),
    ('bash -lc "bcftools view -H variants.vcf.gz | wc -l"', 0, r'^\s*60\s*$'),
    ('bash -c \'echo "$0 $1"\' name arg1', 0, r'^name arg1$'),
    ('sort nofile', 2, r'sort: cannot read: nofile: No such file or directory'),
    ('fastp --version 2>&1 | head -1; jq --version', 0, r'fastp 0\.20\.1\njq-1\.7'),
    ('ls -1 results | head -3', 0, r'.'),
    ('source analysis.sh > /dev/null 2>&1; echo "still here"', None, r'.'),
]

bad = []
def run(page, c, want, pat):
    t0 = time.time()
    r = term(page, c)
    txt = r['text'].replace('\r', '')
    txt = re.sub(r'\n?\s*✦ Ask the AI assistant about this error\s*', '\n', txt)
    ok = (want is None or r['code'] == want) and (pat is None or re.search(pat, txt.strip(), re.M) is not None)
    dt = time.time() - t0
    print(('ok   ' if ok else 'BAD  ') + f'[{r["code"]}] {dt:5.1f}s  {c[:150]}', flush=True)
    if not ok:
        bad.append(c)
        print('     want exit', want, 'pattern', pat)
        print('\n'.join('     | ' + l for l in txt.strip().split('\n')[-14:]), flush=True)
    return r

with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        only = sys.argv[1] if len(sys.argv) > 1 else ''
        if only != 'scripts':
            for c, want, pat in CASES:
                run(page, c, want, pat)
        else:
            term(page, 'mkdir -p ~/t && cd ~/t && cp -r ~/data .')
        for name, text in SCRIPTS.items():
            page.evaluate("([p, t]) => MG.app.fs.writeText(p, t)", ['/home/student/t/' + name, text])
        for c, want, pat in SCRIPT_RUNS:
            run(page, c, want, pat)
        errs = [l for l in logs if 'PAGEERROR' in l]
        print('\n'.join(errs)[:3000])
        print(f'\n{len(bad)} BAD of {len(CASES) + len(SCRIPT_RUNS)}')
        for c in bad:
            print('  - ' + c[:200])
        b.close()
    finally:
        srv.terminate()
