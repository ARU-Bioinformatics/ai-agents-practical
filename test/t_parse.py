"""How the page reads a reply of the agent's model: step, file, report – and which words of a command
are paths that lead out of its folder (such commands are left out of the script made from a run)."""
import sys, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8871
F = '```'
CASES = [
    # (reply, expected subset of parseReply's result, expected report text or None)
    (f"I look at the files.\n{F}bash\nls -l data\n{F}", dict(final=False, bash='ls -l data', file=None), None),
    (f"I look.\n{F}sh\n$ ls -l data\n$ head -2 data/x\n{F}", dict(final=False, bash='ls -l data\nhead -2 data/x'), None),
    (f"{F}shell\nls\n{F}\nand then\n{F}bash\npwd\n{F}", dict(final=False, bash='ls', more=1), None),
    (f"I write the script.\n{F}file:analysis.sh\n#!/usr/bin/env bash\necho hi\n{F}\n{F}bash\nbash analysis.sh\n{F}", dict(final=False, bash='bash analysis.sh'), None),
    (f"{F}file: notes/readme.md\n# Notes\n{F}", dict(final=False, bash=None), None),
    ("REPORT\nThe genotype is 0/1.", dict(final=True, bash=None), 'The genotype is 0/1.'),
    ("## REPORT\n\nThe genotype is 0/1.", dict(final=True), 'The genotype is 0/1.'),
    ("**REPORT**\nThe genotype is 0/1.", dict(final=True), 'The genotype is 0/1.'),
    ("REPORT: the genotype is 0/1.", dict(final=True), 'the genotype is 0/1.'),
    ("The analysis is complete.\n\nREPORT\nThe genotype is 0/1.", dict(final=True), 'The genotype is 0/1.'),
    ("Everything worked.\n\n### Final Report\n\nThe genotype is 0/1.", dict(final=True), 'The genotype is 0/1.'),
    ("FINAL REPORT\nThe genotype is 0/1.", dict(final=True), 'The genotype is 0/1.'),
    (f"REPORT\nI ran:\n{F}bash\nminimap2 -ax sr ref.fa r1.fq r2.fq\n{F}\nGenotype 0/1.", dict(final=True), f"I ran:\n{F}bash\nminimap2 -ax sr ref.fa r1.fq r2.fq\n{F}\nGenotype 0/1."),
    # not a report: a step whose text has the word at the start of a line
    (f"Now I call the variants.\nReport the genotype afterwards.\n{F}bash\nbcftools call -mv x\n{F}", dict(final=False, bash='bcftools call -mv x'), None),
    (f"{F}bash\nbcftools view -H v.vcf.gz\n{F}\nREPORT\nGenotype 0/1.", dict(final=False, bash='bcftools view -H v.vcf.gz'), None),
    ("I think the next step is to map the reads, but first let me consider the options.", dict(final=False, bash=None, file=None, unlabelled=0), None),
    (f"Next:\n{F}\nsamtools index x.bam\n{F}", dict(final=False, bash=None, unlabelled=1), None),
    (f"I start.\n{F}bash\nminimap2 -ax sr data/reference.fa", dict(final=False, bash=None, open=True), None),
    (f"{F}python\nprint(1)\n{F}", dict(final=False, bash=None, unlabelled=0), None),
    ("Reporting what I found so far: nothing.", dict(final=False), None),
    # a file block that is never closed: the reply counts as cut off
    (f"I write it.\n{F}file:README.md\n# A\n{F}bash\nls", dict(final=False, bash=None, file=None, open=True, say='I write it.'), None),
    (f"{F}bash\nmkdir -p results\n{F}\nThen the file.\n{F}file:README.md\n# A\n{F}bash\nls\n{F}\nmore", dict(final=False, bash='mkdir -p results', file=None, open=True), None),
    # a fence of tildes is a code block, too
    ("I look.\n~~~bash\nls -l data\n~~~", dict(final=False, bash='ls -l data', file=None), None),
    ("~~~file:notes.txt\nhello\n~~~\n~~~bash\ncat notes.txt\n~~~", dict(final=False, bash='cat notes.txt', file='notes.txt'), None),
    # … but tildes inside a file block are part of the file: they do not end it, and what is between them is not run
    (f"A README that shows a command.\n{F}file:README.md\n# How to run\n~~~bash\nrm -rf results\n~~~\nThat is all.\n{F}", dict(final=False, bash=None, file='README.md', more=0), None),
    (f"{F}file:README.md\n~~~bash\nbash rerun.sh\n~~~\n{F}\n{F}bash\nls\n{F}", dict(final=False, bash='ls', file='README.md', more=0), None),
]
# (reply, the name and the whole text of the file it writes, the command it runs) – a file that holds code fences of its own
B3 = '```'
README = f"# How to run\n\n{B3}bash\nbash rerun.sh\n{B3}\n\nThe result:\n\n{B3}text\n0/1\n{B3}\n"
BARE = f"# Title\n\nRun it:\n\n{B3}\nbash rerun.sh\n{B3}\n\nDone.\n"
FILES = [
    (f"I write the README.\n{B3}file:README.md\n{README}{B3}", 'README.md', README, None),
    (f"{B3}file:README.md\n{README}{B3}\n{B3}bash\ncat README.md\n{B3}", 'README.md', README, 'cat README.md'),
    (f"Four backticks around it.\n{B3}`file:README.md\n{README}\nA bare block:\n{B3}\nx\n{B3}\n{B3}`\n{B3}bash\nls\n{B3}", 'README.md', README + f"\nA bare block:\n{B3}\nx\n{B3}\n", 'ls'),
    (f"{B3}file:analysis.sh\n#!/usr/bin/env bash\necho hi\n{B3}\n{B3}bash\nbash analysis.sh\n{B3}", 'analysis.sh', "#!/usr/bin/env bash\necho hi\n", 'bash analysis.sh'),
    # a file block that is never closed (cut off, or the closing fence is missing): no file from a part of it, nothing run
    (f"{B3}file:analysis.sh\necho hi\n{B3}bash\nbash analysis.sh\n{B3}", None, None, None),
    (f"{B3}file:README.md\n# Analysis\n{B3}bash\nrm -rf results\n{B3}\nmore of the", None, None, None),
    (f"{B3}file:README.md\n# Analysis\n{B3}bash\nrm -rf results", None, None, None),
    # a Markdown file whose own code blocks have no name
    (f"{B3}file:README.md\n{BARE}{B3}", 'README.md', BARE, None),
    (f"The README, then a look.\n{B3}file:README.md\n{BARE}{B3}\n{B3}bash\ncat README.md\n{B3}", 'README.md', BARE, 'cat README.md'),
    (f"{B3}file:docs/NOTES.md\n{BARE}\n{B3}bash\nls\n{B3}\n{B3}", 'docs/NOTES.md', BARE + f"\n{B3}bash\nls\n{B3}\n", None),
    # … but in another file the first bare fence ends the block
    (f"{B3}file:notes.txt\nhello\n{B3}\nThe output was:\n{B3}\nx\n{B3}", 'notes.txt', "hello\n", None),
    # a file block in tildes, with backtick fences inside: part of the file, not run
    (f"~~~file:README.md\n{README}~~~", 'README.md', README, None),
    (f"~~~file:README.md\n{README}~~~\n{B3}bash\nls\n{B3}", 'README.md', README, 'ls'),
    # a block inside a list item loses the list's indentation (the end of a here-document must be at the start of its line)
    (f"1. The script:\n\n   {B3}file:run.sh\n   cat > x.txt <<EOF\n     hello\n   EOF\n   {B3}\n\n2. Run it:\n\n   {B3}bash\n   bash run.sh\n   {B3}\n", 'run.sh', "cat > x.txt <<EOF\n  hello\nEOF\n", 'bash run.sh'),
    # line ends of Windows do not get into files or commands
    (f"{B3}file:a.txt\r\nline one\r\nline two\r\n{B3}\r\n{B3}bash\r\ncat a.txt\r\n{B3}\r\n", 'a.txt', "line one\nline two\n", 'cat a.txt'),
]
# (a command of a run in /home/student/runs/3-auto, the command as the script has it, is the folder still named in it?)
# – in the script made from a run, "$RUN_FOLDER" stands for the run's folder, wherever a command named it in full
A3 = '/home/student/runs/3-auto'
ANCHOR = [
    (f'cd {A3}/results && ls', 'cd "$RUN_FOLDER"/results && ls', False),
    (f'cd {A3}', 'cd "$RUN_FOLDER"', False),
    (f'cp a {A3}/', 'cp a "$RUN_FOLDER"/', False),
    ('cd ~/runs/3-auto/results', 'cd "$RUN_FOLDER"/results', False),
    ('cd $HOME/runs/3-auto && ls', 'cd "$RUN_FOLDER" && ls', False),
    ('cd "$HOME"/runs/3-auto/x', 'cd "$RUN_FOLDER"/x', False),
    ('cd "${HOME}/runs/3-auto/x y"', 'cd "$RUN_FOLDER/x y"', False),
    (f'minimap2 -ax sr {A3}/data/reference.fa {A3}/data/R1.fastq > {A3}/results/mapped.sam', 'minimap2 -ax sr "$RUN_FOLDER"/data/reference.fa "$RUN_FOLDER"/data/R1.fastq > "$RUN_FOLDER"/results/mapped.sam', False),
    (f'sort -o{A3}/sorted.txt x', 'sort -o"$RUN_FOLDER"/sorted.txt x', False),
    (f'bcftools view --output={A3}/y.vcf x.vcf', 'bcftools view --output="$RUN_FOLDER"/y.vcf x.vcf', False),
    (f'OUT={A3}/results; mkdir -p "$OUT"', 'OUT="$RUN_FOLDER"/results; mkdir -p "$OUT"', False),
    (f'OUT="{A3}/results"', 'OUT="$RUN_FOLDER/results"', False),
    ('OUT=~/runs/3-auto/results', 'OUT="$RUN_FOLDER"/results', False),
    ('export PATH=$PATH:~/runs/3-auto/bin', 'export PATH=$PATH:"$RUN_FOLDER"/bin', False),
    (f'FILES=(~/runs/3-auto/a {A3}/b)', 'FILES=("$RUN_FOLDER"/a "$RUN_FOLDER"/b)', False),
    (f'{A3}/show.sh > x', '"$RUN_FOLDER"/show.sh > x', False),
    (f'for f in {A3}/*.bam; do samtools index "$f"; done', 'for f in "$RUN_FOLDER"/*.bam; do samtools index "$f"; done', False),
    (f'if [[ -f ~/runs/3-auto/x && -d {A3} ]]; then echo yes; fi', 'if [[ -f "$RUN_FOLDER"/x && -d "$RUN_FOLDER" ]]; then echo yes; fi', False),
    (f'echo "saved to {A3}/x and {A3}."', 'echo "saved to $RUN_FOLDER/x and $RUN_FOLDER."', False),
    (f'echo "it\'s in {A3}"', 'echo "it\'s in $RUN_FOLDER"', False),
    ('echo "n: $(wc -l < ~/runs/3-auto/x.txt)"', 'echo "n: $(wc -l < "$RUN_FOLDER"/x.txt)"', False),
    (f'x=`cat {A3}/x`', 'x=`cat "$RUN_FOLDER"/x`', False),
    (f'cat <<EOF > a.txt; ls {A3}\nx {A3}/y\nEOF', 'cat <<EOF > a.txt; ls "$RUN_FOLDER"\nx $RUN_FOLDER/y\nEOF', False),
    (f'ls {A3}/my\\ file', 'ls "$RUN_FOLDER"/my\\ file', False),
    (f'RUN_DIR={A3} && cd $RUN_DIR/results && ls', 'RUN_DIR="$RUN_FOLDER" && cd $RUN_DIR/results && ls', False),
    # another folder: left as it is (and not counted as the run's folder)
    (f'ls {A3}_old {A3}.bak {A3}-2 /home/student/runs/3-automatic {A3}*', None, False),
    (f'ls {A3}\\ x', None, False),
    # inside "…" and in a here-document a quote is a character like any other
    (f'cat > config.sh <<EOF\nOUTDIR="{A3}/my results"\nREF=\'{A3}/data/reference.fa\'\nEOF', 'cat > config.sh <<EOF\nOUTDIR="$RUN_FOLDER/my results"\nREF=\'$RUN_FOLDER/data/reference.fa\'\nEOF', False),
    (f'cat > samples.json <<EOF\n{{"r1": "{A3}/data/R1.fastq", "dirs": ["{A3}"]}}\nEOF', 'cat > samples.json <<EOF\n{"r1": "$RUN_FOLDER/data/R1.fastq", "dirs": ["$RUN_FOLDER"]}\nEOF', False),
    (f'echo "the folder is \'{A3}/out\'" > where.txt', 'echo "the folder is \'$RUN_FOLDER/out\'" > where.txt', False),
    (f'echo "REF=\\"{A3}/data/reference.fa\\"" > ref.txt', 'echo "REF=\\"$RUN_FOLDER/data/reference.fa\\"" > ref.txt', False),
    (f'echo "(see {A3}/out); [{A3}]" > n.txt', 'echo "(see $RUN_FOLDER/out); [$RUN_FOLDER]" > n.txt', False),
    # inside '…' and $'…' the quote is closed and opened again around the variable
    (f"echo '{A3}/x' > where.txt", 'echo "$RUN_FOLDER"\'/x\' > where.txt', False),
    (f"echo '{A3}' > where.txt", 'echo "$RUN_FOLDER" > where.txt', False),
    (f"bash -c 'ls {A3}/data && cat {A3}/x'", 'bash -c \'ls \'"$RUN_FOLDER"\'/data && cat \'"$RUN_FOLDER"\'/x\'', False),
    (f"awk 'BEGIN {{ print \"{A3}\" }}'", 'awk \'BEGIN { print "\'"$RUN_FOLDER"\'" }\'', False),
    (f"echo $'{A3}/x'", 'echo "$RUN_FOLDER"$\'/x\'', False),
    # ${…}: the word after the name is expanded like a text
    (f'echo ${{OUT:-{A3}/results}}', 'echo ${OUT:-$RUN_FOLDER/results}', False),
    (f'f={A3}/a.txt; echo "${{f#{A3}/}} ${{#f}} ${{f}}"', 'f="$RUN_FOLDER"/a.txt; echo "${f#$RUN_FOLDER/} ${#f} ${f}"', False),
    # a here-document that is taken as it is becomes one that is expanded: \ before every $, ` and \ of its text
    (f"cat > run.sh <<'EOF'\ncd {A3}/results\nEOF", 'cat > run.sh <<EOF\ncd $RUN_FOLDER/results\nEOF', False),
    (f"cat > run.sh <<'EOF'\ncd {A3}\necho \"$1 `date` \\n\"\nEOF", 'cat > run.sh <<EOF\ncd $RUN_FOLDER\necho "\\$1 \\`date\\` \\\\n"\nEOF', False),
    (f'cat <<-"END" > t.txt\n\t{A3}/x\n\tEND', 'cat <<-END > t.txt\n\t$RUN_FOLDER/x\n\tEND', False),
    ("cat > keep.sh <<'EOF'\necho no folder here $x\nEOF", None, False),
    # where nothing can be put: the folder is still named
    ("bash -c 'ls $HOME/runs/3-auto'", None, True),
    ("ls '~/runs/3-auto'", None, True),
    (f'echo "\\$HOME/runs/3-auto"', None, True),
    ('bcftools view --output=~/runs/3-auto/y.vcf x.vcf', None, True),
    ('ls "~/runs/3-auto"', None, True),
    (f'ls /mnt{A3}/x', None, True),
    (f'ls $BASE{A3}/x', None, True),
    (f'cat > run.sh <<EOF\ncd {A3}/results\nls ~/runs/3-auto\nEOF', 'cat > run.sh <<EOF\ncd $RUN_FOLDER/results\nls ~/runs/3-auto\nEOF', True),
    # a text that cannot be read stays as it is
    ('echo "unterminated', None, False),
    ('echo hello', None, False),
]
# (a command, the words in it that lead out of the folder it runs in) – such a command is left out of rerun.sh
OUTSIDE = [
    ("samtools view -c ~/mapped.bam", ['~/mapped.bam']),
    ("rm -f ~/later.bam ~/later.txt", ['~/later.bam', '~/later.txt']),
    ("if [ -f ~/later2.txt ]; then rm ~/later2.txt; fi", ['~/later2.txt']),
    ("rm -rf ~/scratch_*", ['~/scratch_*']),
    ("bcftools mpileup -f data/reference.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz", []),
    ("awk '/^>/ {print}' data/reference.fa", []),
    ("grep -v '^#' x.vcf | awk -F'\\t' '$6 >= 30' | sed 's/a/b/' > /dev/null", []),
    ("cd .. && ls", ['..']),
    ("minimap2 -ax sr ~/data/reference.fa ~/data/NA12878_R1.fastq > mapped.sam", []),
    ("OUT=/home/student/x; echo hi > $OUT", ['OUT=/home/student/x']),
    ("bcftools view --output=/home/student/y.vcf x.vcf", ['--output=/home/student/y.vcf']),
    ('echo "see /usr/bin for more"', []),
    ("bash analysis.sh > /tmp/log 2>&1; cat /tmp/log", []),
    ("for f in ../other/*.bam; do samtools index $f; done", ['../other/*.bam']),
    ("echo $(cat ~/secret.txt)", ['~/secret.txt']),
    ("cat > notes.txt <<EOF\nsee ~/x\nEOF", []),
    ('samtools sort -o "$HOME/out.bam" in.sam', ['$HOME/out.bam']),
    ("bcftools query -f '%CHROM\\t%POS\\n' variants.vcf.gz | head", []),
    ("jq '.summary.before_filtering.total_reads / 2' fastp.json", []),
    ("cp results/x.txt ./y.txt && ls ./", []),
]
# (a command, how many folders below the top it starts, does it lead out?)
T, F = True, False
REACH = [
    # the home folder in its spellings
    ('rm -f "$HOME"/victim.txt', 0, T), ('rm -f ${HOME:-x}/victim.txt', 0, T), ('rm -f $HOME"/victim.txt"', 0, T), ('rm -f ~"/victim.txt"', 0, T),
    ('rm -f {~,.}/victim.txt', 0, T), ('rm -f ~-/victim.txt', 0, T), ('rm -f /{home,x}/student/victim.txt', 0, T), ('D=~', 0, T), ('PATH=$PATH:~/bin', 0, T),
    ('rm -f /tmp/../home/student/victim.txt', 0, T), ('rm -f ~/data/../victim.txt', 0, T), ('if [ -f /home/student/x ]; then rm /home/student/x; fi', 0, T),
    ('cat ~/notes.txt', 0, T), ('samtools view -o ~/x.bam mapped.bam', 0, T), ('cp x ~/', 0, T), ('ls ~', 0, T), ('find / -name victim.txt -delete', 0, T),
    ('sed -i s/a/b/ ~/f', 0, T), ('grep -r x ~/notes', 0, T), ('awk -f ~/prog.awk f', 0, T), ('jq . ~/x.json', 0, T), ('sort -o ~/sorted.txt f', 0, T),
    ('tee ~/copy.txt < f', 0, T), ('env X=1 rm -f ~/victim.txt', 0, T), ('xargs rm -f ~/victim.txt < list', 0, T),
    ("printf '%s\\n' victim.txt | xargs -I{} rm -f /home/{}", 0, T), ('rm -f ${PWD%/*}/victim.txt', 0, T), ('rm -f $(dirname $PWD)/victim.txt', 0, T),
    ('cd data && cd /tmp && rm -f $OLDPWD/victim.txt', 0, T), ('X=HOME; rm -f ${!X}/victim.txt', 0, T),
    ('declare -A depth; depth[a]=1; for k in "${!depth[@]}"; do echo "$k=${depth[$k]}"; done', 0, F),
    # cd
    ('cd', 0, T), ('cd ~', 0, T), ('cd && rm -f victim.txt', 0, T), ('cd - > /dev/null && rm -f victim.txt', 0, T), ('cd / && rm -f home/student/victim.txt', 0, T),
    ('pushd .. && rm -f ../victim.txt', 0, T), ('cd .. && ls', 0, T), ('cd work && cd ../.. && ls', 0, T), ('cd ~/data && rm -f ../victim.txt', 0, T),
    ('cd /tmp && rm -f ../home/student/victim.txt', 0, T), ('(cd sub && ls) && cat ../x', 0, T), ('cd ~/data/sub && cat ../../x', 0, T),
    # after a cd to a folder that is only known when the text runs, ".." is not counted (the page notes what the shell really touched)
    ('for d in a b; do cd $d; done; rm ../x', 0, F), ('cd "$D" && rm -rf ../x', 0, F), ('cd "$OUT" && minimap2 -ax sr ../data/reference.fa ../data/NA12878_R1.fastq > mapped.sam', 0, F),
    ('for d in s1 s2; do mkdir -p $d && cd $d && cp ../few.fastq . ; cd ..; done', 0, F), ('rm -f $OUT/../x', 0, F),
    # ".." counted from where the command starts
    ('ls ..', 0, T), ('ls ../x', 0, T), ('cp ../top.txt .', 0, T), ('rm -f ./data/../../../x', 0, T), ('cat ../../x', 1, T),
    ('cp ../top.txt copy.txt', 1, F), ('ls ..', 1, F), ('cat ../../x', 2, F), ('cd data && ls && cd ..', 0, F),
    ('mkdir -p work && cd work && cp ../top.txt copy.txt && cat ../top.txt', 0, F), ('cd data && cd - && ls', 0, F), ('cd sub; cd -; cd -; ls ..', 0, F),
    ('ls data/../data', 0, F), ('cat ./data/../x.json', 0, F),
    # a text for a shell, or for a script
    ('eval "rm -f ~/victim.txt"', 0, T), ("bash -c 'rm -f ~/victim.txt'", 0, T), ('echo "rm -f ~/victim.txt" | bash', 0, T), ('bash <<EOF\nrm -f ~/victim.txt\nEOF', 0, T),
    ("cat > clean.sh <<'EOF'\nrm -f ~/victim.txt\nEOF", 0, T), ("echo 'rm -f ~/victim.txt' > clean.sh", 0, T), ("{ echo 'rm -f ~/victim.txt'; } > clean.sh", 0, T),
    ("cat > run.sh <<'EOF'\n#!/usr/bin/env bash\nset -euo pipefail\nminimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam\nEOF", 0, F),
    ('echo "#!/usr/bin/env bash" > run.sh', 0, F), ('echo "set -euo pipefail" >> run.sh', 0, F), ("printf '%s\\t%s\\n' a b > table.tsv", 0, F),
    # what the page writes in place of the full path of the run's folder: a variable for the folder the script starts in
    ('cd "$RUN_FOLDER"/ && minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq data/NA12878_R2.fastq > mapped.sam', 0, F), ('cd "$RUN_FOLDER" && ls', 0, F),
    ('OUT="$RUN_FOLDER"/ ; echo result > $OUT/made.txt', 0, F), ('cd "$RUN_FOLDER/results" && cat ../data/x', 0, F), ('cd "" && rm -f victim.txt', 0, F),
    ('minimap2 -ax sr "$RUN_FOLDER"/data/reference.fa "$RUN_FOLDER"/data/NA12878_R1.fastq > "$RUN_FOLDER"/results/mapped.sam', 1, F),
    ('cd "$D" && cd "$RUN_FOLDER"/results && cat ../../x', 0, T), ('rm -f "$RUN_FOLDER"/../x', 0, T), ('cat "${RUN_FOLDER}/data/../../x"', 0, T), ('sort -o"$RUN_FOLDER"/sorted.txt f', 0, F),
    # an apostrophe inside "…" is only an apostrophe
    ('echo "Let\'s map the reads" && minimap2 -ax sr data/reference.fa data/NA12878_R1.fastq > mapped.sam', 0, F), ('echo "Here\'s the line for position 11616:"', 0, F),
    ('echo "it isn\'t there" > note.txt', 0, F), ('MSG="can\'t find it"; echo "$MSG"', 0, F), ('echo "a\'b" "c\'d"', 0, F),
    ('echo "it\'s $(rm -f ../victim.txt) John\'s"', 0, T), ("echo 'single' \"it's\" $(cat ~/x)", 0, T),
    # file names with spaces, $'…', braces, trap, and texts that become scripts
    ('cp a.txt "../my copy.txt"', 0, T), ('echo done > "../a b.txt"', 0, T), ('mkdir -p "../new folder" && cp a.txt "../new folder/"', 0, T),
    ("rm -f $'../victim.txt'", 0, T), ('rm -f {..,.}/victim.txt', 0, T), ('rm -f .{.,}/victim.txt', 0, T),
    ('trap "rm -f ../victim.txt" EXIT', 0, T), ("trap 'cd ..; rm -f victim.txt' EXIT", 0, T), ("trap 'rm -f tmp.txt' EXIT", 0, F),
    ("echo 'rm -f ../victim.txt' > clean.sh && bash clean.sh", 0, T), ("printf 'rm -f ../victim.txt\\n' > clean.sh", 0, T),
    ("echo 'cd ..' > clean.sh", 0, T), ("tee clean.sh <<'EOF' > /dev/null\nrm -f ../victim.txt\nEOF", 0, T),
    ("echo 'see ../notes' > hint.txt", 0, T), ("echo 'see ../notes'", 0, F), ("cat > notes.txt <<'EOF'\nrm -f ../victim.txt\nEOF", 0, F),
    # harmless: messages, patterns, programs of other languages, delimiters, addresses, places nobody can change
    ('echo $HOME', 0, F), ('echo "Results are in ~/x"', 0, F), ('echo ~', 0, F), ('echo /home/student', 0, F), ('echo "a/../b"', 0, F),
    ("awk '{ print $1/$2 }' f", 0, F), ("awk '/human_CYP2C19/' mapped.sam", 0, F), ("awk -v OFS=/ '{print $1,$2}' f", 0, F), ("awk -F/ '{print $2}' f", 0, F),
    ("awk -F / '{print $2}' f", 0, F), ("sed '/human_CYP2C9/d' f", 0, F), ("sed -e 's/a/b/' -e '/x/d' f", 0, F), ("sed -n -e '/^@PG/p' f", 0, F), ("sed 's|/|_|g' f", 0, F),
    ("grep -v '/1$' f", 0, F), ("grep -e '/x/' f", 0, F), ("grep -A 2 '/x/' f", 0, F), ("grep -r '/home' .", 0, F), ("xargs grep '/x/' < list", 0, F),
    ("jq '.a / .b' x.json", 0, F), ("jq '..|numbers' x.json", 0, F), ("jq --arg p /x '.a' f.json", 0, F), ('cut -d/ -f1 f', 0, F), ('cut -d / -f 2 f', 0, F),
    ('sort -t / -k 2 f', 0, F), ("tr '/' '_' < f", 0, F), ('seq 1 3 | paste -sd/', 0, F), ('IFS=/ read -ra parts <<< "a/b"', 0, F),
    ('URL=http://example.org/x; echo $URL', 0, F), ('curl -s https://example.org/a/b > x', 0, F), ('x=1/2; echo $x', 0, F), ('x=$(( 10 / 2 )); echo $x', 0, F),
    ("minimap2 -R '@RG\\tID:x\\tSM:y' -ax sr data/reference.fa data/NA12878_R1.fastq", 0, F), ('samtools view mapped.bam human_CYP2C19:11000-12000', 0, F),
    ("bcftools query -f '%CHROM\\t%POS\\t[%GT]\\n' v.vcf.gz", 0, F), ("bcftools view -i 'QUAL>=20' -H v.vcf.gz", 0, F),
    ('ls ~/data', 0, F), ('ls $HOME/data', 0, F), ('cp ~/data/reference.fa .', 0, F), ('cat /home/student/data/README.md', 0, F),
    ('ls data 2>/dev/null', 0, F), ('samtools flagstat mapped.bam > /dev/null 2>&1', 0, F), ('sort -T /tmp f', 0, F), ('date > /tmp/when.txt', 0, F),
    ('head -c 100 /dev/zero | wc -c', 0, F), ('samtools view -o /dev/stdout mapped.bam', 0, F), ('/usr/bin/samtools --version', 0, F), ('/bin/ls', 0, F),
    ('/usr/bin/env bash analysis.sh', 0, F), ('PATH=/usr/bin:$PATH samtools --version', 0, F), ('env LC_ALL=C sort f', 0, F),
    ("find . -name '*.bam'", 0, F), ('./analysis.sh', 0, F), ('bash ./analysis.sh', 0, F), ('test -s x || exit 1', 0, F), ('[[ $x =~ ^/home ]] && echo yes', 0, F),
    ('for i in {1..5}; do echo $i; done', 0, F), ('git log a..b', 0, F), ('f() { cd data; ls; }; f', 0, F), ('time samtools sort -o x.bam y.sam', 0, F),
    ('command -v samtools', 0, F), ('rm -f *.tmp', 0, F), ('mkdir -p out/sub && cp f out/sub/', 0, F), ('ls -d ./*/', 0, F),
    # awk's system( ) runs a command that this reading does not see
    ("awk 'BEGIN { system(\"rm -f x.txt\") }'", 0, T), ("gawk '{ system(\"date\") }' f", 0, T), ("awk '{ print $1 }' f", 0, F), ("awk -v cmd=system '{ print cmd }' f", 0, F),
]
with sync_playwright() as pw:
    srv = server(port=PORT)
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        page.evaluate("MG.app.showWorkbench('assistant')"); page.wait_for_function('!!MG.aiUtil')
        bad = 0
        for text, want, report in CASES:
            got = page.evaluate("(t) => { const P = MG.aiUtil.parseReply(t); return Object.assign({}, P, { file: P.file ? P.file.name : null }); }", text)
            ok = all(got.get(k) == v for k, v in want.items())
            if ok and report is not None:
                ok = page.evaluate("(t) => MG.aiUtil.cleanReport(t)", text) == report
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + repr(text[:70]) + ('' if ok else f'\n     want {want} report {report!r}\n     got  {got}\n     report {page.evaluate("(t) => MG.aiUtil.cleanReport(t)", text)!r}'), flush=True)
        for text, name, body, bash in FILES:
            got = page.evaluate("(t) => { const P = MG.aiUtil.parseReply(t); return { name: P.file && P.file.name, text: P.file && P.file.text, bash: P.bash, more: P.more, final: P.final }; }", text)
            ok = got == {'name': name, 'text': body, 'bash': bash, 'more': 0, 'final': False}
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + 'file: ' + repr(text[:70]) + ('' if ok else f'\n     want {name!r} {body!r} {bash!r}\n     got  {got}'))
        # more than one file in a reply (only the first is written, and the agent is told); a file fenced with tildes
        # that holds blocks of backticks, followed by commands fenced with tildes
        T3 = '~~~'
        MANY = [
            (f"{B3}file:a.sh\necho a\n{B3}\n{B3}file:b.sh\necho b\n{B3}\n{B3}bash\nbash a.sh\n{B3}", 'a.sh', 'echo a\n', 'bash a.sh', 1),
            (f"Three files.\n{B3}file:a.sh\necho a\n{B3}\n{B3}file:b.sh\necho b\n{B3}\n{B3}file:c.txt\nc\n{B3}", 'a.sh', 'echo a\n', None, 2),
            (f"{T3}file:README.md\n# T\n{B3}bash\nls\n{B3}\n{T3}\n{T3}bash\ncat README.md\n{T3}", 'README.md', f"# T\n{B3}bash\nls\n{B3}\n", 'cat README.md', 0),
            (f"{T3}file:a.sh\necho a\n{T3}\n{T3}file:b.sh\necho b\n{T3}\n{T3}bash\nbash a.sh\n{T3}", 'a.sh', 'echo a\n', 'bash a.sh', 1),
            (f"{T3}bash\nls -l\n{T3}", None, None, 'ls -l', 0),
            (f"{B3}file:one.txt\n1\n{B3}\n{B3}bash\ncat one.txt\n{B3}", 'one.txt', '1\n', 'cat one.txt', 0),
        ]
        for text, name, body, bash, extra in MANY:
            got = page.evaluate("(t) => { const P = MG.aiUtil.parseReply(t); return { name: P.file && P.file.name, text: P.file && P.file.text, bash: P.bash, moreFiles: P.moreFiles }; }", text)
            ok = got == {'name': name, 'text': body, 'bash': bash, 'moreFiles': extra}
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + 'files: ' + repr(text[:70]) + ('' if ok else f'\n     want {name!r} {body!r} {bash!r} {extra}\n     got  {got}'))
        for text, want, left in ANCHOR:
            got = page.evaluate("(t) => MG.shellLang.anchor(t, { abs: '/home/student/runs/3-auto', home: '/home/student' }, 'RUN_FOLDER')", text)
            ok = got == {'text': text if want is None else want, 'left': left}
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + 'anchor: ' + repr(text[:90]) + ('' if ok else f'\n     want {want!r} left {left}\n     got  {got}'))
        for text, want in OUTSIDE:
            got = page.evaluate("(t) => MG.aiUtil.outsideWords(t)", text)
            ok = got == want
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + 'outside: ' + repr(text[:70]) + ('' if ok else f'\n     want {want}\n     got  {got}'))
        for text, depth, want in REACH:
            got = page.evaluate("([t, d]) => MG.aiUtil.outsideWords(t, d)", [text, depth])
            ok = bool(got) == want and got != ['?']
            bad += not ok
            print(('ok   ' if ok else 'BAD  ') + ('leads out' if want else 'stays in ') + f' (from {depth}): ' + repr(text[:80]) + ('' if ok else f'\n     got  {got}'))
        print(f'\n{bad} BAD of {len(CASES) + len(FILES) + len(MANY) + len(ANCHOR) + len(OUTSIDE) + len(REACH)}')
        b.close()
    finally:
        srv.terminate()
