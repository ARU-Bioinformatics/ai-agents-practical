"""More of what AI agents write: shell idioms and the less common options of the programs.
(Round 2 of t_typical.py; same form: command, expected exit status or None, pattern or None.)"""
import sys, time, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8861
R1, R2, REF = 'data/NA12878_R1.fastq', 'data/NA12878_R2.fastq', 'data/reference.fa'

SETUP = [
    'mkdir -p ~/t && cd ~/t && cp -r ~/data .',
    f'minimap2 -ax sr {REF} {R1} {R2} 2>/dev/null | samtools sort -o sorted.bam && samtools index sorted.bam',
    f'bcftools mpileup -f {REF} sorted.bam 2>/dev/null | bcftools call -mv -Oz -o variants.vcf.gz 2>/dev/null; bcftools index variants.vcf.gz; bcftools view variants.vcf.gz > variants.vcf',
]
CASES = [
    # ---- expansions ----
    ('VCF=variants.vcf.gz; echo "Variants: $(bcftools view -H "$VCF" | wc -l)"', 0, r'^Variants: 60$'),
    ('f=data/NA12878_R1.fastq; echo "${f%.fastq}.bam ${f##*/} ${f%/*} ${f/R1/R2} ${f:5:7} ${#f}"', 0, r'^data/NA12878_R1\.bam NA12878_R1\.fastq data data/NA12878_R2\.fastq NA12878 21$'),
    ('unset OUT; echo "${OUT:-results}"; : "${OUT:=out}"; echo "$OUT"; echo "${OUT:+set}" "${NOPE:+set}|"', 0, r'^results\nout\nset \|$'),
    ('s=na12878; echo "${s^^} ${s^}"; S=ABC; echo "${S,,}"', 0, r'^NA12878 Na12878\nabc$'),
    ('arr=(sorted.bam variants.vcf.gz); echo "${#arr[@]} ${arr[0]} ${arr[-1]}"; for x in "${arr[@]}"; do echo "- $x"; done; echo "${!arr[@]}"', 0, r'^2 sorted\.bam variants\.vcf\.gz\n- sorted\.bam\n- variants\.vcf\.gz\n0 1$'),
    ('files=(data/*.fastq); echo "${#files[@]} fastq files: ${files[*]}"', 0, r'^2 fastq files: data/NA12878_R1\.fastq data/NA12878_R2\.fastq$'),
    ('samples=(); samples+=(a); samples+=(b c); echo "${samples[@]:1:2}"', 0, r'^b c$'),
    ('declare -A depth; depth[CYP2C19]=106; depth[CYP2C9]=90; for k in "${!depth[@]}"; do echo "$k=${depth[$k]}"; done | sort', 0, r'^CYP2C19=106\nCYP2C9=90$'),
    ('for i in {1..3}; do echo -n "$i "; done; echo "|"; for i in $(seq 1 3); do printf "%d " "$i"; done; echo "|"', 0, r'^1 2 3 \|\n1 2 3 \|$'),
    ('for ((i = 0; i < 3; i++)); do echo "i=$i"; done | tail -1', 0, r'^i=2$'),
    ('count=0; for f in data/*.fastq data/MD5SUMS; do ((count++)); done; echo "$count"; let count+=1; echo $count; count=$((count * 2)); echo $count', 0, r'^3\n4\n8$'),
    ('x=5; if (( x > 3 )); then echo big; fi; (( x == 5 )) && echo five; echo $(( x % 2 == 1 ? 10 : 20 ))', 0, r'^big\nfive\n10$'),
    ('echo $((7038 - 6170)) $((6170 * 100 / 7038)) $((2 ** 10)) $((0x10)) $(( (3 + 4) * 2 ))', 0, r'^868 87 1024 16 14$'),
    # ---- tests ----
    ('v=variants.vcf.gz; if [[ -f $v && -s $v ]]; then echo ok; fi; [[ $v == *.vcf.gz ]] && echo vcf; [[ $v =~ ^([a-z]+)\\.vcf ]] && echo "${BASH_REMATCH[1]}"', 0, r'^ok\nvcf\nvariants$'),
    ('if ! command -v bwa > /dev/null; then echo "no bwa"; fi; if samtools quickcheck sorted.bam && [ -f sorted.bam.bai ]; then echo "bam ok"; fi', 0, r'^no bwa\nbam ok$'),
    ('[ -d results ] || mkdir results; [ -d results ] && echo made; test -e nothing; echo $?; [ "a" != "b" -a 3 -lt 5 ] && echo yes', 0, r'^made\n1\nyes$'),
    ('n=$(bcftools view -H variants.vcf.gz | wc -l); if [ "$n" -eq 60 ]; then echo sixty; elif [ "$n" -gt 60 ]; then echo more; else echo fewer; fi', 0, r'^sixty$'),
    ('[[ -z "$UNSET_VAR" ]] && echo empty; [[ -n "$HOME" ]] && echo home; [[ 10 -gt 9 && "b" > "a" ]] && echo cmp', 0, r'^empty\nhome\ncmp$'),
    ('samtools view -c nothing.bam > /dev/null 2>&1; if [ $? -ne 0 ]; then echo "failed as expected"; fi', 0, r'^failed as expected$'),
    # ---- reading input ----
    ('bcftools view -H variants.vcf.gz | head -3 | while read -r chrom pos id ref alt rest; do echo "$chrom:$pos $ref>$alt"; done', 0, r'^human_CYP2C19:\d+ [ACGT]+>[ACGT,]+\n.*\n.*$'),
    ("while IFS=$'\\t' read -r name len rest; do echo \"$name has $len bases\"; done < data/reference.fa.fai", 0, r'^human_CYP2C19 has 30000 bases\nhuman_CYP2C9 has 26000 bases$'),
    ('n=0; while read -r line; do n=$((n + 1)); done < data/MD5SUMS; echo "$n lines"', 0, r'^3 lines$'),
    ('read -r first second <<< "alpha beta gamma"; echo "$second|$first"', 0, r'^beta gamma\|alpha$'),
    ('grep -c "CYP2C19" <<< "$(cut -f1 variants.vcf | grep -v "^#")"', 0, r'^18$'),
    ('wc -l <<< "one line"; cat <<< "$HOME"', 0, r'^1\n/home/student$'),
    ("line=$(bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz); IFS=$'\\t' read -r c p i r a q rest <<< \"$line\"; echo \"$c $p $r $a $q\"", 0, r'^human_CYP2C19 11616 G A 222$'),
    ('mapfile -t lines < data/MD5SUMS; echo "${#lines[@]} ${lines[2]##* }"; readarray names < data/reference.fa.fai; printf "%s" "${names[1]}" | cut -f1; cut -f1 data/reference.fa.fai | { mapfile -t n; echo "${n[*]}"; }', 0, r'^3 reference\.fa\nhuman_CYP2C9\nhuman_CYP2C19 human_CYP2C9$'),
    ('IFS=: read -ra parts <<< "GT:PL:AD"; echo "${#parts[@]} ${parts[2]}"; read -r -a w <<< "a b  c"; echo "${w[@]}"; x=y; y=5; echo "${!x}"', 0, r'^3 AD\na b c\n5$'),
    ('declare -A m=([minimap2]=60 [bowtie2]=50); m[fastp]="6170 reads"; for k in "${!m[@]}"; do echo "$k -> ${m[$k]}"; done | sort; echo "${#m[@]}"; unset "m[fastp]"; echo "${#m[@]} ${m[bowtie2]}"; [[ -n "${m[minimap2]}" ]] && echo has', 0, r'^bowtie2 -> 50\nfastp -> 6170 reads\nminimap2 -> 60\n3\n2 50\nhas$'),
    # ---- output ----
    ('echo -e "a\\tb\\nc"; echo -n "no newline"; echo; printf "%-12s|%6.2f|%5d|%s\\n" "minimap2" 96.857 60 "0/1"', 0, r'^a\tb\nc\nno newline\nminimap2    \| 96\.86\|   60\|0/1$'),
    ('printf "%s\\n" one two three | paste -sd, -; printf "%05.1f%%\\n" 7.156; printf "%x %o %e\\n" 255 8 12345.678', 0, r'^one,two,three\n007\.2%\nff 10 1\.234568e\+04$'),
    ('echo "error message" >&2; echo "to stdout"; >&2 echo "also error"', 0, r'error message\nto stdout\nalso error'),
    ('{ echo "to out"; echo "to err" >&2; } > both.txt 2>&1; cat both.txt; { echo o; echo e >&2; } 2> err.txt > out.txt; cat err.txt out.txt', 0, r'^to out\nto err\ne\no$'),
    ('samtools flagstat sorted.bam | tee flagstat.txt | head -1; wc -l < flagstat.txt', 0, r'^7038 \+ 0 in total.*\n\s*1\d$'),
    ('bcftools view -H variants.vcf.gz 2>&1 | tee -a log.txt | wc -l; echo done >> log.txt; tail -1 log.txt; wc -l < log.txt', 0, r'^\s*60\ndone\n\s*61$'),
    ('samtools nonsense 2>&1 | head -2; echo "status ${PIPESTATUS[0]}"', 0, r'unrecognized command|status'),
    ('ls *.bam *.vcf.gz 2> /dev/null | sort | tr "\\n" " "; echo "|"', 0, r'^sorted\.bam variants\.vcf\.gz \|$'),
    ("cat > config.txt << 'EOF'\nREF=$HOME/not/expanded\nTHREADS=4\nEOF\ncat config.txt | head -1; cat > note.txt <<EOF\nhome is $HOME\nEOF\ncat note.txt", 0, r'^REF=\$HOME/not/expanded\nhome is /home/student$'),
    ('cat <<-EOF | tr a-z A-Z\n\tindented\n\tEOF', 0, r'^INDENTED$'),
    ('tee notes.md > /dev/null <<EOF\n# Notes\n- variants: $(bcftools view -H variants.vcf.gz | wc -l)\nEOF\ncat notes.md', 0, r'^# Notes\n- variants: 60$'),
    # ---- functions, scripts, traps ----
    ('count_variants() { bcftools view -H "$1" | wc -l; }; echo "n=$(count_variants variants.vcf.gz)"', 0, r'^n=60$'),
    ('function log { local level=$1; shift; echo "[$level] $*"; }; log INFO mapping done; log WARN "two words"', 0, r'^\[INFO\] mapping done\n\[WARN\] two words$'),
    ('check() { [ -s "$1" ] || { echo "missing: $1" >&2; return 1; }; }; check sorted.bam && echo present; check nope.bam || echo "rc=$?"', 0, r'present\nmissing: nope\.bam\nrc=1'),
    ('tmp=$(mktemp -d); echo x > "$tmp/a.txt"; ls "$tmp" | wc -l; rm -rf "$tmp"; [ -d "$tmp" ] || echo cleaned', 0, r'^\s*1\ncleaned$'),
    ('start=$(date +%s); sleep 1; end=$(date +%s); el=$((end - start)); [ "$el" -ge 1 ] && [ "$el" -le 3 ] && echo "timing ok"; echo "$SECONDS" | grep -c "^[0-9]*$"', 0, r'^timing ok\n1$'),
    ('set -x; echo traced; set +x; echo quiet', 0, r'\+ echo traced\ntraced\n\+ set \+x\nquiet'),
    ('(set -e; false; echo "not printed"); echo "subshell rc=$?"; (exit 3); echo "rc=$?"', 0, r'^subshell rc=1\nrc=3$'),
    ('x=outer; (x=inner; echo "$x"); echo "$x"; { x=changed; }; echo "$x"', 0, r'^inner\nouter\nchanged$'),
    ('echo "one two" | { read a b; echo "$b $a"; }; echo "a b c" | awk "{print \\$2}"; seq 3 | tac | tr "\\n" " "; echo "|"', 0, r'^two one\nb\n3 2 1 \|$'),
    ('true && echo "A" || echo "B"; false && echo "C" || echo "D"; ! false && echo "E"', 0, r'^A\nD\nE$'),
    ('a=1 b=2 bash -c \'echo "$a$b"\'; export SAMPLE=NA12878; bash -c \'echo "$SAMPLE"\'; env | grep -c "^SAMPLE="', 0, r'^12\nNA12878\n1$'),
    ('printf \'#!/usr/bin/env bash\\necho "args: $# first=$1 all=$@"\\nexit 4\\n\' > s.sh; chmod +x s.sh; ./s.sh a "b c"; echo "rc=$?"', 0, r'^args: 2 first=a all=a b c\nrc=4$'),
    # ---- things that are not available: a message that says so ----
    # ---- process substitution: the commands in <( ) run first, and the command gets a file ----
    ('diff <(bcftools view -H variants.vcf.gz | cut -f1,2) <(cut -f1,2 variants.vcf | grep -v "^#") && echo "the same positions"', 0, r'^the same positions$'),
    ('comm -12 <(bcftools view -H variants.vcf.gz | cut -f2 | sort) <(cut -f2 variants.vcf | grep -v "^#" | sort) | wc -l', 0, r'^\s*60$'),
    ('while read -r chrom n; do echo "$chrom has $n"; done < <(bcftools view -H variants.vcf.gz | cut -f1 | sort | uniq -c | awk \'{print $2, $1}\')', 0, r'^human_CYP2C19 has \d+\nhuman_CYP2C9 has \d+$'),
    ('samtools index sorted.bam &', None, r'background|&'),
    ('ln -s data/reference.fa ref.fa', None, r'.'),
    ('tar -czf results.tar.gz results', 127, r'tar'),
    ('zip -r results.zip results', 127, r'zip'),
    ('nohup samtools index sorted.bam', None, r'.'),
    ('watch ls', 127, r'.'),
    ('top -b -n 1', 127, r'.'),
    ('R --version', 127, r'.'),
    ('perl -e "print 1"', 127, r'.'),
    ('java -jar picard.jar', 127, r'.'),
    ('docker run hello-world', 127, r'.'),
    ('snakemake -n', 127, r'.'),
    ('samtools tview sorted.bam', None, r'terminal'),
    # ---- options of the programs that models reach for ----
    ('samtools view -h -b -F 4 -q 30 sorted.bam > hq.bam && samtools view -c hq.bam', 0, r'^\d+$'),
    ('samtools view -@ 4 -bS -o x.bam sorted.bam 2>&1 | tail -1; samtools view -c x.bam', 0, r'7038'),
    ('samtools flagstat -O tsv sorted.bam | head -2', 0, r'^7038\t0\ttotal'),
    ('samtools view -c -f 2 sorted.bam; samtools view -c -F 0x904 sorted.bam', 0, r'^6670\n\d+$'),
    ('samtools sort -m 100M -@ 2 -o s2.bam sorted.bam && samtools index -@ 2 s2.bam && ls s2.bam.bai', 0, r's2\.bam\.bai'),
    ('samtools stats sorted.bam | grep -E "^SN\\s+(error rate|average length|insert size average)"', 0, r'error rate:\t[\d.e+-]+'),
    ('samtools addreplacerg -r "@RG\\tID:1\\tSM:NA12878" -o rg.bam sorted.bam && samtools view -H rg.bam | grep -c "^@RG"', 0, r'^1$'),
    ('samtools calmd -b sorted.bam data/reference.fa > md.bam 2>/dev/null; samtools view md.bam | head -1 | grep -o "MD:Z:[0-9A-Z^]*"', 0, r'^MD:Z:'),
    ('printf "human_CYP2C19\\t11600\\t11630\\n" > site.bed; samtools bedcov site.bed sorted.bam', 0, r'human_CYP2C19\t11600\t11630\t\d+'),
    ('samtools view -L site.bed -c sorted.bam; bedtools intersect -a sorted.bam -b site.bed -bed | wc -l', 0, r'^\d+\n\s*\d+$'),
    ('samtools consensus -r human_CYP2C19:11610-11620 sorted.bam 2>&1 | tail -1', None, r'[ACGTRN]{5,}|consensus'),
    ('samtools mpileup -r human_CYP2C19:11616-11616 -f data/reference.fa sorted.bam 2>/dev/null | cut -f5 | fold -w1 | sort | uniq -c | sort -k1,1nr | head -3', 0, r'\d+ [.,Aa]'),
    (f'minimap2 -d ref.mmi {REF} 2>/dev/null; ls ref.mmi && minimap2 -ax sr ref.mmi {R1} {R2} 2>/dev/null | samtools view -c -', 0, r'^ref\.mmi\n70\d\d$'),
    (f'minimap2 -ax sr --MD -Y --secondary=no {REF} {R1} {R2} 2>/dev/null | samtools sort -o md2.bam && samtools view md2.bam | head -1 | grep -c "MD:Z"', 0, r'^1$'),
    (f'minimap2 -a {REF} {R1} 2>/dev/null | samtools flagstat - | grep "mapped ("', 0, r'mapped \('),
    (f'bowtie2-build --quiet {REF} bt >/dev/null && bowtie2 --no-unal -X 600 --sensitive -x bt -1 {R1} -2 {R2} 2>/dev/null | samtools view -c -', 0, r'^\d+$'),
    (f'bowtie2 -x bt -U {R1} --un unaligned.fq -S single.sam', 1, r'--un is not available here'),
    (f'bowtie2 -x bt -U {R1} -S single.sam 2>&1 | tail -1; samtools fastq -f 4 single.sam 2>/dev/null | head -1', 0, r'overall alignment rate\n@SRR'),
    (f'bowtie2 -x bt -1 {R1} -2 {R2} --met-file met.txt -S /dev/null 2>/dev/null; head -1 met.txt | cut -f1-3', 0, r'^Time\tRead'),
    (f'fastp -i {R1} -I {R2} -o c1.fq -O c2.fq --cut_front --cut_tail --cut_mean_quality 20 --length_required 50 --qualified_quality_phred 20 -R "NA12878 QC" -j c.json -h c.html 2>&1 | grep "reads passed filter"', 0, r'reads passed filter: \d+'),
    (f'fastp -i {R1} -I {R2} --stdout -j s.json -h s.html 2>/dev/null | head -1', 0, r'^@SRR098401'),
    (f'fastp -i {R1} -o single.fq -A -G -Q -L -j n.json -h n.html 2>&1 | grep "reads passed filter"', 0, r'reads passed filter: 3519'),
    (f'fastp -i {R1} -I {R2} -o d1.fq -O d2.fq --dedup -j d.json -h d.html 2>&1 | tail -3', None, r'.'),
    (f'fastp -i {R1} -I {R2} -o p1.fq -O p2.fq -p -c -j p.json -h p.html 2>&1 | grep -c "Duplication rate"', 0, r'^1$'),
    (f'seqtk sample -s100 {R1} 1000 > sub.fq; echo $(( $(wc -l < sub.fq) / 4 )); seqtk seq -a sub.fq | grep -c "^>"; seqtk trimfq sub.fq | head -1', 0, r'^1000\n1000\n@'),
    ('seqtk subseq data/reference.fa site.bed', 0, r'^>human_CYP2C19:11601-11630\n[ACGT]{30}$'),
    ("bcftools mpileup -d 1000 -q 20 -Q 20 -a FORMAT/AD,FORMAT/DP -f data/reference.fa sorted.bam 2>/dev/null | bcftools call -mv --ploidy 2 2>/dev/null | bcftools view -H | wc -l", 0, r'^\s*\d+$'),
    ('bcftools view -g het -H variants.vcf.gz | wc -l; bcftools view -g hom -H variants.vcf.gz | wc -l; bcftools view -m2 -M2 -v snps -H variants.vcf.gz | wc -l', 0, r'^\s*\d+\n\s*\d+\n\s*\d+$'),
    ("bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT[\\t%GT]\\n' variants.vcf.gz | awk '$5==\"0/1\"' | wc -l", 0, r'^\s*\d+$'),
    ("bcftools query -i 'QUAL>100' -f '%POS\\n' variants.vcf.gz | wc -l; bcftools view -e 'QUAL<100 || DP<20' -H variants.vcf.gz | wc -l", 0, r'^\s*\d+\n\s*\d+$'),
    ('bcftools index -n variants.vcf.gz; bcftools index --tbi -f variants.vcf.gz && ls variants.vcf.gz.tbi', 0, r'^60\nvariants\.vcf\.gz\.tbi$'),
    ('bcftools +fill-tags variants.vcf.gz -- -t AF', 1, r'plugins \(\+fill-tags\) are not available'),
    ('echo "NA12878" > names.txt; bcftools reheader -s names.txt variants.vcf.gz -o renamed.vcf.gz && bcftools query -l renamed.vcf.gz', 0, r'^NA12878$'),
    ('bcftools sort -Oz -o sorted.vcf.gz variants.vcf.gz 2>&1 | tail -1; bcftools view -H sorted.vcf.gz | wc -l', 0, r'60'),
    ('bcftools annotate -x INFO/VDB,INFO/SGB variants.vcf.gz | grep -v "^#" | head -1 | grep -c VDB', 1, r'^0$'),
    ('bcftools consensus -f data/reference.fa variants.vcf.gz 2>/dev/null | grep -c "^>"', 0, r'^2$'),
    ('bcftools view -r human_CYP2C19:11000-12000 -Ov variants.vcf.gz | bcftools stats | grep "number of records"', 0, r'number of records:\t\d+'),
    ('bcftools mpileup -f data/reference.fa -r human_CYP2C19:11616-11616 sorted.bam 2>/dev/null | bcftools view -H | cut -f1-5', 0, r'^human_CYP2C19\t11616\t\.\tG\tA,<\*>$'),
    ('gzip -k variants.vcf && ls variants.vcf.gz variants.vcf | wc -l; gzip -c variants.vcf > v.gz; gunzip -c v.gz | grep -vc "^#"; zcat v.gz | head -1', None, r'60'),
    ('bgzip -f -@ 2 -c variants.vcf > b.vcf.gz && tabix -f -p vcf b.vcf.gz && tabix b.vcf.gz human_CYP2C19:11616-11616 | cut -f 2', 0, r'^11616$'),
    ('tabix -l variants.vcf.gz; tabix -h variants.vcf.gz human_CYP2C9 | grep -vc "^#"', 0, r'^human_CYP2C19\nhuman_CYP2C9\n42$'),
    ('bedtools genomecov -ibam sorted.bam -d | awk \'$3 >= 20\' | wc -l; bedtools coverage -a site.bed -b sorted.bam -mean', 0, r'^\s*\d+\nhuman_CYP2C19\t11600\t11630\t[\d.]+$'),
    ('bedtools getfasta -fi data/reference.fa -bed site.bed', 0, r'^>human_CYP2C19:11600-11630\n[ACGT]{30}$'),
    ("jq -r '[.summary.before_filtering.total_reads, .summary.after_filtering.total_reads] | @tsv' c.json; jq '.filtering_result | keys | length' c.json; jq -r '.command' c.json | cut -c1-5", 0, r'^7038\t\d+\n5\nfastp$'),
    ("awk -F'\\t' -v OFS='\\t' '!/^#/ {n[$1]++} END {for (c in n) print c, n[c]}' variants.vcf | sort", 0, r'^human_CYP2C19\t18\nhuman_CYP2C9\t42$'),
    ("grep -v '^#' variants.vcf | awk '{if ($6 >= 30) hq++; else lq++} END {printf \"high %d low %d\\n\", hq, lq}'", 0, r'^high 27 low 33$'),
    ("sed -n '/^#CHROM/,$p' variants.vcf | head -2 | cut -f 1-3; sed -e 's/human_//' -e '/^#/d' variants.vcf | cut -f1 | sort -u", 0, r'^#CHROM\tPOS\tID\n.*\nCYP2C19\nCYP2C9$'),
    ("grep -E -o 'DP=[0-9]+' variants.vcf | cut -d= -f2 | sort -n | sed -n '1p;$p' | paste -sd' ' -", 0, r'^\d+ \d+$'),
    ("grep -P '\\t11616\\t' variants.vcf | cut -f1,2", 0, r'^human_CYP2C19\t11616$'),
    ("grep -oP 'DP=\\K\\d+' variants.vcf | sort -n | tail -1; grep -cP '^human_CYP2C19\\t' variants.vcf; grep -P -o 'MQ=\\d+' variants.vcf | head -1; grep -vP '^#' variants.vcf | wc -l", 0, r'^\d+\n18\nMQ=\d+\n\s*60$'),
    ("bcftools view -H variants.vcf.gz | grep -P '^\\S+\\t11616\\t' | grep -oP '(?<=DP4=)[0-9,]+'; echo 'GT:PL 0/1:255,0,255' | grep -oP '[01]/[01]'; grep -qP 'nothing_here' variants.vcf; echo \"rc=$?\"; grep -P '(?i)^##FILEFORMAT' variants.vcf; grep -nP '^#CHROM' variants.vcf | cut -d: -f1 | grep -cP '^\\d+$'", 0, r'^40,4,46,2\n0/1\nrc=1\n##fileformat=VCFv4\.2\n1$'),
    ("grep -P '[[:space:]]11616[[:space:]]' variants.vcf | wc -l; grep -wP '11616' variants.vcf | wc -l; echo 'aB Ab ab' | grep -oP 'a(?i)b' | paste -sd' '", 0, r'^\s*1\n\s*1\naB ab$'),
    ('sort -t"	" -k6,6gr variants.vcf | grep -v "^#" | head -1 | cut -f 6; cut -f 6 variants.vcf | grep -v "^#\\|QUAL" | sort -g | head -1', 0, r'^\d+(\.\d+)?\n\d+(\.\d+)?$'),
    ('column -t data/reference.fa.fai | head -1; nl data/MD5SUMS | tail -1 | cut -c1-8; comm -12 data/MD5SUMS data/MD5SUMS | wc -l', 0, r'human_CYP2C19\s+30000'),
    ('find . -name "*.bam" -newer data/reference.fa | sort | head -2; find . -type f -name "*.fq" -exec ls -l {} \\; | wc -l; find . -name "*.fq" -delete; ls *.fq 2>/dev/null | wc -l', 0, r'\./\S+\.bam'),
    ('du -h sorted.bam | cut -f2; stat sorted.bam | head -1; md5sum sorted.bam | cut -c1-32 | wc -c; sha256sum data/reference.fa | cut -c1-8', 0, r'^sorted\.bam\n'),
    ('cp sorted.bam copy.bam && mv copy.bam moved.bam && ls moved.bam && rm moved.bam && ls moved.bam 2>&1 | grep -c "No such file"', 0, r'^moved\.bam\n1$'),
    ('mkdir -p a/b/c && touch a/b/c/x.txt && cp -r a a2 && rm -r a && ls -R a2 | grep -c x.txt && rmdir a2 2>&1 | grep -c "not empty"', 0, r'^1\n1$'),
    # a read-only file is not written over by cp – unless -f is given; a folder that was removed stays removed
    ('mkdir -p ro/d ro/e && echo a > ro/d/x && chmod -w ro/d/x && cp -r ro/d ro/e/ && echo b > ro/d/y && cp -r ro/d ro/e/; echo "status $?"; ls ro/e/d | tr "\\n" " "; cp -rf ro/d ro/e/; echo "status $?"; cp ro/d/y ro/e/d/x; echo "status $?"; cp -f ro/d/y ro/e/d/x; echo "status $?"; cat ro/e/d/x', 0, r"cp: cannot create regular file 'ro/e/d/x': Permission denied\nstatus 1\nx y status 0\ncp: cannot create regular file 'ro/e/d/x': Permission denied\nstatus 1\nstatus 0\nb$"),
    ('mkdir -p gone/sub && samtools view -H sorted.bam > gone/sub/h.txt && bgzip -c gone/sub/h.txt > gone/sub/h.gz && rm -rf gone && samtools --version | head -1 && ls -d gone gone/sub 2>&1 | grep -c "No such file"; mkdir gone && ls gone | wc -l', 0, r'^samtools 1\.17\n2\n0$'),
    # … also the folder the last program ran in, and a file of the same name afterwards
    ('mkdir -p wd/sub && cd wd/sub && samtools --version | head -1 && cd ~/t && rm -r wd && samtools --version | head -1 && ls -d wd 2>&1 | grep -c "No such file"; echo x > wd && cat wd && rm wd && mkdir wd && ls -d wd && rmdir wd', 0, r'^samtools 1\.17\nsamtools 1\.17\n1\nx\nwd$'),
    # a copy that no program has read yet keeps its bytes when the original is written over (also with < FILE)
    ('cp sorted.bam a1.bam && samtools quickcheck a1.bam && cp a1.bam b1.bam && cp a1.bam c1.bam && mv c1.bam d1.bam && echo x > a1.bam && wc -l < a1.bam && samtools view -c b1.bam && samtools view -c d1.bam && rm a1.bam b1.bam d1.bam', 0, r'^1\n7038\n7038$'),
    ('wc -c < /dev/null; cat < /dev/null | wc -l; while read x; do echo never; done < /dev/null; echo done', 0, r'^0\n0\ndone$'),
    ('mkdir -p cl/d cl/e/d && echo a > cl/d/x && mkdir cl/e/d/x && echo f > cl/e/d2 && mkdir cl/d2; cp -r cl/d cl/e/ ; echo "status $?"; cp -r cl/d2 cl/e/; echo "status $?"; echo keep > cl/n1 && echo new > cl/n2 && cp -n cl/n2 cl/n1 && cat cl/n1 && chmod -w cl/n1 && cp cl/n1 cl/n1; echo "status $?"', 0, r"cp: cannot overwrite directory 'cl/e/d/x' with non-directory\nstatus 1\ncp: cannot overwrite non-directory 'cl/e/d2' with directory 'cl/d2'\nstatus 1\nkeep\ncp: 'cl/n1' and 'cl/n1' are the same file\nstatus 1$"),
    ('echo one > m1 && echo two > m2 && chmod -w m2 && mv m1 m2; echo "status $?"; mv -n m1 m2; cat m2; mv -f m1 m2 && cat m2 && ls m1 2>&1 | grep -c "No such file"', 0, r"write-protected \(use mv -f to replace it anyway\)\nstatus 1\ntwo\none\n1$"),
    # mv and cp do not put a file in place of a folder, or a folder in place of a file or of a folder that is not empty
    ('mkdir -p ty/dd/f1 ty/d1 ty/d2/d1 && echo in > ty/dd/f1/keep && echo f > ty/f1 && echo g > ty/f2 && echo h > ty/d2/d1/h && cd ty; mv f1 dd; echo "status $?"; mv d1 f2; echo "status $?"; mv d1 d2; echo "status $?"; cp f1 dd; echo "status $?"; cat dd/f1/keep f2 d2/d1/h; rmdir d2/d1 2>&1 | grep -c "not empty"; cd ~/t', 0, r"mv: cannot overwrite directory 'dd/f1' with non-directory\nstatus 1\nmv: cannot overwrite non-directory 'f2' with directory 'd1'\nstatus 1\nmv: cannot move 'd1' to 'd2/d1': Directory not empty\nstatus 1\ncp: cannot overwrite directory 'dd/f1' with non-directory\nstatus 1\nin\ng\nh\n1$"),
    # (the folder one is in can be removed, as on Linux: a program still starts there, and what is written there fails)
    ('mkdir -p rd/in && cd rd/in && rmdir ../in; echo "status $?"; samtools --version | head -1; pwd; echo x > f.txt; echo "status $?"; cd ~/t && ls rd | wc -l && rmdir rd && ls -d rd 2>&1 | grep -c "No such file"', 0, r"^status 0\nsamtools 1\.17\n/home/student/t/rd/in\nbash: f\.txt: No such file or directory\nstatus 1\n0\n1$"),
    ('echo text > was_file && samtools --version > /dev/null && rm was_file && mkdir was_file && samtools view -H sorted.bam > was_file/h.txt && grep -c "@SQ" was_file/h.txt && rm -r was_file && echo again > was_file && cat was_file | tr a-z A-Z', 0, r'^2\nAGAIN$'),
    # a destination written with a slash at its end has to be a folder
    ('echo a > ts1 && echo b > ts2; mv ts1 nodir/; echo "status $?"; cp ts1 nodir/; echo "status $?"; cp ts1 ts2/; echo "status $?"; cat ts1 ts2; ls nodir 2>&1 | grep -c "No such file"', 0, r"mv: cannot move 'ts1' to 'nodir/': Not a directory\nstatus 1\ncp: cannot create regular file 'nodir/': Not a directory\nstatus 1\ncp: failed to access 'ts2/': Not a directory\nstatus 1\na\nb\n1$"),
    # cp writes into a file that is there: that file keeps its permissions; a new copy of a read-only file is read-only
    ('echo a > ro1 && chmod a-w ro1 && echo b > w1 && cp ro1 w1 && echo more >> w1 && cat w1; cp ro1 n1 && echo x >> n1; echo "status $?"', 0, r"^a\nmore\nbash: n1: Permission denied\nstatus 1$"),
    ('mkdir -p src/sub && echo 1 > src/a && echo 2 > src/sub/b && mkdir into && cp -r src/. into && ls into into/sub | tr "\\n" " "; cp -t into ts1 ts2 && mv -t into w1 && ls into | tr "\\n" " "; mv ts1 nothere ts2 into; echo "status $?"; ls ts1 ts2 2>&1 | grep -c "No such file"', 0, r"^into: a sub  into/sub: b a sub ts1 ts2 w1 mv: cannot stat 'nothere': No such file or directory\nstatus 1\n2$"),
    ('mv ro1 ro1; echo "status $?"; cd data && cd - && cd - > /dev/null && pwd | sed "s|.*/||"; cd ~/t; cd ""; pwd | sed "s|.*/||"', 0, r"mv: 'ro1' and 'ro1' are the same file\nstatus 1\n/home/student/t\ndata\nt$"),
    # NAME --help of the terminal's own commands says which options they have; -- and commands that run another keep it away
    ('ls --help | head -n 1; split --help | grep -c -- "^ *-[a-z]"; man bc | head -n 1 | cut -c1-9; ls --version | grep -c "the terminal of this practical"; diff --version | head -n 1; cmp --version | head -n 1; diff --help | head -n 1', 0, r"^Usage: ls \[OPTION\]\.\.\. \[FILE\]\.\.\.\n[1-9]\d*\nUsage: bc\n1\ndiff \(GNU diffutils\) 3\.10\ncmp \(GNU diffutils\) 3\.10\nUsage: diff \[OPTION\]\.\.\. FILES$"),
    ('mkdir -- --help && ls -d -- --help && rmdir -- --help; echo "status $?"; echo --help; echo a | xargs echo --help; timeout 5 echo --help; find . -maxdepth 1 -name --help; echo "status $?"', 0, r"^--help\nstatus 0\n--help\n--help a\n--help\nstatus 0$"),
    ('sort --help | head -n 1; samtools --help 2>&1 | grep -c "^Program: samtools"; env --help | head -n 1 | cut -c1-10; env X=1 printenv X; man nosuch; echo "status $?"', 0, r"^Usage: sort \[OPTION\]\.\.\. \[FILE\]\.\.\.\n1\nUsage: env\n1\nNo manual entry for nosuch\nstatus 16$"),
    ("printf 'a\\tb\\n' > ft.tsv && file ft.tsv && file -b ft.tsv && file -i ft.tsv && file --mime-type sorted.bam variants.vcf.gz | sed 's/  */ /'", 0, r"^ft\.tsv: ASCII text\nASCII text\nft\.tsv: text/plain; charset=us-ascii\nsorted\.bam: application/x-gzip\nvariants\.vcf\.gz: application/x-gzip$"),
    # tree, env -C, id -u, uname, sleep, mktemp: their options – and an option that is not there is refused
    ('mkdir -p tr/a/b && echo x > tr/a/f.txt && echo y > tr/g.sh && chmod +x tr/g.sh && touch tr/.h && tree tr; tree -fi --noreport tr; tree -aF --dirsfirst tr | head -n 6; tree -I "a" --noreport tr; tree -d -L 1 tr | tail -n 1', 0, r"^tr\n├── a\n│   ├── b\n│   └── f\.txt\n└── g\.sh\n\n2 directories, 2 files\ntr\ntr/a\ntr/a/b\ntr/a/f\.txt\ntr/g\.sh\ntr\n├── a/\n│   ├── b/\n│   └── f\.txt\n├── \.h\n└── g\.sh\*\ntr\n└── g\.sh\n1 directory$"),
    ('tree -h tr; echo "status $?"; tree -z tr; echo "status $?"; tree --bogus; echo "status $?"; tree -L 0 tr; echo "status $?"', 0, r"tree: -h \(sizes\) is not available in this terminal.*\nstatus 1\ntree: Invalid argument -`z'\.\nusage: tree .*\nstatus 1\ntree: Invalid argument `--bogus'\.\nusage: tree .*\nstatus 1\ntree: Invalid level, must be greater than 0\.\nstatus 1$"),
    ('id -u; id -un; id -g; id -Gn; whoami; hostname -s; nproc --all; uname -sm; uname -o; id -x; echo "status $?"; uname -z; echo "status $?"', 0, r"^1000\nstudent\n1000\nstudent\nstudent\nbiolab\n1\nLinux wasm32\nGNU/Linux\nid: invalid option -- 'x'\nTry 'id --help' for more information\.\nstatus 1\nuname: invalid option -- 'z'\nTry 'uname --help' for more information\.\nstatus 1$"),
    ('env -C tr pwd | sed "s|.*/||"; pwd | sed "s|.*/||"; env -C nosuch pwd; echo "status $?"; env --bogus true; echo "status $?"; env -0 | tr "\\0" "\\n" | grep -c "^HOME="; printenv -0 HOME | od -c | head -n 1 | tr -s " "', 0, r"^tr\nt\nenv: cannot change directory to .nosuch.: No such file or directory\nstatus 125\nenv: unrecognized option '--bogus'\nTry 'env --help' for more information\.\nstatus 125\n1\n0000000 / h o m e / s t u d e n t \\0$"),
    ('sleep 0.1 0.1; sleep abc; echo "status $?"; sleep; echo "status $?"; timeout --bogus 5 true; echo "status $?"; timeout --foreground -k 1 5 echo ok; mktemp -dp . | cut -c1-6; mktemp -x; echo "status $?"; basename -x a; echo "status $?"; dirname --bogus a; echo "status $?"', 0, r"^sleep: invalid time interval .abc.\nTry 'sleep --help' for more information\.\nstatus 1\nsleep: missing operand\nTry 'sleep --help' for more information\.\nstatus 1\ntimeout: unrecognized option '--bogus'\nTry 'timeout --help' for more information\.\nstatus 125\nok\n\./tmp\.\nmktemp: invalid option -- 'x'\nTry 'mktemp --help' for more information\.\nstatus 1\nbasename: invalid option -- 'x'\nTry 'basename --help' for more information\.\nstatus 1\ndirname: unrecognized option '--bogus'\nTry 'dirname --help' for more information\.\nstatus 1$"),
    # /dev/tty is the terminal (here: where the messages go); an input without end is refused with an explanation
    ('x=$(echo shown > /dev/tty; echo captured); echo "x=$x"; wc -c < /dev/zero; echo "status $?"; head -c 3 /dev/zero | od -An -tx1; ls /dev | tr "\\n" " "', 0, r"^shown\nx=captured\nbash: /dev/zero: an input that never ends cannot feed a command in this terminal.*\nstatus 1\n 00 00 00\nnull random stderr stdin stdout tty urandom zero$"),
    # a program's output and its messages come in the order in which the program wrote them
    ('printf "a1\\na2\\n" > oa.txt; printf "a3\\n" > ob.txt; wc -l oa.txt nosuch ob.txt; { grep a oa.txt nosuch ob.txt; } 2>&1 | cat -n | tr -s " \\t" " "', 0, r"^2 oa\.txt\nwc: nosuch: No such file or directory\n1 ob\.txt\n3 total\n 1 oa\.txt:a1\n 2 oa\.txt:a2\n 3 grep: nosuch: No such file or directory\n 4 ob\.txt:a3$"),
    # sdiff, diff3, patch: not here, with a pointer to diff
    ('sdiff a b; echo "status $?"; patch -p1 < /dev/null; echo "status $?"', 0, r"sdiff: command not found\n.*diff -y A B\nstatus 127\n.*patch: command not found\n.*there are diff and cmp\.\nstatus 127"),
    # every program starts afresh: the read group of one minimap2 run is not in the next
    ("minimap2 -ax sr -R '@RG\\tID:lane1\\tSM:x' data/reference.fa data/NA12878_R1.fastq 2>/dev/null | grep -c 'RG:Z:lane1' | sed 's/[0-9][0-9]*/some/'; minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq 2>/dev/null | grep -c 'RG:Z'", None, r'^some\n0$'),
    # ---- October 2026: what a review of the terminal turned up, as it shows at the prompt ----
    # a command that asks (rm -i, cp -i, mv -i): the answer comes from its input; at the terminal nobody can answer, and that is "no"
    ('echo x > ri.txt; rm -i ri.txt; echo "status $?"; ls ri.txt; echo y | rm -i ri.txt; ls ri.txt 2>&1 | grep -c "No such"', 0, r"^rm: remove regular file 'ri\.txt'\? ?\n.*cannot take an answer.*\nstatus 0\nri\.txt\nrm: remove regular file 'ri\.txt'\? ?1$"),
    ('echo 1 > ci1; echo 2 > ci2; cp -i ci1 ci2; cat ci2; echo n | mv -i ci1 ci2; cat ci2; echo y | cp -i ci1 ci2; cat ci2', 0, r"^cp: overwrite 'ci2'\? ?\n.*counted as \"no\".*\n2\nmv: overwrite 'ci2'\? ?2\ncp: overwrite 'ci2'\? ?1$"),
    # the groups of patterns, +( ) and !( ): on at the prompt, off in a script until  shopt -s extglob
    ('shopt extglob | tr -s " \\t" " "; touch eg1.txt eg2.txt eg.log; ls eg!(*.log); ls eg+([0-9]).txt | wc -l; printf "echo eg+([0-9]).txt\\n" > eg.sh; bash eg.sh; echo "status $?"; printf "shopt -s extglob\\necho eg+([0-9]).txt\\n" > eg2.sh; bash eg2.sh', 0, r"^extglob on\neg1\.txt\neg2\.txt\n2\neg\.sh: line 1: syntax error near unexpected token `\('\neg\.sh: line 1: `echo eg\+\(\[0-9\]\)\.txt'\nstatus 2\neg1\.txt eg2\.txt$"),
    # file looks at what is in a file
    ("file sorted.bam data/NA12878_R1.fastq data/reference.fa variants.vcf | sed 's/  */ /'; printf '#!/usr/bin/env bash\\necho hi\\n' > fs.sh; file fs.sh; printf '\\x00\\x01\\x02' > fb.bin; file -b fb.bin; file -b --mime-type variants.vcf", 0, r"^sorted\.bam: Blocked GNU Zip Format \(BGZF; gzip compatible\), block length \d+\ndata/NA12878_R1\.fastq: ASCII text\ndata/reference\.fa: ASCII text\nvariants\.vcf: Variant Call Format \(VCF\) version 4\.2, ASCII text\nfs\.sh: Bourne-Again shell script, ASCII text executable\ndata\ntext/plain$"),
    # exec > >(tee FILE) 2>&1 at the top of a script: what it prints is on the screen and in the file
    ("printf 'exec > >(tee run.log) 2>&1\\necho one\\nls nosuch-file\\necho two\\n' > et.sh; bash et.sh; echo \"status $?\"; wc -l < run.log; grep -c nosuch-file run.log", 0, r"^one\nls: cannot access 'nosuch-file': No such file or directory\ntwo\nstatus 0\n3\n1$"),
    # timeout stops what the page carries out itself; the status is 124 (137 after -s KILL)
    ('timeout 0.2 sleep 5; echo "status $?"; timeout -s KILL 0.2 sleep 5; echo "status $?"; timeout 5 echo ok; timeout 0.3 bash -c "while true; do :; done"; echo "status $?"', 0, r"^status 124\nstatus 137\nok\nstatus 124$"),
    # a command whose reader stops early has the status 141, as on Linux – when it had much more to write
    ('seq 1 200000 | head -n 2; echo "${PIPESTATUS[@]}"; samtools view sorted.bam | head -n 1 | cut -f 3; echo "${PIPESTATUS[@]}"; set -o pipefail; samtools view sorted.bam | head -n 1 > /dev/null; echo "status $?"; set +o pipefail; seq 1 5 | head -n 1; echo "${PIPESTATUS[@]}"', 0, r"^1\n2\n141 0\nhuman_CYP2C19\n141 0 0\n.*SIGPIPE.*\nstatus 141\n1\n0 0$"),
    # fgrep, unexpand, umask
    ('echo "a.b axb" | tr " " "\\n" | fgrep -c "a.b"; printf "a       b\\n" | unexpand -a | od -An -c | tr -s " "; umask; umask 077; touch um.txt; mkdir umd; stat -c %a um.txt umd; umask 022; umask -S', 0, r"^1\n a \\t b \\n\n0022\n600\n700\nu=rwx,g=rx,o=rx$"),
    # printf: a format that begins with a dash; the version of the shell, for scripts that ask for it
    ('printf "-----\\n"; echo "status $?"; printf -- "-----\\n"; printf "%s\\n" "-----"; echo "${BASH_VERSINFO[0]}.${BASH_VERSINFO[1]}"; (( BASH_VERSINFO[0] >= 4 )) && echo "bash 4 or later"', 0, r"^bash: printf: --: invalid option\nprintf: usage: printf \[-v var\] format \[arguments\]\nstatus 2\n-----\n-----\n5\.2\nbash 4 or later$"),
    # checksums: -c reads what the program wrote, and says what does not fit
    ('sha256sum data/reference.fa > ok.sha; sha256sum -c ok.sha; sha256sum --tag data/reference.fa | cut -c1-33; sed "s/^../00/" ok.sha > bad.sha; sha256sum -c bad.sha; echo "status $?"; sha256sum -c --quiet ok.sha; echo "status $?"', 0, r"^data/reference\.fa: OK\nSHA256 \(data/reference\.fa\) = [0-9a-f]{4}\ndata/reference\.fa: FAILED\nsha256sum: WARNING: 1 computed checksum did NOT match\nstatus 1\nstatus 0$"),
    # declare -f and type print a function as bash does; ls -la has the rows of . and ..
    ('greet() { local who=${1:-world}; echo "hello $who"; }; declare -f greet; type greet | head -n 1; ls -la tr | head -n 3 | awk "{print \\$1, \\$NF}"', 0, r"^greet \(\) \n\{ \n    local who=\$\{1:-world\};\n    echo \"hello \$who\"\n\}\ngreet is a function\ntotal \d+\ndrwxr-xr-x \.\ndrwxr-xr-x \.\.$"),
    # ---- October 2026, the second review: what shows only in the page, or needs programs that a test computer may lack ----
    # the variables that the shell exports reach the programs – awk's ENVIRON, jq's env – and the others do not
    ("export SAMPLE=NA12878; DEPTH=20; awk 'BEGIN { print ENVIRON[\"SAMPLE\"] \"|\" ENVIRON[\"DEPTH\"] \"|\" ENVIRON[\"HOME\"] }'; MINQ=30 jq -rn 'env.MINQ + \"|\" + env.SAMPLE + \"|\" + (env.DEPTH // \"none\")'; env -i jq -n 'env | length'; unset SAMPLE DEPTH", 0, r"^NA12878\|\|/home/student\n30\|NA12878\|none\n0$"),
    # LC_ALL=C: the text tools then count and match bytes, as on Linux
    ("printf 'é\\n' | wc -m; printf 'é\\n' | LC_ALL=C wc -m; echo 'é' | LC_ALL=C sed 's/./X/g'; echo 'é' | sed 's/./X/g'; echo 'aé' | LC_ALL=C grep -o . | wc -l", 0, r"^2\n3\nXX\nX\n3$"),
    # "~" in quotes is a name, not the home folder: the folder is made here, and the programs do not find the file
    ('d="~/qt"; mkdir -p "$d/sub"; ls -d ./~/qt/sub; ls -d ~/qt 2>&1 | grep -c "No such"; samtools view "~/sorted.bam" 2>&1 | grep -c "No such file"; rm -r "./~"; ls -d "~" 2>&1 | grep -c "No such"', 0, r"^\./~/qt/sub\n1\n[12]\n1$"),
    # PATH without the folders of the programs: nothing is found any more, and the terminal says why
    ('PATH=/nowhere; ls; echo "status $?"; PATH=/usr/local/bin:/usr/bin:/bin; ls > /dev/null; echo "status $?"', 0, r"^bash: ls: command not found\n.*PATH is \"/nowhere\".*\nstatus 127\nstatus 0$"),
    # scripts that ask whether a program is there
    ('[ -x "$(command -v samtools)" ] && echo found; [[ -x /usr/bin/awk && -d /usr/bin ]] && echo there; command -v nosuchprog || echo "status $?"; compgen -c | grep -c "^samtools$"; type -t getopt', 0, r"^found\nthere\nstatus 1\n1\nfile$"),
    # set -u and an array that was declared but never given a value: bash stops there – with =() it does not
    ("printf 'set -u\\ndeclare -A c\\nfor k in a b a; do ((c[$k]++)) || true; done\\necho not-reached\\n' > du.sh; bash du.sh; echo \"status $?\"; printf 'set -u\\ndeclare -A c=()\\nfor k in a b a; do ((c[$k]++)) || true; done\\necho \"${c[a]} ${c[b]}\"\\n' > du2.sh; bash du2.sh", 0, r"^du\.sh: line 3: c: unbound variable\nstatus 1\n2 1$"),
    # a reader that stops early when less than a pipe holds was left: status 0 here, and a note that Linux may say 141
    ('set -o pipefail; seq 1 5000 | head -n 1; echo "status $?"; set +o pipefail; seq 1 5000 | head -n 1', 0, r"^1\n.*can fail under set -o pipefail.*\nstatus 0\n1$"),
    # getopt (util-linux): long options of a script; -T says that it is the getopt that knows them
    ("printf 'OPTS=$(getopt -o vo: --long verbose,out: -n demo.sh -- \"$@\") || exit 2\\neval set -- \"$OPTS\"\\nwhile true; do case \"$1\" in -v|--verbose) V=1; shift;; -o|--out) O=$2; shift 2;; --) shift; break;; esac; done\\necho \"v=${V:-0} o=${O:-none} rest=$*\"\\n' > go.sh; bash go.sh --out 'my file.txt' reads.fq -v; bash go.sh --nosuch; echo \"status $?\"; getopt -T; echo \"status $?\"", 0, r"^v=1 o=my file\.txt rest=reads\.fq\ndemo\.sh: unrecognized option '--nosuch'\nstatus 2\nstatus 4$"),
    # small programs that scripts call in passing
    ('tty; echo x | tty; logname; groups; locale charmap; stdbuf -oL echo line; sync; echo "status $?"', 0, r"^/dev/pts/0\nnot a tty\nstudent\nstudent\nUTF-8\nline\nstatus 0$"),
    # … and what is not there says what to use instead
    ('mkfifo pipe1; echo "status $?"; dos2unix x.txt; echo "status $?"; exec {fd}> x.txt', 127, r"mkfifo: command not found\n.*no named pipes.*\nstatus 127\n.*dos2unix: command not found\n.*carriage returns.*\nstatus 127\n.*\{fd\}: (command )?not found\n.*from 3 to 9"),
    # wc: columns of 7 for what comes through a pipe or a here-string, as wide as the numbers for a file
    ("echo 'a b' | wc; wc <<< 'a b c'; printf 'x\\n' > w1.txt; wc w1.txt; wc < w1.txt; cat w1.txt | wc -l", 0, r"^1       2       4\n      1       3       6\n1 1 2 w1\.txt\n1 1 2\n1$"),  # (the test takes the blanks off the start of the text)
    # time: TIMEFORMAT and -p
    ("TIMEFORMAT='took %R s'; time true; unset TIMEFORMAT; time -p true", 0, r"^took \d+\.\d{3} s\nreal \d+\.\d\d\nuser \d+\.\d\d\nsys \d+\.\d\d$"),
    # caller in a die() function; builtin is for what the shell carries out itself
    ("printf 'die() { echo \"error at line $(caller 0 | cut -d\" \" -f1): $*\"; exit 1; }\\ncheck() { [[ -s \"$1\" ]] || die \"$1 is missing\"; }\\ncheck nosuch.bam\\n' > cl.sh; bash cl.sh; echo \"status $?\"; builtin ls; echo \"status $?\"", 0, r"^error at line 2: nosuch\.bam is missing\nstatus 1\nbash: builtin: ls: not a shell builtin\nstatus 1$"),
    # ---- October 2026, the third review: empty names, the first line of a script, line ends of Windows, the options of bash ----
    # the empty name ("" – a variable that was never set) is no file: the tests are false, and nothing is moved or copied there
    ('OUT=; [ -d "$OUT" ] && echo dir; [ -e "$OUT" ] || echo "no file"; echo x > keep.txt; mv keep.txt "$OUT"; echo "status $?"; cp keep.txt "$OUT"; echo "status $?"; ls keep.txt; rm -rf "$OUT"; ls -d data; pwd', 0, r"^no file\nmv: cannot move 'keep\.txt' to '': No such file or directory\nstatus 1\ncp: cannot create regular file '': No such file or directory\nstatus 1\nkeep\.txt\ndata\n/home/student/t$"),
    # hash NAME fails for a program that is not there; a loop that was left with  cond && break  has the status 0
    ('hash samtools && echo "have samtools"; hash bwa 2> /dev/null || echo "no bwa"; hash nosuchprog; echo "status $?"; for f in nosuch.fa data/reference.fa; do [[ -s $f ]] && break; done; echo "status $? $f"', 0, r"^have samtools\nno bwa\nbash: hash: nosuchprog: not found\nstatus 1\nstatus 0 data/reference\.fa$"),
    # a file whose first line names a program that is not here: the message and the status of Linux, and a note
    ("printf '#!/usr/bin/env python3\\nprint(1)\\n' > p.py; chmod +x p.py; ./p.py; echo \"status $?\"; printf '#!/usr/bin/perl\\nprint 1;\\n' > p.pl; chmod +x p.pl; ./p.pl; echo \"status $?\"", 0, r"^/usr/bin/env: ‘python3’: No such file or directory\n.*first line of \./p\.py.*python3 is not installed.*\nstatus 127\nbash: \./p\.pl: cannot execute: required file not found\n.*first line of \./p\.pl.*\nstatus 127$"),
    # options on the first line: Linux hands them over as ONE word – "-euo pipefail" fails, "-eu" works, env -S splits
    ("printf '#!/bin/bash -euo pipefail\\necho run\\n' > o.sh; chmod +x o.sh; ./o.sh; echo \"status $?\"; printf '#!/bin/bash -eu\\necho \"$-\"\\n' > o2.sh; chmod +x o2.sh; ./o2.sh; printf '#!/usr/bin/env -S bash -euo pipefail\\necho \"$-\"\\n' > o3.sh; chmod +x o3.sh; ./o3.sh; bash o.sh", 0, r"^/bin/bash: line 0: /bin/bash: \./o\.sh: invalid option name\n.*ONE word.*\nstatus 2\nehuB\nehuB\nrun$"),
    # a file that awk or sed runs
    ("printf '#!/usr/bin/awk -f\\nEND { print NR \" lines\" }\\n' > n.awk; chmod +x n.awk; ./n.awk data/MD5SUMS; printf '#!/bin/sed -f\\ns/human_//\\n' > h.sed; chmod +x h.sed; grep '>' data/reference.fa | ./h.sed | head -n 1", 0, r"^3 lines\n>CYP2C19$"),
    # a script with the line ends of Windows fails as on Linux (the carriage return is a part of the last word), and the terminal says why
    ("printf 'echo one\\r\\nmkdir -p wout\\r\\n' > win.sh; bash win.sh | od -An -c | tr -s ' '; ls -d wout* | od -An -c | tr -s ' '; printf 'set -e\\r\\ncd data\\r\\n' > win2.sh; bash win2.sh; echo \"status $?\"; sed -i 's/\\r$//' win.sh; bash win.sh; rm -r wout*", 0, r"line ends of Windows.*\n o n e \\r \\n\n w o u t \\r \\n\n.*line ends of Windows.*\nwin2\.sh: line 1: set: -\r?: invalid option\n(.*\n)*status [12]\none$"),
    # bash with options: the letters of set, and what bash does not know is refused
    ("bash -f -c 'echo *.zzz $-'; bash -euo pipefail -c 'echo \"$-\"; false; echo no'; echo \"status $?\"; bash -q -c true 2>&1 | head -n 1; bash -o nosuch -c true; echo \"status $?\"; echo 'echo \"from input $-\"' | bash; bash -c 'f() echo x; f'; echo \"status $?\"", 0, r"^\*\.zzz fhBc\nehuBc\nstatus 1\nbash: -q: invalid option\nbash: line 0: bash: nosuch: invalid option name\nstatus 2\nfrom input hBs\nbash: -c: line 1: syntax error near unexpected token `echo'\nbash: -c: line 1: `f\(\) echo x; f'\nstatus 2$"),
    # $- at the prompt: an interactive shell
    ('case $- in *i*) echo "interactive";; *) echo "a script";; esac; printf \'case $- in *i*) echo interactive;; *) echo "a script";; esac\\n\' > i.sh; bash i.sh', 0, r"^interactive\na script$"),
    # ---- October 2026, the fourth review: files changed in place, paths read name by name, the working folder, empty program names ----
    # a file that sed -i has changed can be removed, compressed and written again (an old fault left a ghost of it behind)
    ("printf 'alpha\\nbeta\\n' > g.txt; sed -i 's/alpha/ALPHA/' g.txt; head -n 1 g.txt; rm g.txt; cat g.txt; echo \"status $?\"; seq 3 > g.txt; sed -i '1d' g.txt; gzip g.txt; ls g.txt*; gunzip g.txt.gz; echo \"status $?\"; cat g.txt; sed -i 's/2/two/' g.txt; mv g.txt h.txt; sort -r h.txt -o g.txt; cat g.txt", 0, r"^ALPHA\ncat: g\.txt: No such file or directory\nstatus 1\ng\.txt\.gz\nstatus 0\n2\n3\ntwo\n3$"),
    # … and so can the programs of the practical: after sed -i and rm, bcftools writes the file again; bgzip and bgzip -d work
    ("cp variants.vcf v2.vcf; sed -i 's/human_//' v2.vcf; bgzip v2.vcf; ls v2.vcf*; bgzip -d v2.vcf.gz; echo \"status $?\"; grep -vc '^#' v2.vcf; sed -i 's/CYP2C19/c19/' v2.vcf; rm v2.vcf; bcftools view -H variants.vcf.gz -o v2.vcf; wc -l < v2.vcf; cut -f1 v2.vcf | sort -u | head -n 1; rm v2.vcf", 0, r"^v2\.vcf\.gz\nstatus 0\n60\n60\nhuman_CYP2C19$"),
    # NAME/ is a folder or nothing: a file is not removed, read or written through it; a path through a folder that is not there fails
    ("echo keep > f.txt; rm -f f.txt/; rm -rf f.txt/; cat f.txt/; echo \"status $?\"; echo x > f.txt/; echo \"status $?\"; echo y > nosuch/../f.txt; echo \"status $?\"; rm -f nosuch/../f.txt; cat f.txt", 0, r"^cat: f\.txt/: Not a directory\nstatus 1\nbash: f\.txt/: (Is|Not) a directory\nstatus 1\nbash: nosuch/\.\./f\.txt: No such file or directory\nstatus 1\nkeep$"),
    # the working folder is not moved; it may be removed, and then nothing can be written there
    ("mkdir -p w/sub; cd w; mv . ../w2; echo \"status $?\"; rm -rf ../w; echo \"status $?\"; pwd; echo x > f.txt; echo \"status $?\"; cd ..; pwd; ls -d w w2 2>&1", 2, r"^mv: cannot move '\.' to '\.\./w2': Device or resource busy\nstatus 1\nstatus 0\n/home/student/t/w\nbash: f\.txt: No such file or directory\nstatus 1\n/home/student/t\nls: cannot access 'w': No such file or directory\nls: cannot access 'w2': No such file or directory$"),
    # a typed line that ends in a folder that was removed: the prompt goes to the nearest folder that is there, and says so
    ("mkdir gone; cd gone; rm -r ../gone", 0, r"is not there any more"),
    ("pwd; ls -d gone 2>&1", 2, r"^/home/student/t\nls: cannot access 'gone': No such file or directory$"),
    # cd inside ( ), $( ) or a pipeline is the business of that part alone: cd - still goes back to where this shell was
    ("cd data; ( cd .. ); x=$(cd /tmp; pwd); cd - > /dev/null; pwd; cd data; cd .. | cat; cd -; echo \"$x $OLDPWD\"", 0, r"^/home/student/t\n/home/student/t\n/tmp /home/student/t/data$"),
    # a program name that is empty (a variable that was never set) is a command that is not there – not a line that does nothing
    ("\"$TOOLX\" view data/reference.fa; echo \"status $?\"; if \"$NOPE\"; then echo yes; else echo \"else $?\"; fi; $NOPE; echo \"unquoted $?\"", 0, r"^bash: : command not found\nstatus 127\nbash: : command not found\nelse 127\nunquoted 0$"),
    # a number read from a file with the line ends of Windows is no number until the carriage return is cut off
    ("printf '12\\r\\n' > n.txt; printf '%s\\n' 'n=$(cat n.txt)' 'echo $((n + 1))' 'echo \"status $?\"' '[ \"$n\" -gt 5 ]' 'echo \"status $?\"' 'n=${n%$'\"'\"'\\r'\"'\"'}' 'echo $((n + 1))' > cr.sh; bash cr.sh", 0, r"^cr\.sh: line 2: 12: syntax error: invalid arithmetic operator.*\nstatus 1\ncr\.sh: line 4: \[: 12: integer expression expected\nstatus 2\n13$"),
    # gzip refuses what gzip refuses: a result that is already there, a folder, a file that is not there
    ("echo a > z.txt; gzip -k z.txt; gzip z.txt; echo \"status $?\"; ls z.txt*; mkdir zd; gzip zd; echo \"status $?\"; gzip nosuch.txt; echo \"status $?\"; rm -r z.txt* zd", 0, r"^gzip: z\.txt\.gz already exists;\s+not overwritten\nstatus 2\nz\.txt\nz\.txt\.gz\ngzip: zd is a directory -- ignored\nstatus 2\ngzip: nosuch\.txt: No such file or directory\nstatus 1$"),
    # set with a letter it does not know changes nothing (the -e before it is not switched on)
    ("bash -c 'set -ez 2> /dev/null; false; echo \"still here $-\"'; bash -c 'a=(1 2 3); a=text; echo \"${a[*]}\"; : \"${a[5]:=five}\"; echo \"${!a[*]}\"'", 0, r"^still here hBc\ntext 2 3\n0 1 2 5$"),
    # ---- October 2026, the fifth round: pipelines with a file that cannot be opened, the output of a block, gzip's rules, copies ----
    # a file that cannot be opened fails its own command, not the pipeline: the commands after it run (on an empty input)
    ('sort < nosuch.txt | wc -l; echo "status $? ${PIPESTATUS[*]}"; n=$(grep -c ">" < nosuch.fa | cat); echo "n=[$n] status $?"', 0, r"nosuch\.txt: No such file or directory\n0\nstatus 0 1 0\n.*nosuch\.fa: No such file or directory\nn=\[\] status 0$"),
    # … also in the middle and at the end; a program before it that had written something was ended by SIGPIPE (141)
    ('cat data/MD5SUMS | sort > nodir/out.txt | wc -l; echo "status $? ${PIPESTATUS[*]}"; cut -f 1 data/MD5SUMS | sort > nodir/x; echo "status $? ${PIPESTATUS[*]}"; echo hi | cat < nosuch | cat; echo "status ${PIPESTATUS[*]}"', 0, r"nodir/out\.txt: No such file or directory\n0\nstatus 0 141 1 0\n.*nodir/x: No such file or directory\nstatus 1 141 1\n.*nosuch: No such file or directory\nstatus 0 1 0$"),
    # … and a script under set -e goes on where bash goes on (the status of a pipeline is that of its last command), and stops under pipefail
    ("printf '%s\\n' 'set -e' 'n=$(sort < nosuch.txt | wc -l)' 'echo \"lines: $n\"' 'set -o pipefail' 'm=$(sort < nosuch.txt | wc -l)' 'echo \"not reached\"' > miss.sh; bash miss.sh; echo \"status $?\"", 0, r"^miss\.sh: line 2: nosuch\.txt: No such file or directory\nlines: 0\nmiss\.sh: line 5: nosuch\.txt: No such file or directory\nstatus 1$"),
    # what a block prints is in its file when the next command looks: a count, a header that is written once
    ('{ echo start; wc -l < out.log; } > out.log; cat out.log; for s in A B C; do [ -s table.tsv ] || printf "sample\\treads\\n"; printf "%s\\t%s\\n" "$s" "$(samtools view -c sorted.bam)"; done > table.tsv; wc -l < table.tsv; head -n 2 table.tsv', 0, r"^start\n1\n4\nsample\treads\nA\t7038$"),
    # … and what a function adds to the log that the block around it writes comes in its place
    ('log() { echo "[log] $*" >> run.log; }; { echo "starting"; log "step 1"; samtools view -c sorted.bam; log "step 2"; echo "done"; } >> run.log 2>&1; cat run.log; rm run.log', 0, r"^starting\n\[log\] step 1\n7038\n\[log\] step 2\ndone$"),
    # gzip leaves alone what is compressed already (gzip * in a folder where some files are), and decompresses only what has the suffix
    ('mkdir gz && cd gz && cp ../data/MD5SUMS a.txt && cp a.txt b.txt && gzip a.txt && gzip *; echo "status $?"; ls; gunzip *; echo "status $?"; ls; echo plain > c.txt; gunzip c.txt; echo "status $?"; cd .. && gzip -r gz && ls gz && rm -r gz', 0, r"^gzip: a\.txt\.gz already has \.gz suffix -- unchanged\nstatus 0\na\.txt\.gz\nb\.txt\.gz\nstatus 0\na\.txt\nb\.txt\ngzip: c\.txt: unknown suffix -- ignored\nstatus 2\na\.txt\.gz\nb\.txt\.gz\nc\.txt\.gz$"),
    # a copy keeps its own bytes when the original is cut short or written anew by the terminal's own commands
    ('samtools view -b sorted.bam -o one.bam; cp one.bam two.bam; truncate -s 100 one.bam; samtools view -c two.bam; mv two.bam three.bam; printf "\\037\\213" > two.bam; samtools view -c three.bam; wc -c < two.bam; rm one.bam two.bam three.bam', 0, r"^7038\n7038\n2$"),
    # exec NAME for a program that is not there: the message goes where 2> sends it, and the script ends with 127
    ("bash -c 'exec nosuchprog 2> /dev/null; echo not reached'; echo \"status $?\"; bash -c 'exec nosuchprog 2> nodir/e; echo \"goes on $?\"'", 0, r"^status 127\nbash: line 1: nodir/e: No such file or directory\ngoes on 1$"),
    # ---- October 2026, the fifth independent check (files only): same names into one folder, files written by name, exec >>, sed -i on many files ----
    # two files of the same name copied, then moved, into one folder: the second must not silently replace the first
    ('mkdir -p s1 s2 all; echo one > s1/stats.txt; echo two > s2/stats.txt; cp s1/stats.txt s2/stats.txt all/; echo "status $?"; cat all/stats.txt; mv s1/stats.txt s2/stats.txt all/; echo "status $?"; ls s2; rm -r s1 s2 all', 0, r"^cp: will not overwrite just-created 'all/stats\.txt' with 's2/stats\.txt'\nstatus 1\none\nmv: will not overwrite just-created 'all/stats\.txt' with 's2/stats\.txt'\nstatus 1\nstats\.txt$"),
    # a program writes its file by name while > (with nothing to write) stands on the same command: the file keeps what the program wrote
    ('samtools sort -o s2.bam sorted.bam > s2.bam 2>&1; samtools view -c s2.bam; log() { echo "[log] $*" >> run2.log; }; main() { log start; samtools index sorted.bam; log end; }; main > run2.log 2>&1; cat run2.log; rm s2.bam run2.log', 0, r"^7038\n\[log\] start\n\[log\] end$"),
    # a script that adds its output to a large log with exec >> : the log keeps what it had
    ("seq 60000 > big.log; printf '%s\\n' 'exec >> big.log 2>&1' 'echo \"run starts\"' 'samtools view -c sorted.bam' 'ls nosuch' > job.sh; bash job.sh; echo \"status $?\"; wc -l < big.log; tail -n 3 big.log | cut -c 1-12; rm big.log job.sh", 0, r"^status 2\n60003\nrun starts\n7038\nls: cannot a$"),
    # sed -i on many files in one call (an old fault of the runtime made it stop part-way with 'couldn't open temporary file')
    ('mkdir many; for i in $(seq 40); do echo "sample$i human_chr10" > many/s$i.txt; done; sed -i "s/human_//" many/*.txt; echo "status $?"; grep -L human many/*.txt | wc -l; ls many | wc -l; rm -r many', 0, r"^status 0\n40\n40$"),
    # a script stays executable through gzip and gunzip, and when a line is added to it
    ("printf '#!/bin/bash\\necho ran\\n' > job2.sh; chmod 750 job2.sh; gzip job2.sh; gunzip job2.sh.gz; ./job2.sh; echo 'echo again' >> job2.sh; stat -c %a job2.sh; ./job2.sh | tail -n 1; rm job2.sh", 0, r"^ran\n750\nagain$"),
    # zgrep with several files names each of them; a file that is not compressed is searched as it is
    ("cp data/NA12878_R1.fastq r1.fq; cp data/NA12878_R2.fastq r2.fq; gzip r1.fq r2.fq; zgrep -c '^+$' r1.fq.gz r2.fq.gz; zgrep -c '^+$' data/NA12878_R1.fastq; rm r1.fq.gz r2.fq.gz", 0, r"^r1\.fq\.gz:(\d+)\nr2\.fq\.gz:\1\n\1$"),
    # find -exec rm -r on a folder: find then cannot look into it, says so and ends with status 1 (with -depth it does not)
    ('mkdir -p work/tmp work/keep; touch work/tmp/a; find work -name tmp -exec rm -r {} \; ; echo "status $?"; ls work; find work -depth -name keep -exec rm -r {} \; ; echo "status $?"; rmdir work', 0, r"^find: ‘work/tmp’: No such file or directory\nstatus 1\nkeep\nstatus 0$"),
    # output and messages added to one log with >> and 2>> come in the order written; the message of a file that cannot be opened goes where 2>&1 sent it
    ('{ echo "step 1"; ls nosuch; echo "step 2"; } >> both.log 2>> both.log; sed "s/^ls: .*/ls-message/" both.log; sort > out.txt 2>&1 < nosuch.txt; echo "status $?"; cat out.txt; rm both.log out.txt', 0, r"^step 1\nls-message\nstep 2\nstatus 1\nbash: nosuch\.txt: No such file or directory$"),
    # ---- October 2026, the sixth independent check (whole analyses): read-only copies, samtools and bowtie2 at the edges, long sums, long output, grep -oP ----
    # a read-only file of one's own (a copy of an input keeps its permissions): sed -i and gzip put a new file in its place, as on Linux; writing into it is refused
    ("cp data/reference.fa ref.fa; chmod 444 ref.fa; sed -i 's/human_//' ref.fa; echo \"status $?\"; grep -c '>CYP' ref.fa; stat -c %a ref.fa; gzip ref.fa; echo \"status $?\"; ls ref.fa*; stat -c %a ref.fa.gz; echo x >> ref.fa.gz; echo \"status $?\"; rm -f ref.fa.gz", 0, r"^status 0\n2\n444\nstatus 0\nref\.fa\.gz\n444\nbash: ref\.fa\.gz: Permission denied\nstatus 1$"),
    # … but the course data stays as it is
    ("sed -i 's/human_//' ~/data/reference.fa; echo \"status $?\"; grep -c '>human_' ~/data/reference.fa", 0, r"^sed: ~/data/reference\.fa is read-only \(the course data\): the change to it was undone\nstatus 1\n2$"),
    # a count is text, whatever the other options say; tview prints text with -d T; reheader -c is refused with a way out
    ("samtools view -c -b sorted.bam; n=$(samtools view -b -c -F 4 sorted.bam); echo \"mapped=[$n]\"; samtools tview -d T -p human_CYP2C19:11616 sorted.bam data/reference.fa | wc -l; samtools reheader -c 'sed s/human_/h_/' sorted.bam > rh.bam; echo \"status $?\"; rm -f rh.bam", 0, r"^7038\nmapped=\[6817\]\n\d{2,}\nsamtools reheader: -c \(--command\) runs another program[^\n]*\nstatus 1$"),
    # a subsample with a seed other than 0 is not the one Linux takes: the terminal says so; with seed 0 it is
    ("samtools view -s 42.25 -c sorted.bam; samtools view -s 0.25 -c sorted.bam", 0, r"^(samtools view: with the seed 42 this program keeps other reads than samtools on Linux[^\n]*\n\d+|\d+\nsamtools view: with the seed 42 this program keeps other reads than samtools on Linux[^\n]*)\n1746$"),
    # bowtie2: an index that is not there, a file of reads that is not there – the messages and statuses of Linux
    ("bowtie2 -x nosuchidx -U data/NA12878_R1.fastq -S o.sam; echo \"status $?\"; bowtie2-build -q data/reference.fa bt > /dev/null; bowtie2 -x bt -U nosuch.fq -S o.sam; echo \"status $?\"; ls o.sam; rm -f bt.*", 0, r"^\(ERR\): \"nosuchidx\" does not exist or is not a Bowtie 2 index\nExiting now \.\.\.\nstatus 255\nstat: Bad file descriptor\nWarning: Could not open read file \"nosuch\.fq\" for reading; skipping\.\.\.\nError: No input read files were valid\n\(ERR\): bowtie2-align exited with value 1\nstatus 1\nls: cannot access 'o\.sam': No such file or directory$"),
    # the sum of a long column with paste and bc (56,000 numbers), and the same with awk
    ("samtools depth -a sorted.bam | cut -f 3 | paste -sd+ | bc; samtools depth -a sorted.bam | awk '{ s += $3 } END { print s }'", 0, r"^(\d{5,})\n\1$"),
    # of a very long output the beginning and the end are shown
    ("seq 1 5000", 0, r"^1\n2\n[\s\S]*\n2000\n… 2,000 lines are not shown here[^\n]*\n4001\n[\s\S]*\n5000$"),
    # grep -oP with \K, on real data
    ("grep -v '^#' variants.vcf | grep -oP '\\tDP=\\K\\d+' | sort -n | tail -n 1; grep -v '^#' variants.vcf | head -n 1 | grep -oP '.*;MQ=\\K\\d+'; echo 'results/vcf/calls.vcf.gz' | grep -oP '.*/\\K.*'", 0, r"^\d+\n\d+\ncalls\.vcf\.gz$"),
    # the newest of two folders is the one a program last wrote a new file into; and "was something piped in?"
    ("mkdir -p runs_a runs_b; sleep 0.05; samtools flagstat sorted.bam > runs_a/flagstat.txt; ls -td runs_a runs_b | head -n 1; rm -r runs_a runs_b; samtools view -h sorted.bam | { if [ -p /dev/stdin ]; then samtools view -c -; else echo 'nothing piped in'; fi; }", 0, r"^runs_a\n7038$"),
    # ---- October 2026, the seventh and eighth independent checks: grep -P is a real grep, "was something piped in?", read-only files, bc, bowtie2 -x ----
    # grep -P is GNU grep with PCRE2: a line with a carriage return, a number in the group of option letters, "--", what -o shows after \K when a field is empty, a look-behind that PCRE2 refuses, the version
    ("printf 'k=v\\r\\n' > crlf.txt; grep -cP '^k=.+$' crlf.txt; grep -v '^#' variants.vcf | grep -oPm1 'DP=\\K\\d+'; grep -P -- '-1' <<< 'a-1'; echo '1,2,,4' | grep -oP ',\\K[^,]*'; echo 'a b ab' | grep -cP '(?<=a+)b'; echo \"status $?\"; grep -P --version | head -n 1; rm crlf.txt", 0, r"^1\n\d+\na-1\n2\ngrep: lookbehind assertion is not fixed length\nstatus 2\ngrep \(GNU grep\) 3\.11$"),
    # … and a pattern that would try for ever ends with PCRE's limit, as on Linux
    ("printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab\\n' | grep -cP '^(?=a)(a+)+$'; echo \"status $?\"", 0, r"^grep: \(standard input\): exceeded PCRE's backtracking limit\nstatus 2$"),
    # "was something piped in?" in a script that is given /dev/null, a pipe, nothing; the output of a function that goes to a file
    ("printf 'if [ -p /dev/stdin ]; then echo piped; cat; else echo \"arg: $1\"; fi\\n' > in.sh; bash in.sh x < /dev/null; echo hi | bash in.sh x; bash -c '[ -c /dev/stdin ] && echo device' < /dev/null; f() { [ -f /dev/stdout ] && echo file; }; f > o.txt; cat o.txt; rm in.sh o.txt", 0, r"^arg: x\npiped\nhi\ndevice\nfile$"),
    # a read-only copy: its times can be set (touch), and gzip -f puts a new file in the place of a read-only result
    ("cp data/reference.fa r.fa; chmod 444 r.fa; stat -c %a r.fa; touch r.fa; echo \"status $?\"; gzip -k r.fa; chmod 444 r.fa.gz; gzip -f r.fa; echo \"status $?\"; ls r.fa*; rm -f r.fa.gz", 0, r"^444\nstatus 0\nstatus 0\nr\.fa\.gz$"),
    # bc prints an assignment in parentheses, and breaks a long number after 68 digits; $a of an empty array has no value
    ("echo 'x = 5; (x = 6); x' | bc | tr '\\n' ' '; echo; echo '2^228' | bc | wc -l; ( set -u; a=(); echo \"[$a]\" ); echo \"status $?\"", 0, r"^6 6 \n2\nbash: a: unbound variable\nstatus 1$"),
    # bowtie2 -x with the name of one file of the index: the wrapper's message, and no output file
    ("bowtie2-build -q data/reference.fa bt > /dev/null; bowtie2 -x bt.1.bt2 -U data/NA12878_R1.fastq -S o.sam; echo \"status $?\"; ls o.sam 2> /dev/null | wc -l; rm -f bt.*", 0, r"^\(ERR\): \"bt\.1\.bt2\" does not exist or is not a Bowtie 2 index\nExiting now \.\.\.\nstatus 255\n0$"),
    # what the page has to say about a program's run goes where the program's messages go: > FILE 2>&1
    ("sed -i 's/human_//' ~/data/reference.fa > sed.log 2>&1; echo \"status $?\"; cat sed.log; rm sed.log", 0, r"^status 1\nsed: ~/data/reference\.fa is read-only \(the course data\): the change to it was undone$"),
    # pattern groups work at the prompt, as in a terminal on Linux – and need shopt -s extglob in a script
    ("mkdir -p eg && touch eg/keep.txt eg/a.tmp && rm eg/!(keep.txt) && ls eg; printf 'ls eg/!(keep.txt)\\n' > eg.sh; bash eg.sh; echo \"status $?\"; printf 'shopt -s extglob\\nls eg/!(nothing)\\n' > eg.sh; bash eg.sh; rm -r eg eg.sh", 0, r"^keep\.txt\neg\.sh: line 1: syntax error near unexpected token `\('\neg\.sh: line 1: `ls eg/!\(keep\.txt\)'\nstatus 2\neg/keep\.txt$"),
]

bad = []
def run(page, c, want, pat):
    t0 = time.time()
    r = term(page, c)
    txt = r['text'].replace('\r', '')
    txt = re.sub(r'\n?\s*✦ Ask the AI assistant about this error\s*', '\n', txt)
    ok = (want is None or r['code'] == want) and (pat is None or re.search(pat, txt.strip(), re.M) is not None)
    dt = time.time() - t0
    print(('ok   ' if ok else 'BAD  ') + f'[{r["code"]}] {dt:5.1f}s  {c[:170]}', flush=True)
    if not ok or want is None:
        if not ok:
            bad.append(c)
            print('     want exit', want, 'pattern', pat)
        print('\n'.join('     | ' + l for l in txt.strip().split('\n')[-10:]), flush=True)
    return r

with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        for c in SETUP:
            r = term(page, c)
            print('setup', r['code'], c[:100], flush=True)
        for c, want, pat in CASES:
            run(page, c, want, pat)
        print('\n'.join(l for l in logs if 'PAGEERROR' in l)[:3000])
        print(f'\n{len(bad)} BAD of {len(CASES)}')
        for c in bad:
            print('  - ' + c[:200])
        b.close()
    finally:
        srv.terminate()
