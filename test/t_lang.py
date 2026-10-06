"""The terminal's shell language against real bash: the same scripts must print the same
text and end with the same exit status.
   python3 t_lang.py              all scripts
   python3 t_lang.py NAME …       these (a name, or the name of a group: errexit-and-traps)
The scripts are run by the bash of this computer in a new folder of the system's temporary files (which is their
home folder, too, and is removed afterwards), with the GNU tools of this computer, getopt of util-linux,
LC_ALL=C.UTF-8 and umask 022 (the terminal's own settings). They were written for bash 5.2."""
import sys, time, subprocess, tempfile, os, json, shutil
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from h import *
PORT = 8830
os.umask(0o022)   # (new files as in the terminal: 644, folders 755)

CASES = {}
WITH_FILES = set()   # the scripts that start in a folder with the small files of FIX (see below)
GROUPS = {}
def case(name, text, args=''):
    CASES[name] = (text.strip('\n') + '\n', args)
def more(group, text):
    """a text of scripts that start in a folder with the files of FIX: each line is a script of its own
    (group-L001, group-L002 …); the lines from '### name' to '### end' are one script (group-name)"""
    cur, name, n = None, None, 0
    def add(nm, body):
        full = group + '-' + nm
        assert full not in CASES, full
        case(full, body)
        WITH_FILES.add(full)
        GROUPS.setdefault(group, []).append(full)
    for line in text.strip('\n').split('\n'):
        if line.startswith('### '):
            if cur is not None:
                add(name, '\n'.join(cur))
            name, cur = line[4:].strip(), []
            if name == 'end':
                cur, name = None, None
            continue
        if cur is not None:
            cur.append(line)
        elif line.strip():
            n += 1
            add(f'L{n:03d}', line)
    if cur is not None:
        add(name, '\n'.join(cur))

case('quoting', r'''
x="hello world"; y='single $x'; echo "$x" $y "${x}!" '$x'
echo "a  b"   c    d
z=${x/world/there}; echo "$z"; echo ${#x}; echo "${x:0:5}|${x:6}|${x: -5}"
echo "${undefined:-default}" "${x:+set}" "${undefined:+set}|"
f=sample_R1.fastq.gz; echo "${f%.gz}" "${f%%.*}" "${f#*_}" "${f##*.}" "${f/R1/R2}"
echo "${f^^}" "${x,,}" "${f//a/A}"
echo 'it'"'"'s' "tab\there" 'back\slash' $'ansi\tq'
e=""; echo "[$e]" [$e] "${e:-fallback}" "${e-notused}|"
echo a{1,2}b {1..4} {a..c} "{no,expand}" pre{x,y{1,2}}post
''')
case('substitution', r'''
n=$(printf 'a\nb\nc\n' | wc -l); echo "lines: $n"
echo "sum: $((n * 2 + 1))" "$(( (n + 1) / 2 ))" $((2**10)) $((7 % 3)) $((n > 2 ? 10 : 20))
i=0; i=$((i + 1)); ((i++)); ((i += 5)); echo $i
d=$(dirname /a/b/c.txt); b=$(basename /a/b/c.txt .txt); echo "$d $b"
echo "nested: $(echo "inner $(echo deep)")"
echo `echo backtick`
words=$(echo one two three); for w in $words; do echo "w=$w"; done
echo "$(echo a; echo b)" | wc -l
echo "exit of subst: $(false; echo $?)"
v=$(false) || echo "assign failed: $?"
echo $(( $(seq 5 | wc -l) + 1 ))
''')
case('if-test', r'''
touch f.txt; mkdir d; echo data > g.txt
if [ -f f.txt ]; then echo file; fi
if [ -d d ] && [ ! -e nothing ]; then echo dir; else echo no; fi
if [ -s f.txt ]; then echo nonempty; else echo empty; fi
if [ -s g.txt ]; then echo nonempty; else echo empty; fi
x=5
if [ "$x" -gt 3 ]; then echo gt; elif [ "$x" -eq 3 ]; then echo eq; else echo lt; fi
if [[ $x -lt 10 && -f f.txt ]]; then echo both; fi
s=abc.fastq
if [[ $s == *.fastq ]]; then echo fastq; fi
if [[ $s == "*.fastq" ]]; then echo literal; else echo not-literal; fi
if [[ $s =~ ^([a-z]+)\.fastq$ ]]; then echo "match ${BASH_REMATCH[1]}"; fi
[ -z "" ] && echo empty-string
[ "a" != "b" ] && echo differ
test 3 -le 3 && echo le
if ! grep -q zzz g.txt; then echo "not found"; fi
[ -f g.txt -a -d d ] && echo and
[ -f nothing -o -d d ] && echo or
[[ -n $s || -z $s ]] && echo always
[[ ! -d nothing ]] && echo notdir
if [ -f nothing ]; then echo yes; fi; echo "rc=$?"
[ 1 -eq 2 ]; echo "rc=$?"
''')
case('loops', r'''
for i in 1 2 3; do echo "i=$i"; done
touch a.txt b.txt
for f in *.txt; do echo "file $f"; done
for i in {1..3}; do printf '%d ' "$i"; done; echo
for ((i = 0; i < 3; i++)); do echo "c$i"; done
n=0; while [ $n -lt 3 ]; do n=$((n + 1)); done; echo $n
until [ $n -le 0 ]; do n=$((n - 1)); done; echo $n
for x in a b c; do if [ $x = b ]; then continue; fi; echo $x; done
for x in a b c; do [ $x = b ] && break; echo $x; done
case "sample.bam" in *.sam) echo sam ;; *.bam|*.cram) echo bam ;; *) echo other ;; esac
case "x" in
  a) echo a ;;
  x)
    echo isx
    ;;
esac
printf 'l1 a\nl2 b\n' > in.txt
while read -r name val; do echo "$val:$name"; done < in.txt
cat in.txt | while read line; do echo "[$line]"; done
for i in 1 2; do for j in a b; do echo "$i$j"; done; done
for i in 1 2 3; do for j in a b; do [ $j = b ] && continue 2; echo "$i$j"; done; done
while IFS=, read -r a b; do echo "$b-$a"; done <<END
1,one
2,two
END
i=0; while true; do i=$((i+1)); [ $i -ge 4 ] && break; done; echo "i=$i"
''')
case('functions', r'''
greet() { local who="$1"; echo "hello $who ($#)"; return 3; }
greet world extra; echo "rc=$?"
function add { echo $(($1 + $2)); }
r=$(add 2 3); echo $r
count() { local n=0; for a in "$@"; do n=$((n+1)); done; echo $n; }
count "a b" c "d e f"
set -- x y z; echo "$1 $# $@"; shift; echo "$1 $#"
who=outer; f() { local who=inner; echo $who; }; f; echo $who
g() { echo "to stderr" >&2; echo "to stdout"; }
g 2>/dev/null
out=$(g 2>&1 | wc -l); echo $out
log() { echo "[log] $*"; }
log one two
fact() { if [ $1 -le 1 ]; then echo 1; else echo $(( $1 * $(fact $(( $1 - 1 ))) )); fi; }
fact 5
h() { return 0; }; h && echo ok
''')
case('errexit', r'''
set -euo pipefail
echo start
false || echo "recovered"
if false; then echo no; fi
! false
x=$(echo ok)
echo "x=$x"
false
echo "not reached"
''')
case('pipefail', r'''
set -eo pipefail
echo a | grep -q b || echo "no match"
printf 'x\n' | grep y | wc -l
echo "not reached"
''')
case('nounset', r'''
set -u
echo "before"
echo "$UNDEFINED_VAR"
echo "after"
''')
case('errexit-and', r'''
set -e
false && echo no
echo "still here"
[ -f nothing ] && echo no2
echo "and here"
f() { false; echo "in function, not reached"; }
f
echo "not reached"
''')
case('redirect', r'''
echo one > o.txt; echo two >> o.txt; cat o.txt
ls nothing 2> err.txt; echo "rc=$?"; wc -l < err.txt
{ echo a; echo b; } > g.txt; cat g.txt
cat <<END > h.txt
value: $((1+1)) [$HOME_NOT]
literal \$x and `echo tick`
END
cat h.txt
cat <<'END'
no $expansion here
END
tr a-z A-Z <<< "herestring"
echo err >&2
ls nothing > both.txt 2>&1; grep -c nothing both.txt
for i in 1 2; do echo $i; done > loop.txt; cat loop.txt
echo x > /dev/null; echo "after null"
(echo sub1; echo sub2) | tr a-z A-Z
if true; then echo in-if; fi | sed 's/in/IN/'
cat < o.txt | wc -l
echo "to file" > sub.txt 2>&1; cat sub.txt
echo three >> o.txt; wc -l < o.txt
: > empty.txt; wc -c < empty.txt
cat <<-END
	tabbed
	END
''')
case('printf', r'''
printf '%s\n' a b c
printf '%5d|%-5d|%05d\n' 42 42 42
printf '%.2f %8.3f %e\n' 3.14159 2.71828 12345.678
printf '%-10s|%10s|\n' left right
printf '%s\t%s\n' x y
printf '%d%%\n' 50
printf '%x %X %o\n' 255 255 8
printf 'no newline'; echo
printf '%s=%s\n' k1 v1 k2 v2
printf '%3s|%.2s|\n' a abcdef
printf '%+d % d\n' 5 5
printf '%g %g %g\n' 0.0001 123456789 2.50
printf -v var '%03d' 7; echo "$var"
echo -e "a\tb\nc"; echo -n "no-nl"; echo
''')
case('arrays', r'''
arr=(a "b c" d)
echo "${#arr[@]} ${arr[0]} ${arr[1]} ${arr[-1]}"
for x in "${arr[@]}"; do echo "<$x>"; done
arr+=(e); echo "${arr[@]}"
touch p.txt q.txt; files=(*.txt); echo "${#files[@]}"
echo "${arr[@]:1:2}"
arr[1]=B; echo "${arr[1]} ${arr[*]}"
empty=(); echo "n=${#empty[@]}"; for x in "${empty[@]}"; do echo never; done
''')
case('find-xargs', r'''
mkdir -p d/sub; touch d/a.txt d/b.log d/sub/c.txt
find d -name '*.txt' | sort
find d -type f -name '*.txt' -exec echo found {} \; | sort
find d -maxdepth 1 -type f | sort
printf 'a\nb\nc\n' | xargs echo
printf 'a\nb\n' | xargs -n1 echo item
printf 'a\nb\n' | xargs -I{} echo "<{}>"
find d -type d | sort
find d -name '*.log' -delete; ls d
find d \( -name 'a*' -o -name 'c*' \) -type f | sort
find d -type f ! -name 'a*' | sort
''')
case('misc', r'''
seq 3 | tac
echo "a,b,c" | cut -d, -f2
echo "hello" | rev
printf 'b\na\nb\n' | sort | uniq -c | sort -rn | head -1 | awk '{print $2, $1}'
command -v echo > /dev/null && echo "have echo"
command -v nonexistent_cmd > /dev/null || echo "no such"
true && echo t; false || echo f
x=5; [ $x -eq 5 ] && { echo yes; echo really; }
mkdir -p dd; (cd dd && pwd | sed 's#.*/##'); pwd | sed 's#.*/##' | wc -l
echo "a b c" | { read x y z; echo "$z $y $x"; }
A=1 B=2; echo "$A$B"
eval "echo evaluated $A"
expr 2 + 3; expr 10 / 3
let "q = 4 * 5"; echo $q
basename /x/y/z.fastq.gz .fastq.gz; dirname x/y/z
nonexistent_program_xyz; echo "rc=$?"
ls /nonexistent_dir_xyz 2>/dev/null; echo "rc=$?"
echo "${PWD##*/}" | wc -l
echo done
''')
case('trap', r'''
trap 'echo cleanup' EXIT
echo working
exit 4
''')
case('args', r'''
echo "$0" | sed 's#.*/##'; echo "$1|$2|$#"; echo "$@"; for a in "$@"; do echo "[$a]"; done
echo "${1:-none} ${3:-none}"
''', args='one "two words"')
case('analysis-script', r'''
#!/usr/bin/env bash
# A typical script as an AI model writes it
set -euo pipefail

SAMPLE="NA12878"
THREADS=1
OUTDIR="results"
REF="ref.fa"

log() { echo "[$(echo step)] $*"; }

mkdir -p "$OUTDIR"
printf '>chr1\nACGT\n' > "$REF"
printf '@r1\nACGT\n+\nIIII\n@r2\nTTTT\n+\nIIII\n' > "${SAMPLE}_R1.fastq"

if [ ! -f "$REF" ]; then
    echo "ERROR: reference not found: $REF" >&2
    exit 1
fi

for f in "${SAMPLE}_R1.fastq"; do
    if [[ ! -s "$f" ]]; then
        echo "ERROR: missing input $f" >&2
        exit 1
    fi
done

log "Counting reads"
READS=$(( $(wc -l < "${SAMPLE}_R1.fastq") / 4 ))
log "Reads: ${READS}"

grep -c '^>' "$REF" > "$OUTDIR/contigs.txt" || true
NCONTIG=$(cat "$OUTDIR/contigs.txt")

{
    echo "Sample: $SAMPLE"
    echo "Reads: $READS"
    echo "Contigs: $NCONTIG"
    echo "Threads: ${THREADS}"
} > "$OUTDIR/summary.txt"

cat "$OUTDIR/summary.txt"
if [ "$READS" -gt 1 ]; then echo "PASS"; else echo "FAIL"; fi
log "Done"
''')
case('syntax-error', r'''
echo before
if true; then
echo "unterminated
''')
case('exit-in-function', r'''
die() { echo "fatal: $1"; exit 3; }
echo a
[ -f nothing ] || die "no file"
echo "not reached"
''')
case('subshell-scope', r'''
x=1; (x=2; echo "in $x"); echo "out $x"
cd_test() { mkdir -p zz; cd zz; }
(cd_test; pwd | sed 's#.*/##'); pwd | sed 's#.*/##' | grep -c zz
y=$(x=9; echo $x); echo "$x $y"
echo hi | read v; echo "v=[${v:-}]"
''')

case('idioms', r'''
set -euo pipefail
usage() { echo "usage: $0 FILE" | sed 's#[^ ]*/##'; }
[ $# -lt 1 ] || { usage; exit 2; }
: "${OUT:=results}"; echo "$OUT"
: "${THREADS:=4}" "${MODE:=fast}"; echo "$THREADS $MODE"
mkdir -p out/{bam,vcf,qc}; ls out
printf 'chr1\t10\nchr2\t20\n' > t.tsv
total=$(awk '{s+=$2} END {print s}' t.tsv); echo "total=$total"
if command -v sort >/dev/null 2>&1; then echo "sort present"; fi
if ! command -v gatk >/dev/null 2>&1; then echo "gatk missing"; fi
for f in out/*; do b=$(basename "$f"); echo "dir:${b}"; done
count=0
while IFS=$'\t' read -r chrom pos; do count=$((count + pos)); echo "$chrom=$pos"; done < t.tsv
echo "count=$count"
(( count > 20 )) && echo "big"
if (( count == 30 )); then echo thirty; fi
x=""; [ -z "${x:-}" ] && echo "x empty"
[[ "$OUT" == "results" || "$OUT" == "out" ]] && echo "known out"
name="a.b.c"; echo "${name%.*} ${name%%.*} ${name##*.}"
echo "lines: $(wc -l < t.tsv)"
content=$(< t.tsv); echo "${#content}"
>&2 echo "this goes to stderr"
echo "quiet" &>/dev/null
ls nothing_here &>/dev/null || echo "ls failed quietly"
echo "a
b" | wc -l
long_command=$(echo one \
  two \
  three); echo "$long_command"
echo first &&
  echo second
echo piped |
  tr a-z A-Z
readonly CONST=5; echo $CONST
declare -i num=7; echo $num
local_test() { local a=1 b=2; local -r c=3; echo "$a$b$c"; }; local_test
export GREETING="hi there"; echo "$GREETING"
status=0; false || status=$?; echo "status=$status"
echo "done" # a comment at the end
''')
case('strings', r'''
s="Hello, World"
echo "${s:7}" "${s:0:5}" "${#s}"
echo "${s/o/0}" "${s//o/0}" "${s/#Hello/Bye}" "${s/%World/All}"
a=apple; b=banana
if [[ "$a" < "$b" ]]; then echo "apple first"; fi
if [ "$a" \< "$b" ]; then echo "apple first again"; fi
[[ "$s" == *World* ]] && echo contains
[[ "$s" != *xyz* ]] && echo "no xyz"
case "$s" in Hello*) echo starts ;; esac
case "42" in [0-9]*) echo number ;; *) echo text ;; esac
u=$(echo "$s" | tr '[:lower:]' '[:upper:]'); echo "$u"
echo "${u,,}"
IFS=, read -r p q <<< "left,right"; echo "$q $p"
csv="a,b,c"; IFS=',' read -ra parts <<< "$csv" || true; echo "${csv//,/ }"
printf '%s\n' "multi word" single | while read -r l; do echo "<$l>"; done
v='single "double" inside'; echo "$v"
w="double 'single' inside"; echo "$w"
echo "dollar \$HOME and backslash \\ and quote \""
echo 'a'"b"'c' "x"y'z'
echo "${s// /_}"
n=007; echo $((10#$n + 1)) 2>/dev/null || echo "base-n not supported"
''')
case('status', r'''
true; echo $?
false; echo $?
(exit 7); echo $?
sh -c 'exit 9' ; echo $?
bash -c 'echo inner; exit 5'; echo $?
ls nothing 2>/dev/null; echo $?
grep -q x /dev/null; echo $?
f() { return 42; }; f; echo $?
false | true; echo $?
true | false; echo $?
! true; echo $?
if false; then :; fi; echo $?
[ -e nothing ] || echo "missing: $?"
x=$(exit 3); echo $?
exit 300
''')
case('heredoc-file', r'''
cat > config.txt <<CFG
name=test
home_len=${#HOME_UNSET_VAR}
sum=$((2 + 3))
CFG
cat config.txt
cat > script2.sh <<'INNER'
#!/bin/bash
echo "inner script got $1"
for i in 1 2; do echo "n$i"; done
INNER
bash script2.sh arg
chmod +x script2.sh; ./script2.sh direct
cat <<A; cat <<B
first
A
second
B
grep -c n <<DOC
one
two
nine
DOC
''')

case('assoc-arrays', r'''
declare -A m=([minimap2]=60 [bowtie2]=50)
m[fastp]="6170 reads"
for k in "${!m[@]}"; do echo "$k -> ${m[$k]}"; done | sort
echo "${#m[@]}"
unset "m[fastp]"; echo "${#m[@]} ${m[bowtie2]}"
[[ -n "${m[minimap2]}" ]] && echo has
[[ -z "${m[nothing]}" ]] && echo "no such key"
declare -A counts
for w in a b a c a; do counts[$w]=$(( ${counts[$w]:-0} + 1 )); done
for k in a b c; do echo "$k=${counts[$k]}"; done
key="two words"; m[$key]=x; echo "${m[two words]}|${m["$key"]}"
m+=([extra]=1); echo "${#m[@]}"
for v in "${m[@]}"; do echo "v=$v"; done | sort
f() { local arr=(x y z) n=3; local -a list=("a b" c); echo "${#arr[@]} ${arr[1]} $n ${#list[@]} ${list[0]}"; }
f; echo "[${arr[0]}]"
declare -a idx=(one two three); echo "${!idx[@]}"; echo "${idx[@]:1}"
readonly RO=(p q); echo "${RO[1]}"
x=y; y=5; echo "${!x}"
set -- first second; n=2; echo "${!n}"
unset "idx[1]"; echo "${#idx[@]} ${!idx[@]} ${idx[@]}"
''')
case('mapfile-read', r'''
printf 'l1\nl2 has words\nl3\n' > in.txt
mapfile -t lines < in.txt; echo "${#lines[@]}|${lines[1]}|${lines[2]}"
readarray raw < in.txt; printf '%s' "${raw[0]}"; echo "${#raw[1]}"
mapfile -t -n 2 firsttwo < in.txt; echo "${#firsttwo[@]}"
mapfile -t -s 1 rest < in.txt; echo "${rest[0]}"
printf 'no newline at the end' > open.txt; mapfile -t o < open.txt; echo "${#o[@]}|${o[0]}"
IFS=: read -ra parts <<< "GT:PL:AD"; echo "${#parts[@]} ${parts[2]}"
read -r -a w <<< "a b  c"; echo "${w[@]}|${#w[@]}"
IFS=, read -r a b c <<< "1,2,3,4"; echo "$a $b $c"
bash -c 'echo "$0 $1 $#"' name arg1
bash -c 'echo "$1"' _ "two words"
printf 'echo "in script: $1"\n' > t.sh
bash -n t.sh && echo "syntax ok"
printf 'if true; then\n  echo x\n' > bad.sh
bash -n bad.sh 2>/dev/null; echo "rc=$?"
bash -e -c 'false; echo no'; echo "rc=$?"
bash -euo pipefail -c 'true | false | true; echo no'; echo "rc=$?"
bash -c 'echo "${1:-none}"'
''')

case('preamble', r'''
#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
shopt -s nullglob
export LC_ALL=C
umask 022
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ "$SCRIPT_DIR" = "$PWD" ] && echo "script dir ok"
cd "$(dirname "$0")"
readonly THREADS="${THREADS:-4}"
: "${OUT:=results}"
mkdir -p "$OUT"
echo "threads=$THREADS out=$OUT"
type echo > /dev/null; echo "type rc=$?"
files=(*.nomatch)
echo "nullglob: ${#files[@]}"
shopt -u nullglob
: > "$OUT/empty.txt"; [ -e "$OUT/empty.txt" ] && [ ! -s "$OUT/empty.txt" ] && echo "made empty"
echo one > "$OUT/log.txt"; echo two >> "$OUT/log.txt"; echo err 2>> "$OUT/log.txt" >&2 || true
wc -l < "$OUT/log.txt"
n=0
for x in a b c; do n=$((n+1)); done
printf 'n=%d\n' "$n"
if [[ "${1:-}" == "--help" ]]; then echo usage; fi
echo "args: $#"
exit 0
''')
case('trap-err', r'''
set -eu
trap 'echo "ERROR at line $LINENO (status $?)" >&2; echo "trap ran"' ERR
trap 'echo "cleanup"' EXIT
echo start
false
echo "not reached"
''')
case('trap-err-pipe', r'''
set -euo pipefail
trap 'echo "failed: status $?"' ERR
step() { echo "step $1"; return "$2"; }
step one 0
step two 3 || echo "handled"
if ! step three 1; then echo "in if"; fi
true | false | true
echo "not reached"
''')
case('time-exec', r'''
exec 2>&1
echo "to stdout"
echo "to stderr" >&2
{ echo a; echo b; } | while read -r l; do echo "got $l"; done
x=$( { echo out; echo err >&2; } 2>&1 ); echo "$x" | wc -l
cat <<'A' <<'B' | tr a-z A-Z
first
A
second
B
echo "a b c" | { read -r first rest; echo "$first|$rest"; }
echo "x" |& cat
(echo sub; exit 2) || echo "sub rc=$?"
false || { echo "group after or"; }
! true || echo "negated"
[ 1 -eq 1 ] && [ 2 -gt 1 ] && echo chain
case "sample_R1.fastq.gz" in *_R1*) echo read1 ;; *_R2*) echo read2 ;; esac
case "x" in a|b) echo ab ;; [x-z]) echo xyz ;;& x) echo also ;; *) echo other ;; esac
until [ "${i:=0}" -ge 2 ]; do i=$((i+1)); done; echo "i=$i"
select_tool() { command -v "$1" > /dev/null 2>&1 && echo "$1" || echo "none"; }; select_tool cat; select_tool no_such_tool_x
''')
case('cp-mv-cd', r'''
mkdir d1 e; echo a > f1; echo b > f2; echo c > d1/a
mv f1 new/ 2>/dev/null; echo "mv a file to a missing folder/: $?"
cp f1 new/ 2>/dev/null; echo "cp a file to a missing folder/: $?"
cp f1 f2/ 2>/dev/null; echo "cp onto file/: $?"
mv f1 f2/ 2>/dev/null; echo "mv onto file/: $?"
cat f1 f2; ls | sort | tr '\n' ' '; echo
cp -r d1/. e; echo "cp -r d1/. e: $?"; find e | sort | tr '\n' ' '; echo
mkdir e2; cp -r d1/. e2/; find e2 | sort | tr '\n' ' '; echo
cp -r d1 e; find e | sort | tr '\n' ' '; echo
cp -r d1/. new1; find new1 | sort | tr '\n' ' '; echo
mv d1 moved/; echo "mv a folder to a new name/: $?"; find moved | sort | tr '\n' ' '; echo
mv f1 missing f2 e 2>/dev/null; echo "mv with a missing source: $?"; find e | sort | tr '\n' ' '; echo
echo x > g1; mv g1 g1 2>/dev/null; echo "mv onto itself: $?"; mv g1 . 2>/dev/null; echo "mv to its own folder: $?"; cat g1
cp g1 g1 2>/dev/null; echo "cp onto itself: $?"
mkdir t; echo y > g2; cp -t t g1 g2; echo "cp -t: $?"; mv -t t g1; echo "mv -t: $?"; find t | sort | tr '\n' ' '; ls g1 2>/dev/null; echo
cp -t nowhere g2 2>/dev/null; echo "cp -t to a missing folder: $?"
mkdir -p a/b; cd a; cd b; cd - > /dev/null; pwd | sed 's|.*/||'; cd - > where.txt; ls where.txt 2>/dev/null | wc -l; sed 's|.*/||' ../where.txt; pwd | sed 's|.*/||'
cd ""; echo "cd \"\": $?"; pwd | sed 's|.*/||'
cd ../..; echo "$OLDPWD" | sed 's|.*/||'
ls f2 e t a; ls -d t e2 a; ls -r where.txt f2
''')
case('block-redirect', r'''
TOP=$PWD; mkdir -p d1 d2
{ cd d1; pwd | sed 's|.*/||'; } > out1.txt; cd "$TOP"; ls out1.txt d1/out1.txt 2>/dev/null | tr '\n' ' '; echo; cat out1.txt
for x in 1 2; do cd d2; echo $x; cd ..; done > out2.txt; ls out2.txt d2/out2.txt 2>/dev/null | tr '\n' ' '; echo; cat out2.txt
f() { cd d1; echo in-f; }; f > out3.txt; cd "$TOP"; ls out3.txt d1/out3.txt 2>/dev/null | tr '\n' ' '; echo
if true; then cd d1; echo yes; fi > out4.txt; cd "$TOP"; ls out4.txt d1/out4.txt 2>/dev/null | tr '\n' ' '; echo
i=0; while [ $i -lt 1 ]; do cd d2; i=1; echo w; done > out5.txt; cd "$TOP"; ls out5.txt d2/out5.txt 2>/dev/null | tr '\n' ' '; echo
{ cd d1; echo more; } >> out1.txt; cd "$TOP"; cat out1.txt
{ cd d1; echo err >&2; } 2> err1.txt; cd "$TOP"; cat err1.txt
( cd d2; echo sub ) > out6.txt; ls out6.txt d2/out6.txt 2>/dev/null | tr '\n' ' '; echo
cd d1 d2 2>/dev/null; echo "cd with two folders: $?"; [ "$PWD" = "$TOP" ] && echo "still at the top"
cd -P d1; echo "cd -P: $?"; pwd | sed 's|.*/||'
echo x > a.txt; mkdir -p a.txt/sub 2>/dev/null; echo "mkdir -p below a file: $?"; mkdir a.txt/y 2>/dev/null; echo "mkdir below a file: $?"; cat a.txt
''')
case('slash-args', r'''
printf '>human_CYP2C19\nACGT\n>human_CYP2C9\nTTGA\n' > ref.fa; printf 'see /tmp and /home\nplain\n' > note.txt
echo a/b/c | tr / _
echo a/b/c | cut -d / -f 2
echo a/b/c | cut -d/ -f 2
echo a/b/c | cut --delimiter=/ -f 3
awk '/human_CYP2C19/' ref.fa | head -1
awk '/human_CYP2C19/ { print NR }' ref.fa
grep -c / note.txt
grep -c '/' note.txt
grep -o /tmp note.txt
grep -c /home note.txt
grep -c -e /tmp note.txt
grep -ce /home note.txt
echo a/b | awk -F / '{ print $2 }'
echo a/b | awk -F/ '{ print $2 }'
sed -n '/human_CYP2C19/p' ref.fa
sed -ne '/CYP2C9/p' ref.fa
sed '/^>/d' ref.fa | head -c 4; echo
seq 3 | paste -sd /
seq -s / 3
echo 'a/b' | sort -t / -k 2
printf 'a\tb\n' | tr '\t' /
echo x | sed 's/x/\/tmp/'
echo /x | awk '$0 == "/x"'
echo "in tmp" > /tmp/mg-lang-test-a.txt; cat /tmp/mg-lang-test-a.txt; grep -c tmp /tmp/mg-lang-test-a.txt; head -1 /tmp/mg-lang-test-a.txt | wc -c; sort /tmp/mg-lang-test-a.txt
cut -c1-2 /tmp/mg-lang-test-a.txt; sed -n 1p /tmp/mg-lang-test-a.txt; awk '{ print NF }' /tmp/mg-lang-test-a.txt; wc -l < /tmp/mg-lang-test-a.txt
sort -o /tmp/mg-lang-test-b.txt /tmp/mg-lang-test-a.txt; cat /tmp/mg-lang-test-b.txt
printf 'c\nb\n' > /tmp/mg-lang-test-c.txt; sort -o/tmp/mg-lang-test-d.txt /tmp/mg-lang-test-c.txt; cat /tmp/mg-lang-test-d.txt
echo tmp > /tmp/mg-lang-test-p.txt; grep -c -f/tmp/mg-lang-test-p.txt /tmp/mg-lang-test-a.txt; grep -f /tmp/mg-lang-test-p.txt /tmp/mg-lang-test-a.txt
echo 's/in/IN/' > /tmp/mg-lang-test-s.sed; sed -f/tmp/mg-lang-test-s.sed /tmp/mg-lang-test-a.txt; sed -i 's/tmp/TMP/' /tmp/mg-lang-test-a.txt; cat /tmp/mg-lang-test-a.txt
rm -f /tmp/mg-lang-test-a.txt /tmp/mg-lang-test-b.txt /tmp/mg-lang-test-c.txt /tmp/mg-lang-test-d.txt /tmp/mg-lang-test-p.txt /tmp/mg-lang-test-s.sed
''')
case('env-command', r'''
printf 'b\na\nC\n' > l.txt
env LC_ALL=C sort l.txt
env sort -r l.txt | head -1
/usr/bin/env echo "by its full name"
env FOO=bar bash -c 'echo "FOO is $FOO"'
env -u HOME echo "an option with a value"
env | grep -c '^HOME='
FOO=outer; env FOO=inner true; echo "$FOO"
echo x | env cat
env -- echo "after the two dashes"
mkdir d1; cd -x d1 2>/dev/null; echo "cd -x: $?"; cd -- d1; echo "cd --: $?"; pwd | sed 's|.*/||'
''')

# a program that stands in a block, a function, a loop or a script reads the input of that block …
case('stdin-inherit', r'''
printf 'l1\nl2\nl3\n' > in.txt; printf 'h\nb\na\n' > t.txt; printf '1\n2\n3\n4\n' > n.txt
{ cat; } < in.txt
( wc -l ) < in.txt
f() { cat; }; f < in.txt
g() { wc -l; }; g < in.txt; cat in.txt | g
cat in.txt | { cat; }
s() { sort -r | head -n 1; }; cat in.txt | s; s < in.txt
cat in.txt | { read a; echo "first: $a"; cat; }
{ read a; echo "first: $a"; cat; } < in.txt
{ head -n 1; cat; } < in.txt
{ head -n 1; head -n 1; head -n 1; } < n.txt
cat n.txt | { head -n 1; head -n 1; }
{ head -n 2 > /dev/null; cat; } < n.txt
{ read -r h; echo "$h"; sort; } < t.txt
cat t.txt | (read -r h; echo "$h"; sort)
if true; then wc -l; fi < in.txt
for i in 1; do tr a-z A-Z; done < in.txt
cat in.txt | for i in 1; do wc -c; done
t() { tee copy.txt | wc -l; }; t < in.txt; cat copy.txt
h() { awk '{ n++ } END { print n }'; }; h < in.txt
inner() { wc -l; }; outer() { inner; }; cat in.txt | outer
{ sort -r; } < in.txt > out.txt; cat out.txt
# … and a program that does not read leaves the input to the commands after it
while read x; do echo "<$x>"; wc -c < in.txt; grep -c l in.txt; done < in.txt
while read x; do echo "<$x>"; cat > /dev/null; done < in.txt
while read -r x; do printf '%s:' "$x"; wc -l t.txt; done < in.txt
while read a; do read b; echo "$a+$b"; done < n.txt
{ read -r x; { read -r y; cat; }; echo "$x$y"; } < in.txt
# scripts, bash -c, eval, xargs
echo 'wc -l' > w.sh; bash w.sh < in.txt; cat in.txt | bash w.sh
echo 'read a; echo "script read $a"; cat' > r.sh; bash r.sh < in.txt; cat in.txt | bash r.sh
bash -c 'cat' < in.txt; cat in.txt | bash -c 'wc -l'
eval 'wc -l' < in.txt
{ xargs echo; } < in.txt
cat in.txt | { x=$(cat); echo "[$x]"; }
printf 'echo from-stdin\n' | bash
while read -r s; do bash w.sh; echo "after $s"; done < in.txt
# other readers, and bytes that are more than one byte each
{ grep -c l; } < in.txt; { sed -n 2p; } < in.txt; { cut -c 2; } < in.txt; { md5sum; } < in.txt
{ tac; } < in.txt; cat in.txt | { rev; }; { sha256sum; } < in.txt | cut -c 1-16
printf 'é1\nü2\nz3\n' > u.txt; { head -n 1; cat; } < u.txt; { read -r a; cat; } < u.txt
{ mapfile -t A; echo ${#A[@]}; cat | wc -l; } < in.txt
''')
# … and bash opens the files after > before the command runs
case('redirect-first', r'''
ls > l.txt; cat l.txt
{ ls; } > l2.txt; cat l2.txt
printf 'b\na\n' > f.txt; sort f.txt > f.txt; wc -c < f.txt
printf 'b\na\n' > g.txt; sort < g.txt > g.txt; wc -c < g.txt
printf 'x\ny\n' > k.txt; head -n 1 k.txt > k.txt; wc -c < k.txt
echo keep > m.txt; echo m.txt > m.txt; cat m.txt
echo a > p.txt > q.txt; wc -c < p.txt; cat q.txt
nosuchprogram > made.txt 2> /dev/null; wc -c < made.txt
printf 'x\n' > h.txt; cat h.txt >> h2.txt; cat h2.txt
printf 'b\na\n' > s.txt; sort -o s.txt s.txt; cat s.txt
x=$(cat s.txt); echo "$x" | sort -r > s.txt; cat s.txt
ls | wc -l > count.txt; ls | wc -l
''')

# what scripts with options, loops over lists and logging functions use
case('builtins-more', r'''
usage() { echo "usage: $0 [-i FILE] [-o FILE] [-v]" >&2; }
parse() {
  local OPTIND opt in=none out=none verbose=0
  while getopts "i:o:vh" opt; do
    case $opt in i) in=$OPTARG;; o) out=$OPTARG;; v) verbose=$((verbose + 1));; h) echo help; return 0;; *) echo "bad option"; return 2;; esac
  done
  shift $((OPTIND - 1))
  echo "$in $out $verbose rest=[$*] n=$#"
}
parse -i a.fq -v -o b.bam x y; parse x y; parse -vv -ia.fq; parse -o 2> /dev/null; echo "status $?"; parse -z 2> /dev/null; echo "status $?"; parse -v -- -i x; parse -h
quiet() { local OPTIND o; while getopts ":a:b" o; do case $o in a) echo "a=$OPTARG";; b) echo b;; :) echo "missing value for -$OPTARG";; \?) echo "unknown -$OPTARG";; esac; done; }
quiet -b -a 1 -x -a
while getopts "n:" o -n 5 rest; do echo "$o $OPTARG $OPTIND"; done; OPTIND=1
read -r -n 3 three <<< abcdef; echo "$three"; read -r -N 2 two <<< abcdef; echo "$two"; read -rn1 one <<< xyz; echo "$one"
printf 'a,b;c\n' | { read -r -d ';' first; echo "$first"; }
printf 'one\0two\0' | while IFS= read -r -d '' item; do echo "<$item>"; done
printf 'x y\n' | { read -r -a parts; echo "${#parts[@]} ${parts[1]}"; }
a=(1 2 3); IFS=,; echo "${a[*]}"; echo "${a[@]}"; x="${a[*]}"; echo "$x"; set -- p q r; echo "$*"; unset IFS; echo "${a[*]}" "$*"; set --
IFS=:; path='/usr/bin:/bin::/opt'; for d in $path; do echo "[$d]"; done; unset IFS
IFS=$'\n'; for line in $(printf 'a b\nc d\n'); do echo "[$line]"; done; unset IFS
IFS=,; csv='a, b,c ,'; set -- $csv; echo "$#: [$1] [$2] [$3]"; unset IFS; set --
IFS=; v='a  b'; set -- $v; echo "$#: [$1]"; unset IFS; set --
IFS=' ,'; set -- $(echo 'a, b ,c'); echo "$# $1$2$3"; unset IFS; set --
printf '%d %d %d %d\n' 010 0x1f -5 "'A"; printf '%x %o %X\n' 255 8 0xff; printf '%q|%q|%q\n' 'a b' plain ''; printf '%5d|%-5d|%05d\n' 42 42 42
v=1; [[ -v v ]] && echo set; [[ -v nope ]] || echo unset; [ -v v ] && echo set2; declare -A m; m[k]=1; [[ -v m[k] ]] && echo has; [[ -v m[z] ]] || echo hasnot
false | true | (exit 3); echo "${PIPESTATUS[@]}"; true | false; echo "${PIPESTATUS[0]}${PIPESTATUS[1]} $?"; ls > /dev/null; echo "${#PIPESTATUS[@]}"
log() { echo "[${FUNCNAME[0]}<${FUNCNAME[1]}] $*"; }; step() { log "in step"; }; step; log top
args() { echo "$# [${@:2}] [${@:2:1}] [${@: -1}] [${*:1:2}] [$1]"; }; args a b c d
timeout 5 echo ran; timeout 5s false; echo "status $?"; nice -n 10 echo nice; command -v cd echo printf | tr '\n' ' '; echo
''', args='-q first')
# the commands that work on files and folders
case('files-more', r'''
mkdir -p proj/data proj/out/qc; printf '>a\nAC\n' > proj/data/r.fa; printf 'x\n' > proj/out/qc/r.txt; printf 'echo hi\n' > proj/run.sh; chmod +x proj/run.sh; cd proj
ls -a | head -n 3; ls -R; ls -1 */; ls -d */ data
cp -v data/r.fa copy.fa; mv -v copy.fa moved.fa; rm -v moved.fa; mkdir -v one; mkdir -pv two/three; rmdir -v one; rmdir -p two/three; ls -d two 2>&1
cp -rv data data2 | sort; rm -rv data2 | sort; cp data/r.fa nodir/x 2>&1; echo "status $?"
basename -s .fa data/r.fa; basename -a a/1.txt b/2.txt; basename /; basename a/b/ ; basename -s .gz -a x.fq.gz y.fq.gz; dirname a/b/c.txt d.txt /x; dirname a//b/
realpath --relative-to=out data/r.fa; realpath --relative-to=. out/qc; realpath -e nosuch 2>&1 | sed 's/^realpath: //'; realpath data/../data | sed 's|.*/proj|proj|'
find . -type f -printf '%f %s\n' | sort; find . -type f -name '*.fa' -printf '%h/%f\n'; find . -maxdepth 1 -type d -printf '[%P]\n' | sort; find . -type f -printf '%y %d %m\n' | sort | uniq -c | sed 's/^ *//'; find . -name r.fa -printf '%T+ %TY-%Tm-%Td\n' | grep -cE '^20[0-9]{2}-[0-9]{2}-[0-9]{2}\+[0-9:.]+ 20[0-9]{2}-[0-9]{2}-[0-9]{2}$'; find . -name r.fa -printf '%t\n' | grep -cE '^[A-Z][a-z]{2} [A-Z][a-z]{2} [ 0-9]{2} [0-9:.]+ 20[0-9]{2}$'
find . -name out -prune -o -type f -print | sort; find . -type f -perm -u+x; find . -type f -executable; find . -type f -perm 644 | sort; find . -type f -name '*.fa' -quit | wc -l
du -a data | cut -f 2; du -a . | wc -l; du -s data out | cut -f 2; du -c data out | tail -n 1 | cut -f 2
cmp data/r.fa data/r.fa && echo same; cp data/r.fa c.fa; echo x >> c.fa; cmp -s data/r.fa c.fa; echo "status $?"; cmp data/r.fa nosuch 2> /dev/null; echo "status $?"; rm c.fa
cat data/r.fa | wc -l /dev/stdin; cat data/r.fa | grep -c A /dev/stdin; sort -r data/r.fa -o /dev/stdout | head -n 1; cat data/r.fa | sort /dev/stdin | wc -l
echo "to stderr" > /dev/stderr; echo "status $?"; echo out > /dev/stdout; { echo o; echo e > /dev/stderr; } 2> /dev/null; warn() { echo "warning: $*" > /dev/stderr; }; warn x 2> w.txt; cat w.txt; rm w.txt
ls nosuch 2>&1 > /dev/null | wc -l; ls nosuch > /dev/null 2>&1 | wc -l; ls nosuch data 2>&1 > o.txt | wc -l; cat o.txt; rm o.txt
[ -e /dev/null ] && echo exists; [ -f /dev/null ] || echo no-file; cp /dev/null empty.txt; wc -c < empty.txt; source /dev/null; echo "status $?"; cat /dev/null | wc -c; rm empty.txt
t=$(mktemp -u XXXXXX.tmp); [ -e "$t" ] || echo not-made; t=$(mktemp -p . XXXXXX --suffix=.fa); ls *.fa | wc -l; rm -f ./*.fa; d=$(mktemp -d); [ -d "$d" ] && echo dir; rmdir "$d"
date -u +%Z; date -u -d @0 +%Y-%m-%dT%H:%M:%SZ; TZ=UTC date -d '2024-06-01 12:00' +%s; date -u -d '2024-01-15' +%A; date -u -R -d @86400
cd ..; rm -r proj; ls | wc -l
''')

# <( commands ) and >( commands ): here the commands run before (after) the command they belong to.
# (bash does not wait for the commands in >( ). So that the three lines with >( ) give the same in bash every time,
# also on a busy computer: in the first and the third the commands in >( ) hold the pipe that the last command reads –
# it cannot end before they have; the second waits until their file is there.)
case('process-substitution', r'''
printf 'b\na\nc\n' > one.txt; printf 'c\nb\nd\n' > two.txt
diff <(sort one.txt) <(sort two.txt); echo "status $?"
comm -12 <(sort one.txt) <(sort two.txt)
paste <(cut -c 1 one.txt) <(tr a-z A-Z < two.txt)
join <(sort one.txt) <(sort two.txt) | wc -l
while read -r x; do echo "<$x>"; done < <(sort -r one.txt)
n=0; while read -r x; do n=$((n + 1)); done < <(cat one.txt two.txt); echo "$n lines"
cat <(echo first) <(echo second) one.txt | wc -l
wc -l < <(seq 5)
sort <(printf '2\n1\n') <(printf '4\n3\n') | paste -sd ' '
echo "$(cat <(echo inner))"
grep -c b <(cat one.txt two.txt)
grep -f <(printf 'a\nc\n') one.txt | sort
awk 'NR == FNR { seen[$1] = 1; next } $1 in seen' <(cat one.txt) two.txt
f() { cat "$1" | wc -l; }; f <(seq 3)
if diff -q <(sort one.txt) <(sort one.txt) > /dev/null; then echo identical; fi
mapfile -t L < <(sort one.txt); echo "${#L[@]} ${L[0]}"
read -r first < <(sort two.txt); echo "$first"
cmp -s <(echo x) <(echo x) && echo same; cmp -s <(echo x) <(echo y) || echo different
seq 3 | tee >(wc -l > count.txt; true) | paste -sd+; cat count.txt
echo "to both" | tee >(tr a-z A-Z > upper.txt) > lower.txt; for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do [ -s upper.txt ] && break; sleep 0.1; done; cat lower.txt upper.txt
{ seq 4 > >(paste -sd,); } | cat
diff <(echo "a b" | tr ' ' '\n') <(printf 'a\nb\n') && echo "nested quotes ok"
x=$(comm -13 <(sort one.txt) <(sort two.txt)); echo "only in two: $x"
ls /tmp/.psub-* 2> /dev/null | wc -l
''')

# a new process (bash script.sh, bash -c) gets the exported variables – no others, and no functions
case('export-scope', r'''
REF=data/ref.fa; SAMPLE=NA12878; export SAMPLE
printf 'echo "ref=[${REF:-unset}] sample=[${SAMPLE:-unset}] threads=[${THREADS:-unset}]"\n' > child.sh
bash child.sh; bash -c 'echo "[${REF:-unset}] [${SAMPLE:-unset}]"'; (echo "subshell: $REF"); echo "$(echo "substitution: $REF")"
REF=other bash child.sh; THREADS=4 bash child.sh; echo "after: [${THREADS:-unset}]"
export REF; bash child.sh; export -n REF; bash child.sh; export THREADS=2; bash child.sh; unset THREADS; bash child.sh
helper() { echo "helper runs"; }; printf 'helper 2> /dev/null || echo "no function helper here"\n' > f.sh; bash f.sh; source f.sh; ( helper )
arr=(a b); export arr 2> /dev/null; bash -c 'echo "array: [${arr[0]:-unset}]"'
env | grep -c '^SAMPLE=NA12878$'; env | grep -c '^REF='; printenv SAMPLE; printenv REF; echo "status $?"; x=1; export x; env | grep -c '^x=1$'
env A=1 B=2 bash -c 'echo "$A$B"'; echo "[${A:-unset}]"; A=5 env | grep -c '^A=5$'; env -i bash -c 'echo "[${SAMPLE:-unset}]"' 2> /dev/null | head -n 1
export -p | grep -c 'declare -x SAMPLE="NA12878"'; declare -x D1=one; bash -c 'echo "$D1"'; declare +x D1; bash -c 'echo "[${D1:-unset}]"'
f() { local L=local; export E=exported; bash -c 'echo "[${L:-unset}] [${E:-unset}]"'; }; f
printf 'echo "$#:$1:$2"; echo "${0##*/}"\n' > args.sh; V="a b"; bash args.sh "$V" c; chmod +x args.sh; ./args.sh x
printf 'export FROM_CHILD=1; INNER=2\n' > setvars.sh; bash setvars.sh; echo "[${FROM_CHILD:-unset}]"; source setvars.sh; echo "[$FROM_CHILD] [$INNER]"
set -o pipefail; printf 'false | true; echo "status $?"\n' > pf.sh; bash pf.sh; set +o pipefail
echo 'wc -l' | xargs -I{} sh -c 'echo "sh sees [${REF:-unset}] [${SAMPLE:-unset}]"'
''')
case('builtins-3', r'''
expr 2 + 3; expr 7 / 2; expr 5 \* 3; expr 10 % 3; expr length hello; expr substr hello 2 3; expr index hello l; expr 1 = 1; expr a \< b
expr 3 \> 5; echo "status $?"; expr match abc 'a.*'; expr abc : 'a\(.\)c'; expr abc : 'x'; echo "status $?"; expr \( 1 + 2 \) \* 3; expr 5 - 10; expr hello : '.*'
expr '' \| default; expr 0 \& 5; echo "status $?"; expr 3 \>= 3; expr abc = abc; expr 1 + x 2> /dev/null; echo "status $?"; n=$(expr 4 + 1); echo $n
type -t echo; type -t ls; type -t if; f() { :; }; type -t f; type -t nosuchcmd; echo "status $?"; type -P cat | wc -l; type if | head -n 1; type f | head -n 1
echo -e 'a\tb\\c'; echo -e 'x\0101y'; echo -e 'one\ctwo'; echo; echo -e '\x41\x42' '\n\\'; echo -n -e 'n\n'; echo -e "tab\there"; echo -E 'a\tb'; echo 'a\tb'
set -o | grep -E '^(errexit|nounset|pipefail|xtrace) ' | tr -s ' \t' ' '; set -eu; set -o | grep -E '^(errexit|nounset) ' | tr -s ' \t' ' '; set +eu; set +o | grep -c '^set [-+]o '
shopt -s extglob; shopt extglob | tr -s ' \t' ' '; shopt -u extglob; shopt extglob | tr -s ' \t' ' '; shopt -q nullglob; echo "status $?"; shopt -s nullglob; shopt -q nullglob; echo "status $?"; shopt -u nullglob
declare -i N=5+3; echo $N; N+=2; echo $N; N=N*2; echo $N; declare -l low=ABC; echo $low; low=XyZ; echo $low; declare -u up=abc; echo $up; declare -r RO=1; RO=2 2> /dev/null
echo "$RO $?"
declare -p N low RO | sed 's/declare //'; declare -a list=(1 2); list+=(3); declare -p list; declare -A map=([k]=v); declare -p map; unset N low up
g() { local -i n=2+2; local -r c=const; local -l w=LOW; echo "$n $c $w"; }; g; n=text; c=free; w=UP; echo "$n $c $w"; readonly Z=9; unset Z 2> /dev/null; echo "$Z"
x=3; y=x; z=y; echo $((y)) $((y + 1)) $((z * 2)); e='2 + 3'; echo $((e * 2)); u=; echo $((u + 1)) $((undefined_name + 1)); a=5; echo $((a > 2 ? a : 2)) $((a++ + ++a)) $a
i=08; echo $((10#$i + 1)) $((16#ff)) $((2#101)) $((8#17)) $((0x10)) $((010)); echo $(( 7 / 2 )) $(( -7 / 2 )) $(( -7 % 3 )) $(( 2 ** 10 )) $(( 1 << 10 ))
''')
case('files-3', r'''
mkdir -p w/x1/sub w/x2/sub; cd w; printf 'a\nb\nc\n' > d1; printf 'a\nB\nc\n' > d2; printf 'a\n b\nc\n' > d3; printf 'a\nb\nc' > d4; printf 'a\n\nb\nc\n' > d5
diff -q d1 d2; diff -s d1 d1; diff -i d1 d2 && echo same-i; diff -w d1 d3 && echo same-w; diff -b d1 d3 > /dev/null; echo "status $?"; diff --brief d1 d3; diff -B d1 d5 && echo same-B
diff d1 d4; diff -u d1 d4 | tail -n +3; diff d4 d4 && echo same; diff -U 1 d1 d2 | tail -n +3; diff --unified=0 d1 d2 | tail -n +3; diff -iq d1 d2; echo "status $?"
echo 1 > x1/f; echo 2 > x2/f; echo 3 > x1/only; echo s > x1/sub/s; echo s > x2/sub/s; echo t > x2/sub/t; diff -rq x1 x2; echo "status $?"; diff -r x1 x2; diff x1 x2
diff -rs x1/sub x1/sub; diff -ru x1 x2 | grep -v '^[-+][-+]'; diff -rN x1 x2 | grep -c '^diff'; diff d1 x1 2>&1; echo "status $?"; cp d1 x1/d1; diff d1 x1 && echo "file and folder"
chmod u+x,g-w d1; stat -c '%a %A' d1; chmod 600 d1; stat -c %a d1; ls -l d1 | cut -c 1-10; chmod go+r d1; stat -c %a d1; chmod a-x,u+w d1; chmod +x d1; stat -c %a d1; chmod 644 d1
chmod -w d2; stat -c %a d2; chmod u+w d2; echo x >> d2; echo "status $?"; chmod =r d3; stat -c %A d3; chmod 644 d3; chmod nosuch 2>&1 | head -n 1
touch -c nope.txt; ls nope.txt 2>&1 | grep -c 'No such'; touch -d '2020-01-02 03:04:05' old; touch -r old ref; [ old -ot d1 ] && echo older; [ ref -nt d1 ] || echo ref-old-too; touch -t 202001020304 t2; [ t2 -ot d1 ] && echo t-older
stat --printf='%s %n\n' d1; stat -c '%s' d1 d2; stat -c '%F' x1 d1; stat --format='%U:%G' d1 | grep -c ':'; stat -c %h x1 | wc -c | tr -d ' '
nl d1 | cat -A; nl -ba d5 | tail -n 2; nl -w 2 -s ') ' d1; nl -n rz -w 3 d1 | head -n 1; nl -v 5 -i 5 d1 | cut -f 1 | tr -d ' ' | paste -sd,; nl -s: -w1 d5
tac d1 | cat -A; tac d4 | cat -A; printf 'no newline' | tac; echo; tac d1 d2 | wc -l; rev d1 | head -n 1
ls -m; ls -1 --color=never | head -n 2; ls --color=auto -d x1; ls -x | head -n 1 | wc -l; ls -1 --group-directories-first | head -n 2; ls -lg d1 | awk '{print NF}'; ls -lo d1 | awk '{print NF}'; ls -ln d1 | awk '{print $3 == $4}'
cd ..; rm -r w
''')

# real programs on folders and files that the page keeps: grep -r, sed -i, sort -o, gzip; and pushd / popd
case('folders-and-programs', r'''
mkdir -p g/a/b g/c && cd g && printf 'needle one\nhay\n' > a/x.txt && printf 'hay\nneedle two\n' > a/b/y.txt && printf 'needle three\n' > c/z.log
grep -r needle . | sort; grep -rn needle a | sort; grep -rl needle . | sort; grep -rc needle . | sort; grep -r --include='*.txt' needle . | sort | wc -l; grep -rL needle . | sort
grep -rh needle . | sort; grep -ri NEEDLE c; grep -r nothing .; echo "status $?"; grep -l needle a/*.txt a/b/*.txt; grep -c hay a/x.txt a/b/y.txt; grep -A1 one a/x.txt; grep -B1 two a/b/y.txt
grep -E 'one|three' -r . | sort; grep -o 'needle [a-z]*' a/x.txt; grep -q needle a/x.txt && echo found; grep -s x nosuch; echo "status $?"; grep -e one -e hay a/x.txt | wc -l; grep -x hay a/x.txt
cp a/x.txt e.txt; sed -i 's/needle/pin/' e.txt; cat e.txt; sed -i.bak '1d' e.txt; cat e.txt; ls e.txt*; sed -i -e 's/hay/straw/' -e 's/$/!/' e.txt; cat e.txt; rm e.txt e.txt.bak
printf 'b\na\n' > s.txt; sort -o s.txt s.txt; cat s.txt; echo c | tee -a s.txt > /dev/null; wc -l s.txt a/x.txt; cat s.txt a/x.txt | wc -l; head -n 1 s.txt a/x.txt; tail -n 1 -q s.txt a/x.txt; rm s.txt
cp a/x.txt z.txt; gzip z.txt; ls z.txt*; zcat z.txt.gz | head -n 1; gunzip z.txt.gz; ls z.txt*; gzip -k z.txt; ls z.txt* | wc -l; gzip -c z.txt | zcat | wc -l; gunzip -c z.txt.gz | wc -l; zgrep -c needle z.txt.gz; rm z.txt z.txt.gz
pushd a > /dev/null; pwd | sed 's|.*/g/|g/|'; pushd b > /dev/null; pwd | sed 's|.*/g/|g/|'; popd > /dev/null; pwd | sed 's|.*/g/|g/|'; popd > /dev/null; pwd | sed 's|.*/||'; popd 2> /dev/null; echo "status $?"
pushd a | wc -w; dirs | wc -w; pushd nosuch 2> /dev/null; echo "status $?"; (pushd a > /dev/null; dirs | wc -w); dirs | wc -w
{ echo o; echo e >&2; } > both.txt 2>&1; cat both.txt; ls nosuch 2>> errs.txt; ls nosuch2 2>> errs.txt; wc -l < errs.txt; echo x &> amp.txt; echo y &>> amp.txt; wc -l < amp.txt; rm both.txt errs.txt amp.txt
echo a > 'file with space.txt'; cat file\ with\ space.txt; f='file with space.txt'; wc -c < "$f"; rm "$f"; cd ..; rm -r g; ls | wc -l
''')

case('ifs-and-read', r'''
printf 'a b  c\n' > l.txt; printf 'x:y:z\n1:2\n' > c.txt; printf 's1,NA12878,31\ns2,NA12891,27\n' > t.csv
IFS=,; bash -c 'x="a b,c"; for w in $x; do echo "[$w]"; done'; unset IFS; x="p q"; for w in $x; do echo "<$w>"; done
while IFS=, read -r id name depth; do echo "$name=$depth"; done < t.csv; echo "IFS is [${IFS-unset}]"
IFS=: read -r a b c < c.txt; echo "$a|$b|$c"; read -r a b < l.txt; echo "$a|$b"; read a b c d < l.txt; echo "$a|$b|$c|[$d]"
while IFS= read -r line; do echo "[$line]"; done < <(printf '  lead\ntrail  \n'); read -r one < <(printf 'no newline'); echo "rc=$? $one"
read -ra parts <<< "x y z"; echo "${#parts[@]} ${parts[2]}"; IFS=/ read -ra p <<< "a/b/c"; echo "${p[1]} ${#p[@]}"; read -r -d ';' q <<< "one;two"; echo "$q"
read -n 3 k <<< "abcdef"; echo "$k"; read -N 4 m <<< "ab cdef"; echo "[$m]"; printf 'k=v\n' | { IFS== read -r kk vv; echo "$kk $vv"; }
f() { local IFS=,; echo "$*"; }; f a b c; echo "$(IFS=+; set -- 1 2 3; echo "$*")"; set -- x y z; echo "$*"; IFS=- eval 'echo "$*"'
printf 'a\\tb\n' | { read v; echo "$v"; }; printf 'a\\tb\n' | { read -r v; echo "$v"; }; printf 'two \\\nlines\n' | { read v; echo "$v"; }
''')
case('bytes-through-blocks', r'''
seq 200 > n.txt; ref=$(md5sum < n.txt)
gzip -c n.txt > a.gz; { gzip -c n.txt; } > b.gz; f() { gzip -c "$1"; }; f n.txt > c.gz; ( gzip -c n.txt ) > d.gz
for z in a b c d; do [ "$(zcat $z.gz | md5sum)" = "$ref" ] && echo "$z ok"; done
f n.txt | zcat | tail -n 1; { gzip -c n.txt; } | zcat | wc -l; for i in 1; do gzip -c n.txt; done | zcat | head -n 2 | tail -n 1
bash -c 'gzip -c n.txt' | zcat | wc -l; echo 'gzip -c n.txt' > g.sh; bash g.sh | zcat | md5sum | cut -c1-8; md5sum < n.txt | cut -c1-8
if true; then gzip -c n.txt; fi | gunzip -c | wc -l; while read -r x; do gzip -c "$x"; done <<< n.txt | zcat | wc -l
zcat < <(gzip -c n.txt) | wc -l; cmp <(zcat a.gz) n.txt && echo same; eval 'gzip -c n.txt' | zcat | wc -l; env gzip -c n.txt | zcat | wc -l
command gzip -c n.txt | gunzip | wc -l; x=1 gzip -c n.txt | zcat | sed -n 3p; gzip -c n.txt | { cat; } | zcat | wc -l; gzip -c n.txt | cat | cat | zcat | wc -l
printf 'a\0b\0c' | { cat; } | od -An -c; printf 'x\0y' | tr '\0' '\n'; printf '\001\002\377' | { cat; } | od -An -tx1; g() { cat; }; printf 'p\0q' | g | wc -c
''')
case('redirect-order', r'''
{ echo out; echo err >&2; } > o1.txt 2>&1; cat o1.txt; { echo out; echo err >&2; } 2>&1 > o2.txt | sed 's/^/pipe: /'; cat o2.txt
f() { echo fo; echo fe >&2; }; f > f1.txt 2>&1; wc -l < f1.txt; f 2> f2.txt > f3.txt; cat f2.txt f3.txt; f 2>&1 > /dev/null | wc -l; f > /dev/null 2>&1 | wc -l
ls nosuch > e1.txt 2>&1; wc -l < e1.txt; ls nosuch 2>&1 > e2.txt | wc -l; wc -c < e2.txt; ls nosuch 2> /dev/null; echo "rc=$?"
exec 3> fd3.txt; echo one >&3; echo two >&3; exec 3>&-; cat fd3.txt; exec 4>> fd3.txt; echo three >&4; exec 4>&-; wc -l < fd3.txt
printf 'r1\nr2\nr3\n' > in.txt; exec 3< in.txt; read -r a <&3; read -u 3 b; echo "$a $b"; cat <&3; exec 3<&-
while read -r -u 5 l; do echo "got $l"; done 5< in.txt; while read -r l <&6; do echo "six $l"; break; done 6< in.txt
exec 3>&1; exec 1> cap.txt; echo captured; exec 1>&3 3>&-; echo back; cat cap.txt
{ echo a >&3; echo b; } 3> t3.txt > t1.txt; cat t3.txt t1.txt; echo x 3> t4.txt >&3; cat t4.txt; echo y > t5.txt 2> t6.txt; cat t5.txt; wc -c < t6.txt
for i in 1 2; do echo "i=$i"; echo "e$i" >&2; done > loop.txt 2> loop.err; cat loop.txt loop.err; if true; then echo in-if; fi > if.txt; cat if.txt
echo first > app.txt; echo second >> app.txt; { echo third; echo fourth; } >> app.txt; wc -l < app.txt; : > app.txt; wc -c < app.txt
''')
case('files-opened-first', r'''
printf 'b\na\nc\n' > f.txt; sort f.txt > f.txt; wc -c < f.txt; printf 'b\na\n' > g.txt; sort g.txt -o g.txt; cat g.txt
ls > list.txt; grep -c list.txt list.txt; rm list.txt; printf 'x\n' > h.txt; tr x y < h.txt > h.txt; wc -c < h.txt
printf 'k\n' > k.txt; cat k.txt >> k.txt 2> /dev/null; echo "rc=$?"; cat k.txt; printf '1\n' > a.txt; printf '2\n' > b.txt; cat a.txt b.txt > b.txt 2> /dev/null; echo "rc=$?"; cat b.txt
printf 'data\n' > keep.txt; grep data keep.txt > keep.txt; wc -c < keep.txt; echo new > made.txt; [ -f made.txt ] && echo made
set -C; echo one > nc.txt; echo two > nc.txt 2> /dev/null; echo "rc=$?"; cat nc.txt; echo three >| nc.txt; cat nc.txt; echo four >> nc.txt; wc -l < nc.txt; set +C; echo five > nc.txt; cat nc.txt
nosuchcmd > out1.txt 2> /dev/null; echo "rc=$?"; ls out1.txt; wc -c < out1.txt; echo x > nodir/out.txt 2> /dev/null; echo "rc=$?"; echo y > /dev/null/z 2> /dev/null; echo "rc=$?"
printf 'q\n' > q.txt; head -n 1 q.txt > q.tmp && mv q.tmp q.txt; cat q.txt; rm -f q.txt > q.txt; ls q.txt 2> /dev/null | wc -l
''')
case('export-and-shells', r'''
A=1; export B=2; bash -c 'echo "[$A] [$B]"'; C=3 bash -c 'echo "[$C]"'; echo "[$C]"; export A; bash -c 'echo "[$A]"'
set -a; D=4; E=5; set +a; F=6; bash -c 'echo "$D $E [$F]"'; declare -x G=7; bash -c 'echo "$G"'; export -n G; bash -c 'echo "[$G]"'
hello() { echo "hello $1"; }; bash -c 'hello a' 2> /dev/null; echo "rc=$?"; export -f hello; bash -c 'hello b'; echo 'hello c' > h.sh; bash h.sh
f() { local L=in; export L; bash -c 'echo "L=$L"'; }; f; bash -c 'echo "L=[$L]"'; g() { local B; bash -c 'echo "B=$B"'; }; g
echo "$SHLVL" | grep -c '^[0-9]*$'; bash -c 'echo $((SHLVL - '"$SHLVL"'))'; x=outer; ( x=inner; echo "$x" ); echo "$x"; echo "$(x=sub; echo $x) $x"
mkdir -p out/qc && cd "$_" && pwd | sed 's|.*/out|out|'; cd ../..; echo a b c; echo "[$_]"; true; echo "[$_]"; ls out > /dev/null; echo "[$_]"
readonly R=1; R=2 echo with-prefix 2> /dev/null; echo "rc=$?"; R=3 bash -c 'echo "child [$R]"' 2> /dev/null; echo "R=$R"
env -i bash -c 'echo "[$A] [$HOME]"'; env X1=1 bash -c 'echo $X1'; env -u A bash -c 'echo "[$A]"'; printenv B; printenv NOSUCH; echo "rc=$?"
bash -c 'echo "$0 $1 $#"' name arg1 arg2; bash -c 'nosuchcmd' 2>&1 | sed 's/: line [0-9]*//'; echo 'echo "from input $1"' | bash -s word
''')
case('arrays-and-patterns', r'''
a=(5 10 15); echo $((a[0] + a[2])) $((a[1] * 2)) $(( ${a[1]} / 5 )); i=1; echo $((a[i] + a[i+1])); ((a[0]++)); ((a[1] += 5)); echo "${a[@]}"
declare -A m=([x]=1 [y]=2); ((m[x] += 10)); echo "${m[x]} ${m[y]}"; k=y; echo $((m[$k] * 3)); echo "${!m[@]}" | tr ' ' '\n' | sort | tr '\n' ' '; echo
s=(a.fq b.fq c.fq); echo "${s[@]/%.fq/.bam}"; echo "${s[@]/#/in/}"; echo "${s[@]%.fq}"; echo "${s[-1]} ${s[@]: -2}"; unset 's[-1]'; echo "${#s[@]}"
e=(); echo "${e[@]:-none}" "${#e[@]}"; echo "${e[@]+set}|"; n=(1 2 3); echo "${n[@]:1:1}" "${!n[@]}"; n+=(4 5); echo "${#n[@]}"
x=abc123; [[ $x == [[:alpha:]]* ]] && echo alpha; [[ $x == *[[:digit:]] ]] && echo digit; [[ $x == +([a-z])+([0-9]) ]] && echo ext; case $x in *[!0-9]) echo nondigit;; *) echo digit-end;; esac
f=sample.R1.fastq.gz; echo "${f%%.*} ${f%.*} ${f#*.} ${f##*.}"; echo "${f/R1/R2} ${f//./_}"; echo "${f:7:2} ${f: -3}"; echo "${f^^} ${f^}"
touch r1.txt r2.txt r10.txt R3.TXT; echo r?.txt; echo r[0-9]*.txt; echo [rR]*.[tT]*; echo r{1,2}.txt; echo *.nomatch; shopt -s nullglob; echo *.nomatch; shopt -u nullglob
shopt -s nocasematch; [[ ABC == abc ]] && echo nocase; case Fastq in fastq) echo case-nocase;; esac; shopt -u nocasematch; [[ ABC == abc ]] || echo cased
mkdir -p d/e/f; touch d/a.txt d/e/b.txt d/e/f/c.txt; shopt -s globstar; echo d/**/*.txt; shopt -u globstar; echo d/*/*.txt
touch .hid; echo *hid; shopt -s dotglob; echo *hid; shopt -u dotglob; set -f; echo *.txt | wc -w; set +f; shopt -s failglob; echo *.zzz 2> /dev/null; echo "rc=$?"
mapfile -t lines < <(printf 'l1\nl2\nl3\n'); echo "${#lines[@]} ${lines[1]}"; mapfile -t -d , parts < <(printf 'a,b,c'); echo "${parts[2]}"; readarray -t two <<< $'p\nq'; echo "${two[0]}${two[1]}"
''')
case('printf-and-echo', r'''
printf '%.1f %.1f %.0f %.0f %.2f\n' 99.95 0.05 2.5 3.5 1.005; printf '%5.2f|%-6d|%06.2f|%+d|%x|%o|%e\n' 3.14159 42 2.5 7 255 8 12345.678
printf '%s=%d\n' a 1 b 2; printf '%5s|%-5s|%.2s\n' ab cd efgh; printf '%d %d\n' 0x1f 010; printf '%c%c\n' hello world; printf '%%|%3d%%\n' 50
printf '%q %q %q\n' 'a b' "it's" plain; printf '%b' 'tab\there\n'; printf '%s\n' "a\tb"; printf 'a\tb\n' | od -An -c
printf '\x41\101B\n'; printf '%d\n' abc 2> /dev/null; echo "rc=$?"; printf '%d\n' 3.7 2> /dev/null; echo "rc=$?"; printf -v v '%03d' 7; echo "$v"
TZ=UTC printf '%(%Y-%m-%d %H:%M:%S)T\n' 0; TZ=UTC printf '%(%F)T %(%a %b)T\n' 86400 1700000000; printf '%s\n' "$(TZ=UTC date -d @0 +%Y)"
echo -e 'a\tb\n'; echo -n no-newline; echo; echo -E 'a\tb'; echo -e '\101\x42'; echo -ne 'x\ty\n'; echo -en 'z\n'; echo -e 'stop\chere'; echo
echo -e '\0101' | od -An -c; echo 'single \n'; echo "double \n"; echo $'dollar\ttab' | od -An -c; echo -- a; echo - b; echo -x
printf 'ab\tc\n\0\377' | od -An -c; printf '\xff\xfe' | od -An -tx1; printf '\x1f\x8b' > magic.bin; od -An -tx1 magic.bin; wc -c < magic.bin; echo -ne '\x80\x81' | wc -c
printf '\303\251\n' | od -An -tx1; printf 'caf\xc3\xa9\n' | wc -c; printf '%b' '\0303\0251\n' | od -An -tx1; x=$'\x41\x42'; echo "$x"
''')
case('shell-options', r'''
set -o | grep -E '^(errexit|nounset|pipefail|noglob|noclobber|allexport|verbose|xtrace) ' | awk '{print $1 "=" $2}' | tr '\n' ' '; echo
set -eu -o pipefail; echo $-| tr -d 'hBs' | grep -o '[eu]' | tr -d '\n'; echo; set +eu +o pipefail; false; echo "after false rc=$?"
set -o nosuchoption 2> /dev/null; echo "rc=$?"; set -Z 2> /dev/null; echo "rc=$?"; shopt -s nosuchopt 2> /dev/null; echo "rc=$?"; shopt -q nullglob; echo "rc=$?"
shopt -s nullglob; shopt -q nullglob; echo "rc=$?"; shopt nullglob | awk '{print $2}'; shopt -p nullglob; shopt -u nullglob; shopt -p nullglob
shopt -s lastpipe; echo val | read lp; echo "[${lp:-unset}]"; seq 3 | while read n; do last=$n; done; echo "last=$last"; shopt -u lastpipe; echo v2 | read lp2; echo "[${lp2:-unset}]"
set -o pipefail; false | true; echo "pipefail rc=$?"; true | false | true; echo "rc=$? ${PIPESTATUS[*]}"; set +o pipefail; false | true; echo "rc=$?"
f() { set -- a b; echo "$#"; }; set -- 1 2 3; f; echo "$# $1"; set --; echo "$#"; set -- "x y" z; for a in "$@"; do echo "[$a]"; done
x=$(set -e; false; echo not-here); echo "sub rc=$? [$x]"; (set -e; false; echo no); echo "subshell rc=$?"; bash -c 'set -e; false; echo no'; echo "child rc=$?"
bash -ec 'false; echo no'; echo "rc=$?"; bash -uc 'echo "$unset_var"; echo no' 2> /dev/null; echo "rc=$?"; bash -c 'set -n; echo not-run'; echo "rc=$?"; bash -n -c 'echo not-run; if' 2> /dev/null; echo "rc=$?"
trap 'echo "exit trap"' EXIT; set -e; echo before; false; echo not-reached
''')
case('nul-separated-names', r'''
mkdir -p d; touch 'd/a b.txt' d/c.txt 'd/e f.txt'
find d -name '*.txt' -print0 | xargs -0 -n 1 basename | sort; find d -type f -print0 | xargs -0 ls | wc -l; find d -name '*.txt' -print0 | sort -z | tr '\0' '\n'
find d -type f -print0 | while IFS= read -r -d '' f; do echo "[$f]"; done | sort; find d -type f -print0 | xargs -0 -I{} echo "file: {}" | sort
printf 'x y\0z\0' | xargs -0 -n 1 echo; printf 'a\0b\0c\0' | tr '\0' '\n' | wc -l; printf 'one\0two\0' | { read -r -d '' first; echo "$first"; }
mapfile -d '' -t names < <(find d -type f -print0 | sort -z); echo "${#names[@]} [${names[0]}]"; printf '%s\0' p q r | xargs -0 echo; printf '1\n2\n3\n' | xargs -d '\n' -n 2 echo
basename -z d/c.txt | od -An -c; dirname -z d/c.txt | od -An -c; printf 'b\0a\0' | sort -z | od -An -c; printf 'n1\0n2\0' | grep -z n2 | od -An -c
find d -type f -print0 | xargs -0 -n 1 sh -c 'echo "arg: $0"' | sort; find d -name 'c*' -exec echo found {} \; ; find d -name '*.txt' -exec echo all {} + | wc -w
''')
case('gzip-several-files', r'''
seq 5 > a.txt; seq 6 9 > b.txt; printf 'plain\n' > p.txt
gzip a.txt b.txt; ls; zcat a.txt.gz b.txt.gz | wc -l; gunzip a.txt.gz b.txt.gz; ls; gzip -k a.txt; ls a.txt*; gzip -c a.txt b.txt > ab.gz; zcat ab.gz | tail -n 1
gzip -dc ab.gz | wc -l; gunzip -c ab.gz a.txt.gz | wc -l; zcat -f p.txt; gzip -cd < ab.gz | head -n 1; cat a.txt | gzip | zcat | wc -l; gzip < b.txt > b2.gz; zcat b2.gz | md5sum; md5sum < b.txt
gunzip nosuch.gz 2> /dev/null; echo "rc=$?"; gzip nosuch.txt 2> /dev/null; echo "rc=$?"; gzip -t ab.gz; echo "rc=$?"; zcat p.txt 2> /dev/null; echo "rc=$?"
gzip -f a.txt; ls a.txt* ; gunzip -f a.txt.gz; cat a.txt | wc -l; zgrep -c 7 ab.gz; zcat ab.gz | grep -c .; gzip -9 -c a.txt | zcat | wc -l; gzip -1 -c a.txt | gunzip -c | wc -l
for f in a.txt b.txt; do gzip -c "$f" > "$f.gz"; done; zcat *.txt.gz | wc -l; for z in *.txt.gz; do zcat "$z" | head -n 1; done; rm -f *.gz; ls | wc -l
''')
case('calculator-and-bytes', r'''
echo '2^100' | bc; echo 'scale=5; 10/3' | bc; echo '5 % 3; -7 / 2' | bc; echo 'scale=10; sqrt(2)' | bc; echo '3 > 2; 3 == 4' | bc; bc <<< '12 + 30'
echo 'scale=4; a(1)*4' | bc -l; echo 'l(10)' | bc -l | cut -c1-12; echo 'e(1)' | bc -l | cut -c1-12; echo "scale=2; 3519 * 76 / 56000" | bc
x=$(echo "scale=3; 22/7" | bc); echo "x=$x"; if (( $(echo "$x > 3" | bc -l) )); then echo bigger; fi; echo 'a = 5; a * 2; a++; a' | bc
printf 'define f(n) {\n if (n <= 1) return (1);\n return (n * f(n-1));\n}\nf(20)\n' | bc; printf 'for (i = 1; i <= 3; i++) i * i\n' | bc
echo 'obase=2; 99' | bc; echo 'obase=16; 255' | bc; echo 'ibase=16; FF' | bc; echo 'ibase=2; 1010' | bc; echo 'scale=2; 0.1 + 0.2; .5 * 4' | bc; echo '1/0' | bc 2> /dev/null; echo "rc=$?"
printf 'hello\n' | od -c; printf 'hello\n' | od -An -tx1; printf 'ab\tc\n' | od -An -c; printf 'abc' | od -An -tu1; seq 3 | od -An -c | tr -s ' '
printf 'hello world\n' | base64; printf 'hello world\n' | base64 | base64 -d; printf 'aGVsbG8=' | base64 --decode; echo; seq 30 | base64 -w 0 | wc -c; seq 30 | base64 | wc -l
printf 'hello\n' | sha1sum; printf 'hello\n' | sha256sum | cut -c1-16; printf 'hello\n' | sha512sum | cut -c1-16; printf 'x\n' > x.txt; sha1sum x.txt > x.sha1; sha1sum -c x.sha1; md5sum x.txt | md5sum -c -
seq 10 > n.txt; split -l 4 n.txt part_; ls part_*; wc -l < part_ac; cat part_* | md5sum; md5sum < n.txt; split -n 3 n.txt h; wc -c < haa; ls h?? | wc -l; split -b 5 -d n.txt b; ls b0* | wc -l
truncate -s 5 n.txt; wc -c < n.txt; truncate -s +3 n.txt; od -An -c n.txt; truncate -s 0 n.txt; wc -c < n.txt; truncate -s 1K k.bin; wc -c < k.bin; head -c 3 /dev/zero | od -An -c
printf 'a\tb\tc\n' | expand | od -An -c; printf 'a\tb\n' | expand -t 4; printf 'x\ty\n' | expand -t 2,6 | od -An -c
''')
case('listings', r'''
own() { sed -E 's/^([-dl][-rwxsStT]{9}[.+]? +[0-9]+) +[^ ]+ +[^ ]+ /\1 U G /' | sed -E 's/[A-Z][a-z]{2} +[0-9]+ +[0-9:]+ /DATE /'; }
mkdir -p d1/sub d2; printf 'alpha\nbeta\n' > a.txt; : > empty.txt; seq 300 > big.txt; printf 'one\n' > d1/x.txt; printf 'deep\n' > d1/sub/z.txt; echo '#!/bin/bash' > run.sh; chmod +x run.sh
ls; ls -1 d1; ls -a d1 | tr '\n' ' '; echo; ls -A | wc -l; ls -p; ls -F; ls -d d*; ls -d */; ls d1 d2 a.txt; ls -R d1
ls -l | own; ls -l a.txt big.txt | own; ls -ld d1 d2 | own | awk '{print $1, $2, $5}'; ls -lh big.txt | awk '{print $5}'; ls -la d1 | wc -l; ls -l d2
ls -s; ls -s a.txt empty.txt; ls -1s d1; ls -S; ls -Sr | head -n 2; ls -r | head -n 2; ls -X | head -n 3; ls -m; ls -C; ls -x; ls -w 30 -C; ls -w 20 -m
ls -1 --hide='*.txt'; ls -I '*.txt' -I 'd*'; touch back~; ls -B | wc -l; rm back~; touch 'sp ace'; ls -Q sp*; ls -b sp*; ls -1 sp*; rm 'sp ace'; ls nosuch a.txt 2> /dev/null; echo "rc=$?"
du -a d1 | sort -k2; du -s d1 | cut -f1; du -sh d1 | cut -f1; du -h a.txt big.txt | cut -f1; du -c a.txt big.txt | tail -n 1 | cut -f1; du -d 1 . | wc -l
stat -c '%s %n %F' a.txt empty.txt d1; stat -c '%a %A' a.txt run.sh d1; stat -c '%h' d1 d1/sub a.txt; stat --format=%n -- a.txt; stat -c '%s' nosuch 2> /dev/null; echo "rc=$?"
t=$(mktemp -p . tmp.XXXXXX); [ -f "$t" ] && echo "made ${#t}"; rm "$t"; d=$(mktemp -d -p . dir.XXXX); [ -d "$d" ] && echo dir; rmdir "$d"; TMPDIR=d2 mktemp | grep -c '^d2/tmp\.'; rm -f d2/tmp.*
tac a.txt; printf 'a\nb' | tac | od -An -c; tac -s , <<< 'x,y,z' | head -n 2; nl a.txt; printf 'a\n\nb\n' | nl -ba; printf 'a\nb\n' | nl -w 2 -s ': '; printf 'a\nb\n' | nl -nrz -w 3 -v 9
top=$PWD; mkdir -p p/q r; pushd p > /dev/null; pushd ../r > /dev/null; dirs | wc -w; pushd +1 > /dev/null; pwd | sed 's|.*/||'; popd > /dev/null; popd > /dev/null; pwd | sed 's|.*/||'; cd "$top"
[ -e /dev/null ] && [ -c /dev/null ] && [ -d /dev ] && echo devices; ls /dev/null; cp a.txt /dev/null; echo "rc=$?"; cat a.txt | tee /dev/stdout | wc -l; cat a.txt | tee /dev/stderr 2>&1 | wc -l
expr 9223372036854775807 + 1; expr 123456789012 \* 1000; expr 7 / 2; expr 7 % 2; expr length hello; expr substr hello 2 3; expr abc \< abd; expr hello : 'h\(.*\)o'
''')
case('diff-formats', r'''
printf 'alpha\nbeta\ngamma\n' > a.txt; printf 'alpha\nBETA\ngamma\ndelta\n' > b.txt; mkdir -p d1/sub d2; printf 'one\ntwo\n' > d1/x.txt; printf 'one\nTWO\n' > d2/x.txt; echo same > d1/y.txt; echo same > d2/y.txt; echo deep > d1/sub/z.txt; echo only > d2/only2.txt
diff a.txt b.txt; echo "rc=$?"; diff a.txt a.txt; echo "rc=$?"; diff -q a.txt b.txt; diff -s a.txt a.txt; diff a.txt nosuch 2> /dev/null; echo "rc=$?"
diff -u a.txt b.txt | sed '1,2d'; diff -U 0 a.txt b.txt | sed '1,2d'; diff -u --label old --label new a.txt b.txt | head -n 2; diff --unified=1 a.txt b.txt | tail -n +3
diff -c a.txt b.txt | sed '1,2d'; diff -e a.txt b.txt; diff -n a.txt b.txt; diff --normal a.txt b.txt | head -n 1
diff -y -W 40 a.txt b.txt; diff -y --suppress-common-lines -W 40 a.txt b.txt; diff -y --left-column -W 30 a.txt a.txt | head -n 2
diff -i a.txt b.txt; diff -w <(echo 'a  b') <(echo 'ab'); echo "rc=$?"; diff -b <(echo 'a  b') <(echo 'a b'); echo "rc=$?"; diff -B <(printf 'a\n\nb\n') <(printf 'a\nb\n'); echo "rc=$?"
diff -r d1 d2; echo "rc=$?"; diff -rq d1 d2; diff -rN d1 d2; diff -rqN d1 d2; diff -rs d1 d1 | sort; diff d1 d2 | grep -c Common
diff -r -x '*.txt' d1 d2; echo "rc=$?"; diff -rq -x sub -x only2.txt d1 d2; diff -rNu d1 d2 | grep -v '^[-+][-+][-+]'; diff <(sort a.txt) <(sort -r a.txt) | head -n 1
cmp a.txt b.txt | sed 's/char/byte/'; echo "rc=${PIPESTATUS[0]}"; cmp -s a.txt a.txt; echo "rc=$?"; cmp -l a.txt b.txt 2> /dev/null | head -n 2; comm -12 <(sort a.txt) <(sort b.txt)
''')
case('diff-large', r'''
seq 1 20000 > A; seq 1 20000 | sed 's/^7$/x/; 15000d; 19990,19995d' > B2; diff A B2; echo "rc=$?"; diff -u A B2 | tail -n +3 | md5sum
seq 1 7000 | sed 's/^/a/' > x1; seq 1 7000 | sed 's/^/b/' > x2; diff x1 x2 | tail -n 3; diff x1 x2 | wc -l; diff x1 x2 | md5sum
seq 1 6000 | awk '{print ($1 * 7919) % 501}' > r1; seq 1 6500 | awk '{print ($1 * 104729) % 503}' > r2; diff r1 r2 | grep -c '^[0-9]'; diff r1 r2 | md5sum; diff -d r1 r2 | md5sum; diff -H r1 r2 | md5sum; diff -e r1 r2 | md5sum
seq 1 30000 | awk '{print ($1 * 31) % 9973}' > s1; awk 'NR % 37 != 0' s1 | sed '5000s/.*/changed/; 21000i\added' > s2; diff s1 s2 | md5sum; diff -H s1 s2 | md5sum; cmp s1 s2 | sed 's/char/byte/'; cmp -l r1 r2 2> /dev/null | wc -l
printf 'a\nb' > n1; printf 'a\nb\n' > n2; printf 'a\nb\nb' > n4; diff n1 n2; diff -b n1 n2; echo "rc=$?"; diff n1 n4; diff n2 n4; diff -u n4 n1 | tail -n +3; diff -e n1 n4 2>&1; echo "rc=$?"
''')
case('output-order', r'''
printf 'a1\na2\n' > a.txt; printf 'a3\n' > b.txt
{ grep a a.txt nosuch b.txt; } 2>&1
{ wc -l a.txt nosuch b.txt; } 2>&1
f() { head -n 1 a.txt nosuch b.txt; }; f 2>&1 | cat -n
x=$( { cat a.txt nosuch b.txt; } 2>&1 ); echo "$x"
for f in a.txt nosuch b.txt; do cat "$f"; done 2>&1 | cat -n
bash -c 'sort a.txt nosuch; echo done' 2>&1
printf 'a\nb' > n1; printf 'x\nb' > n3; { diff -e n1 n3; } 2>&1; echo "rc=$?"
grep a a.txt nosuch b.txt > all.txt 2>&1; cat all.txt; { grep a a.txt nosuch b.txt; } &> all2.txt; cmp all.txt all2.txt && echo same
''')
case('messages-in-scripts', r'''
{
nosuchcmd
cd nosuchdir
cat < nosuchfile
echo x > nosuchdir/f
mkdir d1; echo x > d1
popd
./nosuch.sh
source nosuch3.sh
} 2>&1 | sed 's/^.*s\.sh: /S: /'
f() {
  nosuchinf
}
f 2>&1 | sed 's/^.*s\.sh: /S: /'
x=$(nosuchsub 2>&1); echo "$x" | sed 's/^.*s\.sh: /S: /'
eval "nosucheval" 2>&1 | sed 's/^.*s\.sh: /S: /'
bash -c 'nosuch1
nosuch2' 2>&1
echo 'nosuch8' | bash 2>&1; bash nosuchfile.sh 2>&1; echo "rc=$?"
echo "line $LINENO $(echo $LINENO)"
''')


# ------------------------------------------------------------------------------------------------------
# Further scripts: what an independent review of the terminal turned up in October 2026, and the checks that
# were written while those faults were mended – set -e and traps, regular expressions, printf, substrings,
# functions as bash prints them, extglob, a pipe whose reader stops early. Most are one line long. Each starts
# in a folder with these small files:
FIX = {
    'in.txt': 'l1 a\nl2 b\nl3 c\nl4 d\nl5 e\n',
    'nums.txt': '3\n1\n2\n10\n2\n',
    'names.txt': 'sampleB\nsampleA\nsampleC\n',
    'tab.tsv': 'chr1\t100\tA\tG\nchr1\t250\tC\tT\nchr2\t30\tG\tA\n',
    'csv.csv': 'id,name,depth\ns1,NA12878,31\ns2,NA12891,27\ns3,NA12892,40\n',
    'utf.txt': 'café naïve\n你好 世界\nüber straße\n',
    'nonl.txt': 'first\nsecond\nlast-without-newline',
    'empty.txt': '',
    'a.txt': 'alpha\nbeta\ngamma\n',
    'b.txt': 'alpha\nBETA\ngamma\ndelta\n',
    'list.txt': 'a.txt\nb.txt\nin.txt\n',
    'small.fa': '>seq1 first\nACGTACGTAC\nGGGTTT\n>seq2 second\nTTTTAAAA\n',
    'small.fq': '@r1\nACGT\n+\nIIII\n@r2\nGGCC\n+\nIIII\n@r3\nTTAA\n+\nIIII\n',
    'd1/x.txt': 'one\ntwo\n',
    'd1/y.txt': 'same\n',
    'd1/sub/z.txt': 'deep\n',
    'd2/x.txt': 'one\nTWO\n',
    'd2/y.txt': 'same\n',
    'd2/only2.txt': 'only\n',
}

more('errexit-and-traps', r'''
set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; done; echo "after rc=$?"
set -e; for n in 1 2; do (( n < 2 )) && echo small; done; echo "after rc=$?"
set -e; for f in a.txt nosuch; do test -f $f && echo "found $f"; done; echo "after rc=$?"
set -e; for f in a.txt nosuch; do [ -f $f ] && echo "found $f"; done; echo "after rc=$?"
set -e; for f in a.txt nosuch; do grep -q alpha $f 2>/dev/null && echo "alpha in $f"; done; echo "after rc=$?"
set -e; i=0; while (( i < 2 )); do i=$((i+1)); [[ $i == 1 ]] && echo one; done; echo "after rc=$?"
set -e; i=0; until (( i >= 2 )); do i=$((i+1)); [[ $i == 1 ]] && echo one; done; echo "after rc=$?"
set -e; if true; then false && echo x; fi; echo "after rc=$?"
set -e; if false; then :; else false && echo x; fi; echo "after rc=$?"
set -e; { false && echo x; }; echo "after rc=$?"
set -e; case x in x) false && echo y ;; esac; echo "after rc=$?"
set -e; for n in 1 2; do for m in 1 2; do [[ $m == 1 ]] && echo "$n$m"; done; done; echo "after rc=$?"
set -e; while read -r l; do [[ $l == alpha ]] && echo "got $l"; done < a.txt; echo "after rc=$?"
set -e; cat a.txt | while read -r l; do [[ $l == alpha ]] && echo "got $l"; done; echo "after rc=$?"
set -e; f() { false && echo x; }; f; echo "after rc=$?"
set -e; f() { for n in 1 2; do [[ $n == 1 ]] && echo one; done; }; f; echo "after rc=$?"
set -e; ( false && echo x ); echo "after rc=$?"
set -e; ( for n in 1 2; do [[ $n == 1 ]] && echo one; done ); echo "after rc=$?"
set -e; x=$(for n in 1 2; do [[ $n == 1 ]] && echo one; done); echo "after rc=$? x=$x"
set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; done | cat; echo "after rc=$?"
set -e; for n in 1 2; do false || false; done; echo "after rc=$?"
set -e; for n in 1 2; do [[ $n == 1 ]] || echo "not one"; done; echo "after rc=$?"
set -e; for n in 1 2; do [[ $n == 2 ]] && echo two; done; echo "after rc=$?"
set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; true; done; echo "after rc=$?"
set -e; for n in 1 2; do if [[ $n == 1 ]]; then echo one; fi; done; echo "after rc=$?"
set -e; for n in 1 2; do ! true; done; echo "after rc=$?"
set -e; { for n in 1 2; do [[ $n == 1 ]] && echo one; done; } > o.txt; echo "after rc=$?"; cat o.txt
set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; done > o.txt; echo "after rc=$?"; cat o.txt
set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; done && echo "and-list"; echo "after rc=$?"
set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; done || echo "or-list"; echo "after rc=$?"
set -eo pipefail; for s in A B; do [[ $s == A ]] && echo "first sample"; done; echo "pipeline goes on"
set -e; for ((i = 0; i < 3; i++)); do (( i % 2 == 0 )) && echo "even $i"; (( i == 0 )) && echo zero; done; echo "after rc=$?"
set -e; select_first() { for x in "$@"; do [[ -f $x ]] && { echo "$x"; return 0; }; done; return 1; }; select_first nosuch a.txt b.txt; echo "after rc=$?"
set -e; n=0; for x in 1 2 3; do (( x > 1 )) && n=$((n + 1)); done; echo "n=$n"; for x in 3 2 1; do (( x > 1 )) && n=$((n + 1)); done; echo "n=$n"
set -e; arr=(5 3 9 1); max=0; for v in "${arr[@]}"; do (( v > max )) && max=$v; done; echo "max=$max"
set -e; for f in *.txt; do [[ -s $f ]] || echo "$f is empty"; [[ $f == a* ]] && echo "$f starts with a"; done; echo done
### errtrap_lineno
exec 2>&1
trap 'echo "error at line $LINENO: status $?"' ERR
echo a
false
echo b
ls nosuch-file
echo c
f() {
  echo in-f
  false
}
f
echo "f status $?"
(exit 3)
echo d
### end
### errtrap_bashcommand
exec 2>&1
set -eE
trap 'echo "Error on line $LINENO: command \"$BASH_COMMAND\" failed with status $?" >&2' ERR
echo start
cp nosuch-source nosuch-dest
echo "not reached"
### end
### exittrap_lineno
exec 2>&1
set -e
trap 'echo "exit trap: rc=$? line=$LINENO"' EXIT
echo start
grep -q zzz a.txt
echo "not reached"
### end
### errtrap_function
exec 2>&1
set -euo pipefail
on_error() { local rc=$? line=$1; echo "FAILED at line $line (exit $rc)"; exit "$rc"; }
trap 'on_error $LINENO' ERR
echo one
cat nosuch.bam > /dev/null 2>&1
echo "not reached"
### end
### errtrap_pipeline
exec 2>&1
set -o pipefail
trap 'echo "ERR: ${PIPESTATUS[*]} line $LINENO"' ERR
true | false | true
echo next
false | true
echo "last $?"
if false; then :; fi
false || echo "or"
! true
echo end
### end
### exit_trap_status
trap 'echo "bye $?"' EXIT
echo hi
exit 7
### end
### exit_trap_in_function
cleanup() { echo "cleanup called with rc=$?"; }
trap cleanup EXIT
f() { echo "in f"; exit 4; }
f
echo "not reached"
### end
### trap_reset
trap 'echo first' EXIT
trap 'echo second' EXIT
trap -p EXIT
trap - EXIT
trap -p EXIT
echo "end"
### end
### trap_exit_subshell
trap 'echo "outer exit"' EXIT
( trap 'echo "inner exit"' EXIT; echo "in subshell" )
( echo "subshell without trap" )
x=$(trap 'echo "cs exit"' EXIT; echo "in cs")
echo "$x"
echo end
### end
### find_delete_empty
mkdir -p e/a/b/c e/x/y e/keep; touch e/keep/file e/x/empty.txt
find e -type d -empty | sort
find e -type d -empty -delete; echo "rc=$?"
find e | sort
### end
### find_delete_empty2
mkdir -p e/a/b/c e/x/y; touch e/x/y/zero
find e -empty -delete; echo "rc=$?"
ls -d e 2>&1
### end
### find_delete_depth
mkdir -p e/a/b/c e/x/y; touch e/x/y/f
find e -depth -type d -empty -delete; echo "rc=$?"
find e | sort
find e -depth | head -n 3
find e -delete -print 2>&1 | sort; ls -d e 2>&1
### end
### find_delete_order
mkdir -p t/sub; touch t/f1 t/sub/f2
find t -print -delete | tr '\n' ' '; echo; ls -d t 2>&1
mkdir -p t/sub; touch t/f1 t/sub/f2
find t -name 'f*' -delete -print | sort | tr '\n' ' '; echo; find t | sort | tr '\n' ' '; echo
find t -type d -delete 2>&1 | sed 's/^find: //'; echo "rc=$?"
mkdir -p u/v; find u -maxdepth 0 -delete 2>&1 | sed 's/^find: //'; find u/v -delete; ls u | wc -l
### end
### declare_f
count_reads() { local f=$1; echo $(( $(wc -l < "$f") / 4 )); }
g() {
  if [[ $1 == x ]]; then
    echo yes
  fi
}
declare -f count_reads
declare -f g
type g
declare -F | grep -c 'declare -f'
declare -F g; declare -F nosuch; echo "rc=$?"
typeset -f g | wc -l
### end
### xtrace_simple
exec 2>&1
set -x
n=$(wc -l < a.txt)
echo "$n lines"
x=5; y=$((x * 2))
[[ $n -gt 2 ]] && echo big
[ "$x" -eq 5 ] && echo five
for i in 1 2; do echo "i=$i"; done
ls a.txt nosuch > /dev/null 2>&1 || echo "ls failed"
head -n 1 a.txt
echo 'single "quoted"' "two words" plain
v="a b"; echo $v "$v"
set +x
echo off
### end
### xtrace_bash_x
printf 'x=1\necho "x is $x"\nif [ $x -eq 1 ]; then echo one; fi\n' > t.sh
bash -x t.sh 2>&1
bash -xc 'a=(1 2); echo "${a[@]}"; (( 1 + 1 )); f() { echo hi; }; f arg' 2>&1
### end
### source_missing
exec 2>&1
source nosuch.sh; echo "rc=$?"
. ./nosuch2.sh; echo "rc=$?"
source d1; echo "rc=$?"
source; echo "rc=$?"
echo end
printf "%'d\n" 1234567; printf "%'.2f\n" 1234567.891; printf "%'10d|\n" 1000
### end
''')

more('exit-trap-and-errexit', r'''
### exittrap_rc_exit
trap 'rc=$?; echo "cleanup rc=$rc"; exit $rc' EXIT
echo work
exit 3
### end
### exittrap_rc_exit_fn
cleanup() { local rc=$?; rm -f tmp.$$; echo "cleanup: $rc"; exit "$rc"; }
trap cleanup EXIT
touch tmp.$$
[[ -f a.txt ]] || exit 1
grep -q zzz a.txt || exit 5
echo "not reached"
### end
### exittrap_rc_last
trap 'echo "rc=$?"' EXIT
echo work
false
### end
### exittrap_rc_sete
set -e
trap 'echo "rc=$?"' EXIT
echo work
ls nosuch 2> /dev/null
echo "not reached"
### end
### exittrap_rc_plain_exit
trap 'echo "rc=$?"' EXIT
false
exit
### end
### exittrap_rc_exit0
trap 'echo "rc=$?"' EXIT
false
exit 0
### end
### exittrap_no_exit_in_trap
trap 'echo "trap rc=$?"; true' EXIT
exit 9
### end
### exittrap_changes_status
trap 'exit 0' EXIT
exit 9
### end
### exittrap_die
die() { echo "FATAL: $*" >&2; exit 2; }
trap 'st=$?; if [ $st -ne 0 ]; then echo "pipeline failed with status $st"; else echo "pipeline ok"; fi' EXIT
[[ -f nosuch.bam ]] || die "no bam"
### end
### exittrap_ok
trap 'st=$?; if [ $st -ne 0 ]; then echo "pipeline failed with status $st"; else echo "pipeline ok"; fi' EXIT
echo fine
### end
### sete_redirect_compound
set -e
{ echo x; } > /nosuchdir/f
echo "after rc=$?"
### end
### sete_redirect_loop
set -e
for i in 1 2; do echo $i; done > /nosuchdir/f
echo "after rc=$?"
### end
### sete_bashc
bash -c 'set -e; for n in 1 2; do [[ $n == 1 ]] && echo one; done; echo "after rc=$?"'; echo "outer rc=$?"
bash -ec 'for f in a.txt nosuch; do [ -f $f ] && echo "found $f"; done; echo "after"'; echo "outer rc=$?"
bash -c 'set -e; if true; then false && echo x; fi; echo after'; echo "outer rc=$?"
### end
### sete_fn_loop_cond
set -e
has() { for x in "$@"; do [[ $x == b ]] && return 0; done; return 1; }
if has a b c; then echo yes; fi
has a c || echo "no b"
check_all() { for f in "$@"; do [[ -f $f ]] && echo "ok $f"; done; }
check_all a.txt nosuch || echo "check_all returned $?"
echo "before"
check_all a.txt nosuch
echo "not reached in bash"
### end
### sete_last_in_script
set -e
for f in a.txt nosuch; do [[ -f $f ]] && echo "ok $f"; done
### end
### sete_nested_if_loop
set -euo pipefail
for s in A B; do
  if [[ $s == A ]]; then
    for k in 1 2; do
      [[ $k == 1 ]] && echo "$s$k"
    done
  fi
  echo "sample $s done"
done
echo "all done"
### end
### sete_while_counter
set -e
n=0
while [ $n -lt 3 ]; do
  n=$((n + 1))
  [ $((n % 2)) -eq 1 ] && echo "odd $n"
done
echo "n=$n"
i=0
while true; do
  i=$((i + 1))
  [ $i -ge 2 ] && break
done
echo "i=$i"
for x in 1 2 3; do
  [ $x -eq 2 ] && continue
  echo "x=$x"
done
echo end
### end
### sete_errtrap_loop
set -eE
trap 'echo "ERR at $LINENO"' ERR
for n in 1 2; do [[ $n == 1 ]] && echo one; done
echo "after"
### end
### sete_arith_let
set -e
i=0
((i++)) || true
echo "i=$i"
let j=0 || true
echo "j=$j"
k=0
(( k += 1 ))
echo "k=$k"
(( k -= 1 ))
echo "not reached: k=$k"
### end
### sete_arith_incr0
set -e
count=0
((count++))
echo "not reached in bash: $count"
### end
### sete_local_cmdsub
set -e
f() { local v=$(false); echo "local hides the failure: rc=$?"; }
f
g() { local v; v=$(false); echo "not reached"; }
g
echo "not reached either"
### end
### sete_cmdsub_assign
set -e
x=$(echo hi; false)
echo "not reached x=$x"
### end
### sete_export_cmdsub
set -e
export V=$(false)
echo "export hides it: rc=$? V=[$V]"
readonly W=$(false)
echo "readonly hides it"
declare Z=$(false)
echo "declare hides it"
Y=$(false) true
echo "prefix: goes on"
Q=$(false)
echo "not reached"
### end
### sete_negation
set -e
! false
echo "a"
! true
echo "b: rc=$?"
if ! grep -q zzz a.txt; then echo "no zzz"; fi
! grep -q alpha a.txt || echo "has alpha"
echo c
### end
### sete_subshell
set -e
(false; echo "inner not reached")
echo "not reached"
### end
### sete_subshell_or
set -e
(false; echo "inner reached: -e ignored in ||") || echo "or"
echo "next"
(set -e; false; echo "x") && echo "and" || echo "failed"
echo "end"
### end
### sete_pipeline_mid
set -e
false | true
echo "one: ${PIPESTATUS[*]}"
set -o pipefail
false | true
echo "not reached"
### end
### sete_cond_function
set -e
f() { false; echo "f goes on in a condition"; }
if f; then echo "f true"; fi
f || echo no
f && echo "f and"
echo "now alone"
f
echo "not reached"
### end
### sete_eval_source
set -e
eval 'false' || echo "eval false caught"
eval 'true; false; echo no' && echo y || echo "eval list"
printf 'echo in-src\nfalse\necho "src not reached"\n' > src.sh
source src.sh
echo "not reached"
### end
### sete_plus_e_region
set -e
set +e
false
echo "in +e region: $?"
grep -q zzz a.txt
rc=$?
set -e
echo "rc=$rc"
[ $rc -eq 0 ] || echo "handled"
false
echo "not reached"
### end
### sete_and_or_last
set -e
true && false
echo "not reached"
### end
### sete_or_true
set -e
false || true
false && true
echo "reached: rc=$?"
true && false || echo "handled"
f() { [[ -n ${1:-} ]] && echo "arg $1"; }
f x
f || echo "f without arg: $?"
f
echo "not reached"
### end
''')

more('errexit-in-conditions', r'''
set -e; f() { [[ -s nosuch ]]; }; f || echo "missing"; echo "after"
set -e; f() { grep -q zzz a.txt; }; f || echo "no zzz"; echo "after"
set -e; f() { false; }; f || echo "f failed: $?"; echo "after"
set -e; f() { false; echo "f goes on"; }; f || echo "f failed: $?"; echo "after"
set -e; f() { false; echo "f goes on"; }; f && echo "f ok"; echo "after"
set -e; f() { false; echo "f goes on"; }; if f; then echo "f ok"; fi; echo "after"
set -e; f() { false; echo "f goes on"; }; if ! f; then echo "f failed"; fi; echo "after"
set -e; f() { false; echo "f goes on"; }; ! f; echo "after rc=$?"
set -e; f() { false; echo "f goes on"; }; while f; do echo "in loop"; break; done; echo "after"
set -e; f() { false; echo "f goes on"; }; until f; do echo "in loop"; break; done; echo "after"
set -e; f() { false; echo "f goes on"; }; f || true; echo "after"
set -e; f() { ls nosuch 2> /dev/null; echo "f goes on"; }; x=$(f) || echo "caught"; echo "x=$x"
set -e; f() { false; echo "f goes on"; }; g() { f; echo "g goes on"; }; g || echo "g failed"; echo "after"
set -e; { false; echo "group goes on"; } || echo "group failed"; echo "after"
set -e; ( false; echo "subshell goes on" ) || echo "subshell failed"; echo "after"
set -e; eval 'false; echo "eval goes on"' || echo "eval failed"; echo "after"
set -e; bash -c 'false; echo "child goes on"' || echo "child failed"; echo "after"
set -e; if { false; echo "group in if"; }; then echo yes; fi; echo "after"
set -e; if ( false; echo "subshell in if" ); then echo yes; fi; echo "after"
set -e; if eval 'false; echo "eval in if"'; then echo yes; fi; echo "after"
set -e; for i in 1; do false; echo "loop goes on"; done || echo "loop failed"; echo "after"
set -e; f() { for i in 1 2; do false; echo "i=$i"; done; }; f || echo "f failed"; echo "after"
set -e; f() { if false; then :; fi; cat nosuch 2> /dev/null; echo "f goes on"; }; f || echo "f failed"; echo "after"
set -e; run() { "$@"; echo "ran $1"; }; run false || echo "run failed"; run true; echo "after"
set -e; step() { echo "step $1"; [[ $1 != 2 ]]; }; step 1 && step 2 && step 3 || echo "a step failed"; echo "after"
set -e; try() { "$@" || return $?; }; try false || echo "try: $?"; try true; echo "after"
set -e; f() { false; return 0; }; f || echo "f failed"; echo "after f"; f; echo "not reached"
set -e; f() { cat nosuch.txt > /dev/null 2>&1; echo "then this"; }; out=$(f || echo "handler"); echo "out=$out"
set -e; f() { false; echo "f goes on"; }; f | cat; echo "after rc=$?"
set -e; f() { false; echo "f goes on"; }; f | cat || echo "pipe failed"; echo "after"
set -e; f() { return 3; }; f || echo "returned $?"; echo "after"
set -e; f() { (exit 3); echo "f goes on $?"; }; f || echo "f failed"; echo "after"
set -e; source /dev/stdin <<< 'false; echo "sourced goes on"' || echo "source failed"; echo "after"
set -e; printf 'false\necho "sourced goes on"\n' > inc.sh; . ./inc.sh || echo "source failed"; echo "after"
set -e; printf 'false\necho "sourced goes on"\n' > inc.sh; if . ./inc.sh; then echo "yes"; fi; echo "after"
set -e; trap 'echo "ERR trap"' ERR; f() { false; echo "f goes on"; }; f || echo "f failed"; echo "after"
set -e; f() { false; echo "f goes on"; }; f || echo "f failed"; f; echo "not reached"
set -e; f() { set +e; false; echo "f with +e"; set -e; }; f; echo "after"
''')

more('regex-patterns-namerefs', r'''
[[ axb =~ ^a\.b$ ]] && echo wrong1 || echo right1; [[ a.b =~ ^a\.b$ ]] && echo right2 || echo wrong2; [[ 3x14 =~ ^[0-9]+\.[0-9]+$ ]] && echo wrong3 || echo right3; [[ 3.14 =~ ^[0-9]+\.[0-9]+$ ]] && echo right4 || echo wrong4
[[ readsXfq =~ \.fq$ ]] && echo wrong1 || echo right1; [[ reads.fq =~ \.fq$ ]] && echo right2 || echo wrong2; f=sample.fastq.gz; [[ $f =~ \.fastq\.gz$ ]] && echo right3; f=sampleXfastqXgz; [[ $f =~ \.fastq\.gz$ ]] && echo wrong4 || echo right4
re='^a\.b$'; [[ axb =~ $re ]] && echo wrong1 || echo right1; [[ a.b =~ $re ]] && echo right2 || echo wrong2; re2='\.fq$'; [[ readsXfq =~ $re2 ]] && echo wrong3 || echo right3; re3='^[0-9]+\.[0-9]+$'; [[ 3x14 =~ $re3 ]] && echo wrong4 || echo right4
[[ axb =~ "a.b" ]] && echo wrong1 || echo right1; [[ a.b =~ "a.b" ]] && echo right2 || echo wrong2; [[ axb =~ a"."b ]] && echo wrong3 || echo right3; [[ 'a+b' =~ "a+b" ]] && echo right4 || echo wrong4; [[ aab =~ "a+b" ]] && echo wrong5 || echo right5; p='a.b'; [[ axb =~ "$p" ]] && echo wrong6 || echo right6; [[ axb =~ $p ]] && echo right7 || echo wrong7
[[ aXb =~ a[[:upper:]]b ]] && echo right1 || echo wrong1; [[ 123 =~ ^[[:digit:]]+$ ]] && echo right2 || echo wrong2; [[ "a b" =~ [[:space:]] ]] && echo right3 || echo wrong3; [[ abc =~ ^[[:alpha:]]+$ ]] && echo right4 || echo wrong4; [[ ab1 =~ ^[[:alnum:]]+$ ]] && echo right5 || echo wrong5; [[ abc =~ ^[[:lower:]]+$ ]] && echo right6 || echo wrong6; [[ "a,b" =~ [[:punct:]] ]] && echo right7 || echo wrong7; [[ abc =~ [[:digit:]] ]] && echo wrong8 || echo right8
re='^[[:digit:]]+$'; [[ 123 =~ $re ]] && echo right1 || echo wrong1; [[ 12a =~ $re ]] && echo wrong2 || echo right2; re='^[[:space:]]*$'; [[ "   " =~ $re ]] && echo right3 || echo wrong3; re='^[[:alpha:]_][[:alnum:]_]*$'; [[ var_1 =~ $re ]] && echo right4 || echo wrong4; [[ 1var =~ $re ]] && echo wrong5 || echo right5; [[ "x y" =~ ^x[[:blank:]]y$ ]] && echo right6 || echo wrong6; [[ ACGT =~ ^[ACGT[:space:]]+$ ]] && echo right7 || echo wrong7
[[ a+b =~ a\+b ]] && echo right1 || echo wrong1; [[ aab =~ ^a\+b$ ]] && echo wrong2 || echo right2; [[ 'a*b' =~ a\*b ]] && echo right3 || echo wrong3; [[ '(x)' =~ \(x\) ]] && echo right4 || echo wrong4; [[ 'a|b' =~ a\|b ]] && echo right5 || echo wrong5; [[ ab =~ ^a\|b$ ]] && echo wrong6 || echo right6; [[ 'a?' =~ a\?$ ]] && echo right7 || echo wrong7; [[ '$5' =~ ^\$[0-9]$ ]] && echo right8 || echo wrong8; [[ 'a\b' =~ a\\b ]] && echo right9 || echo wrong9; [[ '[x]' =~ \[x\] ]] && echo right10 || echo wrong10; [[ x =~ ^\[x\]$ ]] && echo wrong11 || echo right11; [[ 'a{2}' =~ a\{2\} ]] && echo right12 || echo wrong12
[[ chr1:100 =~ ^chr[0-9XY]+:[0-9]+$ ]] && echo right1; [[ "NA12878_R1.fastq" =~ ^(.*)_R[12]\.fastq$ ]] && echo "${BASH_REMATCH[1]}"; [[ "NA12878_R1Xfastq" =~ ^(.*)_R[12]\.fastq$ ]] && echo wrong3 || echo right3; v=1.17; [[ $v =~ ^([0-9]+)\.([0-9]+)$ ]] && echo "${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"; [[ 117 =~ ^([0-9]+)\.([0-9]+)$ ]] && echo "wrong5 ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}" || echo right5; [[ "0/1" =~ ^[01][/|][01]$ ]] && echo right6; [[ "x@y.org" =~ ^[^@]+@[^@]+\.[a-z]+$ ]] && echo right7; [[ "x@yorg" =~ ^[^@]+@[^@]+\.[a-z]+$ ]] && echo wrong8 || echo right8
[[ abc =~ z ]]; echo "rc=$? [${BASH_REMATCH[0]}] ${#BASH_REMATCH[@]}"; [[ abc =~ (a)(x)? ]]; echo "${#BASH_REMATCH[@]} [${BASH_REMATCH[1]}] [${BASH_REMATCH[2]}]"; [[ abc =~ ^(a|b)+ ]]; echo "${BASH_REMATCH[0]} ${BASH_REMATCH[1]}"; [[ AbC =~ ^abc$ ]] && echo wrong || echo right; shopt -s nocasematch; [[ AbC =~ ^abc$ ]] && echo right-nocase; shopt -u nocasematch; [[ "a  b" =~ a\ +b ]] && echo right-space; [[ $'a\tb' =~ a[[:space:]]b ]] && echo right-tab; [[ abc =~ ^.{3}$ ]] && echo right-brace; [[ ab =~ ^(ab|cd)$ ]] && echo right-alt; [[ é =~ ^[[:alpha:]]$ ]] && echo alpha-utf8
s="a/b/c"; echo "${s////|}" "${s///|}" "${s//\//|}" "${s/\//|}" "${s//\//}" "${s///}" "${s////}"; p=/data/run/x.fq; echo "${p////_}" "${p//\//_}" "${p#/}" "${p////-}"; t=a.b.c; echo "${t//./\/}" "${t//.//}" "${t/./ }" "${t//./}"; u="x y z"; echo "${u// /_}" "${u// /}" "${u/ /\ \ }" "${u//[xz]/Q}"
x=3; echo $(( "$x" + 1 )) $(( "3" + 1 )) $(( '3' * 2 )) $(( "$x" > 2 )); (( "$x" > 2 )) && echo yes; (( "$x" == 3 )) && echo three; y="5"; echo $(( "$y" * "$x" )) $(( $x + "2" )); if (( "$x" < "$y" )); then echo less; fi; echo "$(( "$x" + 1 ))"; z=$(( "${x}" * 2 )); echo $z
t="hello world"; echo "${t~}" "${t~~}"; echo "${t@U}"; echo "${t@u}"; echo "${t@L}"; echo "${t@Q}"; x="a b"; echo "${x@A}"; echo "${x@E}"; echo "${x@P}"; arr=(a b); echo "${arr[@]@Q}"; echo "${arr@a}"; echo "${x@a}|"; declare -i n=5; echo "${n@a}"; echo "${t^^[lo]}"; echo "${t//[lo]/X}"; echo "${t^h}" "${t^x}"; T=ABC; echo "${T,,[AB]}" "${T,A}"
f() { local -n r=$1; r="set by nameref"; }; f target; echo "$target"; g() { local -n out=$1; out=(1 2 3); }; g res; echo "${res[*]} ${#res[@]}"; declare -n alias=target; echo "$alias"; alias=changed; echo "$target"; echo "${!alias}"; h() { local -n m=$1; m[k]=v; }; declare -A map; h map; echo "${map[k]}"; k() { local -n arr=$1; echo "${#arr[@]} ${arr[1]}"; }; a=(x y z); k a; unset -n alias; echo "[${alias:-unset}] $target"; sum() { local -n total=$1; shift; total=0; for v in "$@"; do (( total += v )); done; }; sum result 1 2 3; echo "$result"
arr=(x y z); ref='arr[1]'; echo "${!ref}"; ref2='arr[@]'; echo "${!ref2}"; n=arr; r3="$n[2]"; echo "${!r3}"; v=one; name=v; echo "${!name}"; echo "${!name^^}" "${!name:0:1}" "${!name:-d}" "${#name}"; unset w; nm=w; echo "[${!nm}]" "[${!nm:-default}]"
for i in 1; do break 5; done; echo "after break 5"; for i in 1 2; do for j in 1 2; do break 3; done; echo no; done; echo "after break 3"; for i in 1 2; do continue 4; echo no; done; echo "after continue 4"; while true; do break 2; done; echo "after while break 2"
find d1 -name x.txt -execdir ls {} \;; find d1 -name x.txt -execdir pwd \; | sed 's|.*/||'; find d1 -name z.txt -execdir sh -c 'echo "in $(basename "$PWD"): $1"' _ {} \;; find d1 -type f -execdir echo {} + | tr ' ' '\n' | sort | tr '\n' ' '; echo; find d1 -name 'x.txt' -execdir cp {} {}.bak \;; ls d1; ls *.bak 2>&1 | wc -l
touch -d '2020-05-05 05:05:05' a.txt; cp -p a.txt p1.txt; stat -c %y p1.txt | cut -c1-19; cp -a a.txt p2.txt; stat -c %y p2.txt | cut -c1-19; cp --preserve a.txt p3.txt 2>&1; stat -c %y p3.txt 2>&1 | cut -c1-19; mkdir pd; touch -d '2021-06-06 06:06:06' pd/f; cp -rp pd pd2; stat -c %y pd2/f | cut -c1-19; cp -a pd pd3; stat -c %y pd3/f | cut -c1-19; mv a.txt moved.txt; stat -c %y moved.txt | cut -c1-19; cp a.txt 2> /dev/null; cp moved.txt plain.txt; stat -c %y plain.txt | cut -c1-4 | grep -c 2020
x=$(case abc in a*) echo "case in sub" ;; esac); echo "$x"
x=$(case abc in (a*) echo "case with parens in sub" ;; esac); echo "$x"
kind=$(case "reads.fq.gz" in *.gz) echo gz ;; *) echo plain ;; esac); echo "$kind"; echo "$(for i in 1 2; do case $i in 1) echo one ;; esac; done)"; n=$(echo 5 | while read v; do case $v in 5) echo five ;; esac; done); echo $n
f() { case $1 in a) echo A ;; *) echo other ;; esac; }; y=$(f a); echo "$y"; z=`case x in x) echo back ;; esac`; echo "$z"; echo $(if true; then case q in q) echo nested ;; esac; fi)
''')

more('printf-numbers-and-text', r'''
printf '%d\n' 99999999999999999999; echo "rc=$?"; printf '%d\n' -99999999999999999999; echo "rc=$?"; printf '%d\n' 9223372036854775807 9223372036854775808 -9223372036854775808; echo "rc=$?"
printf '%u\n' -1 18446744073709551615 18446744073709551616; echo "rc=$?"; printf '%x %X %o\n' -1 -1 -1; printf '%x %o\n' -255 -8; printf '%d\n' 0x7fffffffffffffff 0xffffffffffffffff; echo "rc=$?"
printf '%x %x %x\n' 255 0x10 010; printf '%#x %#o %#X|%#x|%#o\n' 255 8 255 0 0; printf '%5d|%-5d|%05d|%+d|% d|%+d|% d\n' 42 42 42 42 42 -42 -42; printf '%.3d|%8.3d|%-8.3d|%08.3d|%+.3d\n' 5 5 5 5 5
printf "%'d %'.2f %'s|\n" 1234567 1234567.891 txt; printf "%'10d|%-'10d|%'010d\n" 1234567 1234567 1234567
printf '%c|%5c|%-5c|\n' abc x y; printf '%c' ''; echo "|"; printf '%c\n' é | od -An -c; printf '%5c|\n' é | od -An -c
printf '%5s|%-5s|%.2s|%.1s|\n' é 你好 éè é | od -An -c; printf '%-8s|%8s|\n' naïve café; printf '%.3s|\n' 你好
printf '%q\n' 'x#' '#x' 'a#b' '~x' 'x~' 'a=b' 'a:b' 'a%b' 'a+b' 'a@b' 'a,b' 'a.b' 'a/b' '-x' 'a{b' 'a}b' 'a]b' 'é' 'a^b' 'a!b' '%' '=' '~' '#' '~/x' 'a~b' '{' '}' '{a,b}' '[' ']' 'a b' '*' '?' "it's" 'a"b' '$x' '`x`' 'a\b' 'a|b' 'a&b' 'a;b' 'a<b' 'a>b' '(x)'
printf '%q\n' $'tab\there' $'nl\nx' $'cr\rx' $'esc\ex' $'bel\ax' $'a\001b' $'del\177x' $'q\x27t' 'é è' $'é\tè' '' ' ' '  '
printf -v 1bad x; echo "rc=$?"; printf -v 'a b' x; echo "rc=$?"; printf -v; echo "rc=$?"; printf -v x; echo "rc=$?"; printf -v ok '%d' 5; echo "rc=$? $ok"; printf -v 'arr[3]' y; echo "${arr[3]} rc=$?"
printf '%d\n' '' ' 5' '5 ' ' 5 ' '+5' '--5' 5x 0x 08 1e3 '0x1g' '- 5'; echo "rc=$?"
printf '%i|%5.2s|%-6sx\n' 3 abc ab; printf '%ld %lld %hd %zu %jd %Lf %qd\n' 1 2 3 4 5 6 7; echo "rc=$?"
printf '%z\n' 1; echo "rc=$?"; printf '%'; echo "rc=$?"; printf 'abc%'; echo "rc=$?"; printf '%5'; echo "rc=$?"; printf '%y %d\n' 1 2; echo "rc=$?"
printf '%*d|%-*d|%*d|\n' 5 42 5 42 -5 42; printf '%.*f|%*.*f|\n' 2 3.14159 8 3 2.71828; printf '%*s|%.*s|\n' 6 ab 2 abcdef; printf '%*d\n' x 5; echo "rc=$?"
printf '%b\n' 'a\tb\0101\x41é' 'x\c ignored' 'never'; echo "|"; printf '%b|' '\101' '\0101' '\1' '\01' '\001' '\0001' '\8' '\q' '\\' '\"' "\\'"; echo; printf '%5b|%-5b|\n' 'a\n' 'b'
printf '\101\x41é\U0001F600\n'; printf '\e[0m\033[1m' | od -An -c; printf 'a\cb'; echo "|"; printf '\8\q\z\n'; printf '\x\n' | od -An -c; printf '\0\00\000\0000' | od -An -c; printf '\1011\n'; printf "\'\"\?\n"
printf '%s\n'; printf '%d\n'; printf '%s %s\n' a b c; printf '%s\n' a b; printf 'no args\n' x y; echo "rc=$?"; printf '%s %d %s\n' a; printf; echo "rc=$?"; printf -- '-x\n'; printf -- '%s\n' --; printf '%s\n' -- x
printf '%5.1f|%-8.2e|%G|%g|%g|%g|%g\n' 3.14159 31415.9 0.00001234 100000 1000000 0.0001 0.00001; printf '%e %E\n' 0 12345.678; printf '%.0e %#.0e %#.0f %#g\n' 5 5 5 5
printf '%f\n' abc; echo "rc=$?"; printf '%d\n' 3.7; echo "rc=$?"; printf '%.0f %.0f %.0f %.0f %.0f\n' 0.5 1.5 2.5 3.5 -0.5; printf '%f %f %f %F\n' inf nan -inf inf; printf '%f\n' 1e400 1e-400; echo "rc=$?"
printf '%.2f %.2f %.2f %.2f %.3f\n' 2.675 1.005 0.125 0.375 1.0005; printf '%.20f\n' 0.1; printf '%.15g %.17g\n' 0.1 0.1; printf '%10.4f|%-10.4f|%+.2f|% .2f|%010.3f\n' 3.14159 3.14159 2 2 -1.5
printf '%f %g %e\n' 0x10 0x1p4 010; printf '%d %d\n' "'A" '"é'; printf '%d\n' "'"; printf '%f\n' "'A"; printf '%x\n' "'é"; printf '%c%c\n' 65 '\101'
printf '%(%Y-%m-%d)T\n' 0; printf '%(%H:%M)T|%10(%Y)T|%-10(%Y)T|\n' 0 0 0; printf '%(%s)T\n' 86400; printf '%()T\n' 0 | wc -c; printf '%(%Y)T\n' -1 | grep -c '^20'; printf '%(%Y)T\n' | grep -c '^20'
printf '%s\n' "${var-unset}" "$(printf '%s' 'a b')"; printf '%s=%s\n' k1 v1 k2 v2 k3; printf '[%s]' ; echo; printf '[%s][%s]' a; echo; printf '%s' ; echo "|"; printf '%%|%5%|%-5%|\n'
printf 'a\0b' | od -An -c; printf '%s\0' x y | od -An -c; printf '%b' 'a\0b' | od -An -c; printf '%s' $'a\nb' | od -An -c; v=$(printf 'a\0b'); echo "${#v}"; printf '%q\n' "$(printf 'a\tb')"
printf '%d %s\n' 1 one 2 two 3; printf '%3d: %s\n' 1 "a b" 22 c; printf "%-10s|%10s|\n" left right; printf '%05.1f|%5s|%-5d|%5x\n' 3.14159 ab 7 255; printf '%+5d|%+5s|% 5d|%05s|\n' 3 ab 3 ab
''')

more('printf-more', r'''
printf '%f|%e|%g\n' 0 0 0; printf '%f|%e|%g\n' -0 -0 -0; printf '%.3f|%.3e|%.3g\n' 1234.5678 1234.5678 1234.5678; printf '%g|%g|%g|%g|%g\n' 123456 1234567 0.0001234 0.00001234 1e21
printf '%#g|%#.3g|%#f|%#e|%#.0f|%#.0e\n' 1 1 1 1 1 1; printf '%a|%A|%.2a|%a|%a\n' 1 0.1 0.1 0 -2.5; printf '%.0a|%.1a|%10.3a|%a\n' 1.5 255 0.3 1e100
printf '%f %f %f\n' inf -inf nan; printf '%F %E %G\n' inf nan inf; printf '%5f|%-5f|%05f|%+f|% f\n' inf inf inf inf inf; printf '%f\n' -nan infinity INFINITY NaN iNf
printf '%f\n' 1e400 | cut -c1-60; printf '%e\n' 1e400 1e-400 1e4000 1e-4000; printf '%g\n' 1e5000; echo rc=$?; printf '%g\n' 1e-5000; echo rc=$?
printf '%.25f\n' 0.1; printf '%.30e\n' 0.1; printf '%.40g\n' 0.1; printf '%.19g|%.20g|%.21g\n' 0.1 0.1 0.1; printf '%.18f|%.19f|%.20f|%.21f\n' 0.3 0.3 0.3 0.3
printf '%f|%f|%f\n' ' 1.5' '1.5 ' '+1.5'; echo rc=$?; printf '%f|%g\n' 1.5e 1.5e+; echo rc=$?; printf '%f\n' .5 5. . e5 ''; echo rc=$?
printf '%5.3d|%-5.3d|%05.3d|%+5.3d|%.0d|%.0d|%5.0d|\n' 7 7 7 7 0 1 0; printf '%x|%X|%#x|%#X|%08x|%-8x|%+x|% x|%.4x|%#.4x|%#010x\n' 255 255 255 255 255 255 255 255 255 255 255
printf '%o|%#o|%05o|%.4o|%#.4o|%#o\n' 8 8 8 8 8 0; printf '%u|%5u|%-5u|%05u|%+u|% u|%.3u\n' 42 42 42 42 42 42 42
printf '%n\n' v; echo "$v"; printf 'abc%n def%n\n' v1 v2; echo "$v1 $v2"; printf '%n' 1bad; echo rc=$?
printf '%Q\n' 'a b' ; printf '%.3Q|\n' 'a b c d'; printf '%10q|%-10q|%.2q|\n' 'a b' 'a b' 'a b'; printf '%s\n' -5; printf '%d\n' -5; printf '%5s|%5d|\n' -5 -5
printf -x; echo rc=$?; printf "-----\n"; echo rc=$?; printf "- item\n"; echo rc=$?; printf -; echo " rc=$?"; printf -- ; echo rc=$?; printf -vx '%s' glued; echo "$x"; printf -v x -- '%s' y; echo "rc=$? $x"
printf '%s %s\n' "$(printf '\x00')" x | od -An -c; printf -v z 'a\0b'; echo "${#z}"; printf '%s' "$z" | od -An -c
printf '%-5c|%05c|%.0c|\n' a b c | od -An -c; printf '%c%c%c\n' '' x '' | od -An -c
printf '%*d|\n'; printf '%.*d|\n'; printf '%*.*f|\n' 8; printf '%*s|%s\n' 3; echo rc=$?
printf '%s %(%Y)T %s\n' a 0 b; printf '%(%Y %% %n %t)T|\n' 0 | od -An -c | head -n 2; printf '%(bad\n' 0; echo rc=$?; printf '%(%Y)x\n' 0; echo rc=$?; printf '%.2(%Y)T|%8.2(%Y)T|\n' 0 0
printf '%b' 'a\x' | od -An -c; printf '%b' '\u' | od -An -c; printf '\u\n'; printf '\U\n'; printf '\uzz\n'; printf '%b\n' '😀' '€' '\U1F600' '\u41'
printf '%b' '\0' '\00' '\000' '\0000' '\00000' | od -An -c; printf '%b' '\400' '\777' '\0400' | od -An -c; printf '\400\777' | od -An -c
printf '%d %d %d\n' "'" '"' "'ab"; printf '%d\n' "'€" "'😀"; printf '%d\n' \'A; printf '%u %o %x\n' "'A" "'A" "'A"; printf '%e\n' "'A"
printf '%5%|%-5%|%%|\n'; echo rc=$?; printf '%%%s%%\n' x; printf '100%%\n'; printf '%d%%\n' 50
printf 'abc\ndef' | od -An -c | tail -n 1; printf '%s\n' 'a\nb'; printf 'a\\nb\n'; printf 'tab\there\n'; printf "dq \$x \\\\ \n"
printf '%d\n' 08; echo "rc=$?"; printf '%d\n' 0x1g; echo "rc=$?"; printf '%d\n' 0x; echo "rc=$?"; printf '%d\n' 09.5 +08 ' 08'; echo "rc=$?"; printf '%f\n' 08 0x1g; echo "rc=$?"
printf '%s|' a b c; echo; printf '%s|%s|\n' a b c; printf '%d|' 1 2 x 4; echo " rc=$?"; printf '%s\n' a b | wc -l; printf '\n' a b c | wc -l; printf 'x' a b c; echo
''')

more('substrings-and-readonly', r'''
s=abcdefghij; echo "[${s: -5}] [${s: -10}] [${s: -11}] [${s: -20}] [${s:10}] [${s:11}] [${s:20}] [${s:0:0}] [${s:0:20}] [${s:9:1}] [${s:9:5}]"
s=abcdefghij; echo "[${s:3:-3}] [${s:3:-7}] [${s: -3:-1}] [${s:0:-10}] [${s:5:-5}]"; echo "[${s:3:-8}]"; echo "rc=$?"; echo next
s=abcdefghij; echo "[${s:6:-5}]"; echo "not reached rc=$?"
s=abcdefghij; n=-10; echo "[${s:3:n}]"; echo "not reached"
s=abcdefghij; echo "[${s:0:-11}]"; echo "not reached"
set -- a b c d e; echo "[${@:2}] [${@:2:2}] [${@: -2}] [${@:0}] [${@:0:2}] [${@:6}] [${@:7}] [${@: -6}] [${@: -7}] [${*:2:1}] [${@:1:0}]"; echo "[${@:2:-1}]"; echo "not reached"
a=(p q r s t); echo "[${a[@]:1}] [${a[@]:1:2}] [${a[@]: -2}] [${a[@]:5}] [${a[@]:9}] [${a[@]: -9}] [${a[*]:3:9}] [${a[@]:0:0}]"; echo "[${a[@]:1:-1}]"; echo "not reached"
a=([2]=x [5]=y [9]=z); echo "[${a[@]:0:2}] [${a[@]:3}] [${a[@]:5:1}] [${a[@]:6}] [${a[@]: -1}] [${a[@]: -5}] [${a[@]:2:1}]"
s='héllo wörld'; echo "[${s:1:3}] [${s: -3}] [${s:6}] ${#s}"; e=; echo "[${e:0}] [${e:1}] [${e:0:1}] [${e: -1}]"; unset u; echo "[${u:0:2}] [${u:2}]"
f() { echo "[${1:1}] [${2:0:1}] [${#1}]"; }; f hello world; x=12345; echo "${x:1:${#x}-2} ${x:$((1+1))} ${x: $(( -2 ))} ${x:(-2)} ${x:1+1:1+1}"
k() { local -r c=5; c=6; echo after; } 2> /dev/null; k; echo "rc=$?"
k3() { readonly d=1; d=2; echo after3; }; k3; echo "rc=$?"; echo next
readonly r=1; r=2; echo "rc=$?"; echo same-line
readonly r=1; r=2 true; echo "rc=$?"; f() { r=3; echo in-f; }; f; echo "after f rc=$?"
readonly r=1; { r=2; echo in-group; }; echo "rc=$?"
readonly r=1; ( r=2; echo in-subshell ); echo "rc=$?"; echo "$(r=5; echo in-subst) rc=$?"; echo end
readonly r=1; for i in 1 2; do r=$i; echo loop-$i; done; echo "rc=$?"
readonly r=1; if true; then r=2; echo then; fi; echo "rc=$?"
readonly r=1; r=2 || echo "or branch"; echo "rc=$?"
readonly r=1; true && r=2; echo "rc=$?"
readonly r=1; unset r; echo "rc=$?"; declare r=5; echo "rc=$?"; export r=6; echo "rc=$?"; local r 2> /dev/null; echo "rc=$?"; read r <<< x; echo "rc=$? $r"
readonly r=1; r+=2; echo "rc=$?"
readonly r=1; (( r = 5 )); echo "rc=$? $r"; (( r++ )); echo "rc=$? $r"; echo $(( r += 1 )); echo "rc=$?"
readonly r=1; for r in 1 2; do echo $r; done; echo "rc=$? $r"
readonly -a ra=(1 2); ra[0]=9; echo "rc=$?"
readonly -a ra=(1 2); ra+=(3); echo "rc=$?"
''')

more('functions-printed', r'''
### big
count_reads() { local f=$1; echo $(( $(wc -l < "$f") / 4 )); }
g() {
  if [[ $1 == x && -f "$2" ]] || [ "$1" = y ]; then
    echo yes   # a comment
  elif (( $# > 2 )); then echo many; else
    echo no
  fi
  for f in a "b c" *.txt; do echo "$f"; done
  for ((i=0; i<3; i++)); do :; done
  while read -r line; do echo "$line"; done < "$2" | sort -u > out.txt 2>&1
  until false; do break; done
  case $1 in
    a|b) echo ab ;;
    c*) echo c ;&
    *) echo other ;;
  esac
  ( cd /tmp && ls ) || { echo failed >&2; return 1; }
  x=$(echo "a b" | tr a b) y=2 cmd arg
  arr=(1 2 "three four")
  cat <<EOF2
heredoc $x
EOF2
  cat <<'EOF3' | wc -l
quoted $x
EOF3
  ! true
  time sleep 0
  local -a la=(1 2); export V=1
  function inner { echo inner; }
  inner2() ( echo subshell-body )
  echo a; echo b && echo c
}
declare -f count_reads
declare -f g
type count_reads
declare -F
declare -f nosuch; echo "rc=$?"
h() { echo "redir"; } > /dev/null 2>&1
declare -f h
k() if true; then echo k; fi
declare -f k
### end
### small
a() { echo one; }
b() { echo one; echo two; }
c() { echo "x" | tr x y | tr y z; }
d() { [[ -f $1 ]] && echo file || echo "no file"; }
e() { for x; do echo "$x"; done; }
f() { while :; do break; done; until :; do :; done; }
gg() { if a; then b; elif c; then d; elif e; then f; else gg; fi; }
hh() { case "$1" in -h|--help) echo help;; -v) ;; *) echo x; echo y;; esac; }
ii() { ( echo sub; echo two ) > /dev/null; { echo grp; } 2>&1; }
jj() { cat > out.txt <<EOF
body line
EOF
}
kk() { cat <<-EOF
	tabbed
	EOF
  echo after
}
ll() { ((n++)); (( n > 3 )) && return; echo $n >> log.txt 2> /dev/null < /dev/null; }
mm() { local a=1 b="two words" c; a+=x; arr=(1 2 3); arr[1]=x; echo "${arr[@]}" 2>&1 >/dev/null; }
nn() { echo a && echo b || echo c; ! false; time true; }
oo() { for ((i = 0 ; i < 3 ; i++ )); do echo $i; done > /dev/null; }
pp() { echo "$@" >&2; cat <<< "here string"; exec 3>&1; echo x >&3; exec 3>&-; cmd &> all.log; cmd2 &>> all.log; cmd3 >| forced; }
qq() { x=1; y=2 z=3; }
rr() { if a; b; then c; d; fi; while a; b; do c; done; }
ss() { case x in esac; case y in a) ;; esac; }
tt() { { echo nested; { echo deeper; }; }; }
uu() { f() { echo inner-f; }; f; }
vv() { echo 'single quoted' "double $quoted" $'ansi\n' `backtick` $(sub shell) ${param:-default} $((1+2)) <(proc sub); }
for n in a b c d e f gg hh ii jj kk ll mm nn oo pp qq rr ss tt uu vv; do declare -f $n; done
### end
### roundtrip
f() { local n=$1; if (( n > 2 )); then echo big; else echo small; fi; for i in 1 2; do echo "i=$i"; done; }
g() { case $1 in a) echo A;; *) echo other;; esac | tr a-z A-Z; }
eval "$(declare -f f | sed 's/^f /f2 /')"; f2 5; f2 1
bash -c "$(declare -f g); g a; g zzz"
declare -f f g | wc -l
export -f f; bash -c 'f 9' | head -n 1; declare -f | grep -c '^declare -fx f$'; declare -F | sort
type f | head -n 1; type -t f; command -V g | head -n 2
unset -f f; declare -f f; echo "rc=$?"; declare -F
### end
''')

more('extglob', r'''
### e1
touch a.txt b.md c.gz
echo !(*.gz)
### end
### e2
touch a.txt b.md c.gz
shopt -s extglob
echo !(*.gz)
echo @(a|b).*
echo +([a-c]).txt
### end
### e3
x=000123
echo ${x##+(0)}
shopt -s extglob
echo ${x##+(0)}
### end
### e4
case aaa in +(a)) echo yes;; *) echo no;; esac
### end
### e5
shopt -s extglob
case aaa in +(a)) echo yes;; *) echo no;; esac
### end
### e6
p='+(a)'
case aaa in $p) echo yes;; *) echo no;; esac
shopt -s extglob
case aaa in $p) echo yes;; *) echo no;; esac
### end
### e7
[[ aaa == +(a) ]] && echo yes
x=file.fastq.gz; [[ $x == *.@(fq|fastq).gz ]] && echo fq
### end
### e8
touch a.txt b.md c.gz
p='*.@(txt|md)'
echo $p
shopt -s extglob
echo $p
### end
### e9
shopt extglob
shopt -s extglob
shopt extglob
echo $BASHOPTS | tr : '\n' | grep extglob
### end
### e10
echo hi
shopt -s extglob; echo +(a)
echo after
### end
### e11
f() {
  shopt -s extglob
}
f
echo +(a)
### end
### e12
echo hi
x=$(echo +(a))
echo "after $x"
### end
### e13
shopt -s extglob
x=$(echo +(a))
echo "after $x"
shopt -u extglob
echo ?(b)
echo end
### end
### e14
if true; then
  shopt -s extglob
fi
echo @(x|y)
### end
### e15
echo a(b)
### end
### e16
x=aXbXc
echo ${x//+(X)/-}
shopt -s extglob
x=aXXbXc
echo ${x//+(X)/-}
### end
### e17
touch a.txt b.md
eval 'echo !(a.txt)'
shopt -s extglob
eval 'echo !(a.txt)'
### end
### e18
touch a.txt b.md
ls !(a.txt)
echo "rc=$?"
### end
### e19
bash -c 'shopt -s extglob
echo +(z)'
bash -O extglob -c 'echo +(z)'
### end
### e20
if !(false); then echo neg; fi
! (true); echo "rc=$?"
### end
### e21
shopt -s extglob
if !(false); then echo neg; fi
echo "rc=$?"
### end
### e22
x=report_v2.txt
echo "${x%.@(txt|csv)}"
echo "${x/@(report|data)/R}"
shopt -s extglob
echo "${x%.@(txt|csv)}"
echo "${x/@(report|data)/R}"
### end
### e23
set -e
shopt -s extglob nullglob
touch s1.fastq.gz s2.fq.gz s3.bam
for f in *.@(fastq|fq).gz; do echo "$f"; done
### end
### e24
shopt -s nullglob
shopt -s extglob 2>/dev/null || true
echo @(q|r)
### end
### e25
printf 'a.b\naxb\n' > t.txt
fgrep a.b t.txt
fgrep -c x t.txt
printf 'a.b\naxb\n' | egrep 'a.b|zz'
### end
### e26
bash -O extglob -c 'touch k1 k2; echo k+([0-9])'
bash +O extglob -c 'x=aab; echo ${x##+(a)}'
bash -O nosuchopt -c 'echo hi'; echo "rc=$?"
### end
### e27
shopt -s extglob
touch r1.fq r2.fq keep.txt
rm -f !(keep.txt|s.sh|*.fq)
ls
### end
### e28
shopt -s extglob
f=sample_R1_001.fastq.gz
echo "${f%%_R[12]*(_001).f*q.gz}" "${f/%.f?(ast)q.gz/.bam}"
v="  padded  "; v="${v##+([[:space:]])}"; v="${v%%+([[:space:]])}"; echo "[$v]"
### end
### e29
set -euo pipefail
ls -d !(d1) > /dev/null 2>&1 && echo listed || echo "no: $?"
### end
### e30
find . -maxdepth 1 -name '+(a).txt' | sort
find . -maxdepth 1 -name '@(a|b).txt' | sort
ls --hide='@(a|b).txt' | head -n 3
### end
''')

more('closed-pipe', r'''
seq 1 100000 | head -n 1; echo "${PIPESTATUS[@]}"; seq 1 100000 | head -n 1 > /dev/null; echo "rc=$?"; set -o pipefail; seq 1 100000 | head -n 1 > /dev/null; echo "rc=$?"; set +o pipefail; seq 1 100000 | head -n 1 > /dev/null; echo "rc=$?"
seq 1 100000 | grep -q 5; echo "${PIPESTATUS[@]}"; seq 1 100000 | sed -n 1p; echo "${PIPESTATUS[@]}"; seq 1 100000 | sed 1q; echo "${PIPESTATUS[@]}"; seq 1 100000 | awk 'NR == 1 { print; exit }'; echo "${PIPESTATUS[@]}"; seq 1 100000 | awk 'NR == 1'; echo "${PIPESTATUS[@]}"
seq 1 100000 | wc -c; echo "${PIPESTATUS[@]}"; seq 1 100000 | wc -l; echo "${PIPESTATUS[@]}"; seq 1 100000 | tail -n 1; echo "${PIPESTATUS[@]}"; seq 1 100000 | tail -c 5; echo "${PIPESTATUS[@]}"; seq 1 100000 | sort -n | tail -n 1; echo "${PIPESTATUS[@]}"; seq 1 100000 | cat > /dev/null; echo "${PIPESTATUS[@]}"; seq 1 100000 | md5sum | cut -c1-8; echo "${PIPESTATUS[@]}"
seq 1 100000 | sort -rn | head -n 1; echo "${PIPESTATUS[@]}"; seq 1 100000 | sort -rn | head -n 1 | tr 0 o; echo "${PIPESTATUS[@]}"; seq 1 100000 | head -c 10 | wc -c; echo "${PIPESTATUS[@]}"; seq 1 100000 | grep -m 2 9; echo "${PIPESTATUS[@]}"; seq 1 100000 | grep -c 9; echo "${PIPESTATUS[@]}"; seq 1 100000 | grep -l 9; echo "${PIPESTATUS[@]}"
seq 1 100000 | while read x; do echo "first $x"; break; done; echo "${PIPESTATUS[@]}"; seq 1 100000 | { head -n 1; }; echo "${PIPESTATUS[@]}"; seq 1 100000 | { read a; read b; echo "$a $b"; }; echo "${PIPESTATUS[@]}"; seq 1 100000 | while read x; do :; done; echo "${PIPESTATUS[@]}"; seq 1 100000 | { cat > /dev/null; }; echo "${PIPESTATUS[@]}"; seq 1 100000 | { wc -l; }; echo "${PIPESTATUS[@]}"
seq 1 100000 | true; echo "${PIPESTATUS[@]}"; seq 1 100000 | echo hi; echo "${PIPESTATUS[@]}"; seq 1 100000 | cat < a.txt | wc -l; echo "${PIPESTATUS[@]}"; seq 1 100000 | cat - > /dev/null; echo "${PIPESTATUS[@]}"; seq 1 100000 | sort /dev/stdin | wc -l; echo "${PIPESTATUS[@]}"; seq 1 100000 | wc -l /dev/stdin | cut -d' ' -f1; echo "${PIPESTATUS[@]}"
f() { head -n 1; }; seq 1 100000 | f; echo "${PIPESTATUS[@]}"; g() { cat > /dev/null; }; seq 1 100000 | g; echo "${PIPESTATUS[@]}"; h() { seq 1 100000; }; h | head -n 1; echo "${PIPESTATUS[@]}"; { seq 1 100000; echo more; } | head -n 1; echo "${PIPESTATUS[@]}"; for i in 1 2; do seq 1 100000; done | head -n 1; echo "${PIPESTATUS[@]}"; ( seq 1 100000 ) | sed 2q | wc -l; echo "${PIPESTATUS[@]}"
### pipefail_script
#!/bin/bash
set -euo pipefail
echo "start"
seq 1 100000 | awk 'NR <= 2'
seq 1 100000 | sed -n '1,2p'
n=$(seq 1 100000 | wc -l)
echo "n=$n"
first=$(seq 1 100000 | head -n 1) || echo "command substitution failed with $?"
echo "first=$first"
seq 1 100000 | head -n 2 || echo "pipeline failed with $?"
echo "before the fatal line"
seq 1 100000 | head -n 2
echo "not reached"
### end
''')


# ---- from the second independent check of the terminal (October 2026) and from mending what it found ----
more('nounset-in-arithmetic', r'''
### u1
set -u; echo $((n + 1)); echo "not reached"
### end
### u2
set -u; a=(1); echo $(( a[5] + 1 )); echo "reached?"
### end
### u3
set -u; echo "${#x}"; echo "not reached"
### end
### u4
set -u; echo "${#arr[@]}"; echo "reached?"
### end
### u5
set -u; (( n++ )); echo "reached? $n"
### end
### u6
set -u; (( n = 5 )); echo "n=$n"; (( m += 1 )); echo "m=$m"
### end
### u7
set -u; let k=k+1; echo "k=$k"
### end
### u8
set -u; for (( i = 0; i < lim; i++ )); do echo $i; done; echo after
### end
### u9
set -u; a=(x y z); echo "${a[idx]}"; echo after
### end
### u10
set -u; s=abcdef; echo "${s:off:2}"; echo after
### end
### u11
set -u; [[ n -eq 0 ]] && echo zero; echo after
### end
### u12
set -u; [ "${n:-0}" -eq 0 ] && echo zero; echo $(( ${n:-0} + 1 )); echo after
### end
### u13
set -u; declare -i t; t=u+1; echo "t=$t"
### end
### u14
set -u; x=1; echo $(( x ? y : 2 )); echo after
### end
### u15
set -u; x=0; echo $(( x ? y : 2 )) $(( x && y )) $(( 1 || y )); echo after
### end
### u16
set -u; declare -A m; echo $(( m[k] + 1 )); echo after
### end
### u17
set -u; n=; echo $(( n + 1 )); echo after
### end
### u18
set -u; count=0; while read -r l; do ((count++)) || true; done < a.txt; echo "count=$count"; ((total++)) || true; echo "total=$total"
### end
### u19
echo $((n + 1)) "${#x}" "${#arr[@]}"; ((c++)); echo "c=$c"
### end
### u20
set -u; a=(1 2); echo "${a[5]:-none}" "${#a[5]}"; echo after
### end
''')

more('default-words-and-subscripts', r'''
### v1
set -u; a=(); echo "${#a[@]}"; declare -A m; echo "${#m[@]}"; declare -a e; echo "${#e[@]}"; echo $(( a[0] + 1 )); echo after
### end
### v2
set -u; declare -a e; echo $(( e[0] + 1 )); echo after
### end
### v3
set -u; a=(); echo $(( a[0] + 1 )); echo after
### end
### v4
set -u; echo "${#1}"; echo after
### end
### v5
set -u; echo "${#@} ${#*} ${#?} ${##}"; echo after
### end
### v6
a=(x); a+=y; echo "${#a[@]} ${a[0]}"; a+=(z); a+=w; declare -p a; declare -A m=([k]=1); m+=q; declare -p m; declare -i n=(1 2); n+=5; declare -p n
### end
### v7
a=(a b c); i=1; unset 'a[$i]'; echo "${a[*]}"; a=(a b c); unset 'a[${#a[@]}-1]'; echo "${a[*]}"; a=(a b c); unset 'a[-1]'; echo "${a[*]}"; a=(a b c); n=1; unset 'a[n+1]'; echo "${a[*]}"; a=(a b c); unset a[0] a[2]; echo "${a[*]} ${!a[*]}"
### end
### v8
declare -A m=([k]=1 [j]=2 ['a b']=3); k=k; unset 'm[$k]'; echo "${#m[@]}"; unset 'm[a b]'; echo "${!m[@]}"; unset "m[j]"; echo "${#m[@]}"; unset 'm[nosuch]'; echo "rc=$?"
### end
### v9
f() { local -n r=$1; unset 'r[1]'; }; a=(a b c); f a; echo "${a[*]}"; g() { local -n r=$1; unset r; }; b=5; g b; echo "[${b-unset}]"
### end
### v10
a=(a b c); unset 'a[9]'; echo "rc=$? ${a[*]}"; unset 'a[-9]'; echo "rc=$?"; s=str; unset 's[0]'; echo "rc=$? [${s-unset}]"; t=str; unset 't[1]'; echo "rc=$? [${t-unset}]"; unset 'nosuch[1]'; echo "rc=$?"
### end
### v11
read <<< "  x  "; echo "[$REPLY]"; read -r <<< $'\ttab  '; echo "[$REPLY]"; read v <<< "  x  "; echo "[$v]"; printf '  a b  \n' | { read; echo "[$REPLY]"; }; IFS= read -r l <<< "  keep  "; echo "[$l]"
### end
### v12
a=(p q); read -r 'a[1]' <<< new; echo "${a[1]}"; read -r 'a[5]' <<< far; declare -p a; declare -A m; read -r 'm[key]' <<< val; echo "${m[key]}"; read -r x 'a[0]' <<< "one two three"; echo "$x|${a[0]}"
### end
### v13
a=(p q); i=1; [[ -v a[i] ]] && echo set1; [[ -v a[5] ]] || echo unset5; [[ -v a ]] && echo seta; declare -A m=([k]=1); k=k; [[ -v m[$k] ]] && echo setk; [[ -v 'm[$k]' ]] && echo setk2; [[ -v m[x] ]] || echo unsetx; [ -v 'a[0]' ] && echo test0; [[ -v a[@] ]] && echo at; e=(); [[ -v e[@] ]] || echo emptyat; [[ -v e ]] || echo emptye
### end
### v14
declare 'a[2]=x'; declare -p a; declare -a 'b[1]=y'; declare -p b; export 'c[0]=z' 2>&1; declare -p c 2>&1; local 'd[0]=1' 2>&1 | head -n 1
### end
### v15
unset u; printf '<%s>' ${u:-"*.fa"}; echo; printf '<%s>' ${u:-'a b'} ${u:-a b} "${u:-a b}" ${u:-"a b" c}; echo; v="x y"; args=(${v:+-o "$v"}); echo "${#args[@]}"; args=(${v:+"-o" "$v" tail}); echo "${#args[@]}"; printf '<%s>' ${u:-$v} ${u:-"$v"} "${u:-$v}"; echo
### end
### v16
a=(); b=("${a[@]+"${a[@]}"}"); echo "${#b[@]}"; a=(1 "2 3"); b=("${a[@]+"${a[@]}"}"); echo "${#b[@]}"; set --; c=("${@:+"$@"}"); echo "${#c[@]}"; set -- "p q" r; c=("${@:+"$@"}"); echo "${#c[@]}"; c=(${1:+"$@"}); echo "${#c[@]}"; d=("${u:-"$@"}"); echo "${#d[@]}"; d=(${u:-"$@"}); echo "${#d[@]}"; d=(${u:-$@}); echo "${#d[@]}"
### end
### v17
unset u; echo "${u:-'q'}" "${u:-~/x}" ${u:-~/x} ${u:-'q'} "${u:-"dq"}" "${u:-\$x}" ${u:-\$x} "${u:-a\ b}" ${u:-a\ b}; echo "${u:-`echo bt`}" "${u:-$(echo cs)}" "${u:-$((1+1))}"
### end
### v18
unset u; x=5; echo "${u:=a b}" "$u"; unset u; echo ${u:=*.fa}; echo "$u"; unset u; : ${u:="q r"}; echo "$u"; echo "${x:+yes "$x"}" ${x:+a "b c" d} | wc -w; unset e; echo "${e:?custom message}" 2>&1 | sed 's/.*: e: //'
### end
### v19
unset u; for w in ${u:-"a b" c}; do echo "[$w]"; done; for w in ${u:-'x y'z}; do echo "[$w]"; done; IFS=,; for w in ${u:-a,b "c,d"}; do echo "[$w]"; done; unset IFS
### end
### v20
unset u; s="${u:-}"; echo "[$s]"; echo "[${u:-  spaced  }]" [${u:-  spaced  }]; echo "${u:-{a,b}}" ${u:-{a,b}}; echo "${u:-*}" | wc -c; echo "${HOME:+h}${u:+n}" "${u-}" "${u+x}"
### end
''')

more('subshells-return-exec', r'''
### s1
f() { ( return 5 ); echo "after subshell rc=$?"; }; f; echo "f rc=$?"
### end
### s2
find_it() { cat a.txt | while read -r x; do if [[ $x == beta ]]; then echo found; return 0; fi; done; echo "not found"; return 1; }; find_it; echo "rc=$?"
### end
### s3
echo x | while read l; do exit 3; done; echo "after $?"
### end
### s4
f() { echo a | { read v; return 7; }; echo "pipe rc=$?"; }; f; echo "f rc=$?"
### end
### s5
f() { { return 4; } | cat; echo "rc=${PIPESTATUS[0]} $?"; }; f; echo "f rc=$?"
### end
### s6
( exec > /dev/null; echo silenced ); echo "after null"
### end
### s7
( exec > out.txt; echo in-file ); echo "on screen"; cat out.txt
### end
### s8
echo data | ( exec > out2.txt; cat ); echo "screen2"; cat out2.txt
### end
### s9
f() { exec 3> fd3.txt; echo to3 >&3; }; ( f ); echo x >&3 2> /dev/null; echo "rc=$?"; cat fd3.txt
### end
### s10
( exec 2> err.txt; ls nosuch ); ls nosuch2 2>&1 | wc -l; cat err.txt | wc -l
### end
### s11
x=$(exec > /dev/null; echo hidden); echo "[$x]"; y=$(exec 2>&1; ls nosuch); echo "$y" | wc -l
### end
### s12
( exec < a.txt; read l; echo "$l" ); read -t 0.1 z < /dev/null; echo "rc=$?"
### end
### s13
for i in 1 2; do ( break ) 2> /dev/null; echo "i=$i"; done; for i in 1 2; do ( continue ) 2> /dev/null; echo "j=$i"; done
### end
### s14
f() { for i in 1 2 3; do echo $i | while read n; do [[ $n == 2 ]] && return 9; echo "n=$n"; done; echo "loop rc=$?"; done; echo end; }; f; echo "f rc=$?"
### end
### s15
( exit 4 ); echo "rc=$?"; ( return 4 ) 2> /dev/null; echo "rc=$?"; { ( exit 6 ); }; echo "rc=$?"
### end
### s16
set -e; f() { ( return 3 ); echo "not reached"; }; f; echo "not reached 2"
### end
### s17
f() { echo start; $(return 5); echo "rc=$?"; x=$(return 6); echo "rc=$?"; x=$(echo out; return 7); echo "rc=$? $x"; }; f
### end
### s18
f() { ( exec > /dev/null; echo hidden; return 2 ); echo "visible rc=$?"; }; f
### end
### s19
( source /dev/stdin <<< 'exec > src_out.txt; echo sourced' ); echo "after source"; cat src_out.txt
### end
### s20
f() { cat a.txt | grep -q beta && return 0; return 1; }; f; echo "rc=$?"; g() { grep -q zzz a.txt || { echo "missing"; return 3; }; echo "not reached"; }; g; echo "rc=$?"
### end
''')

more('declared-only-arrays', r'''
### d1
set -u; declare -A c; for k in a b a; do ((c[$k]++)) || true; done; declare -p c
### end
### d2
set -u; declare -A c=(); for k in a b a; do ((c[$k]++)) || true; done; declare -p c
### end
### d3
set -u; declare -A c; c[x]=1; for k in a b a; do ((c[$k]++)) || true; done; declare -p c
### end
### d4
set -u; declare -A c; for k in a b a; do c[$k]=$(( ${c[$k]:-0} + 1 )); done; declare -p c
### end
### d5
set -u; declare -a e; e[2]=5; echo $(( e[0] + e[2] )); declare -a f; echo "${#f[@]}"; echo after
### end
### d6
set -u; declare -A m; echo "${m[@]}" "${!m[@]}"; echo "n=${#m[@]}"; echo after
### end
### d7
set -u; declare -a f; echo "${f[@]}" "${!f[@]}"; echo "n=${#f[@]}"; echo after
### end
### d8
set -u; local_test() { local -A seen; local -a list; [[ -v seen[x] ]] || echo "not seen"; seen[x]=1; echo "${#seen[@]} ${#list[@]}"; }; local_test
### end
### d9
set -u; declare -A c; (( c[a] += 1 )); echo "after ${c[a]}"
### end
### d10
set -u; declare -i n; echo "[$n]"; echo after
### end
### d11
set -u; declare x; echo "[${x-unset}]"; echo "$x"; echo after
### end
### d12
declare -A m; declare -p m; declare -a a; declare -p a; declare -i n; declare -p n; declare x; declare -p x; [[ -v m ]] || echo "m not set"; echo "${#m[@]} ${#a[@]}"
### end
''')

more('tilde-in-quotes-is-a-name', r'''
mkdir -p "~/results/sub"; ls -d ./~ ./~/results; ls -d ~/results 2>&1 | sed 's/^ls: //'
d="~/out"; mkdir -p "$d"; echo x > "$d/f.txt"; cat "./~/out/f.txt"; ls
d='~'; [[ -d $d ]] && echo dir || echo nodir; [ -d "~" ] && echo dir2 || echo nodir2; cd "~" 2>&1; echo "rc=$?"; pwd | sed 's|.*/||'
echo hi > "~"; cat ./~; ls -l "~" | wc -l; rm "~"; ls
echo ~ ~/x "~" '~' \~ ~nosuchuser ~+ "~/y" a~ a=~ a=~/b a:~/b :~ x=~:~/c:~ --out=~/x -o~/x
x=~/data; echo "$x"; y="~/data"; echo "$y"; z=~; echo "$z"; export P=~/bin:~/tools; echo "$P"; declare q=~/q; echo "$q"; w=a:~; echo "$w"
p=$HOME/a/b; echo "${p#~/}" "${p#"~/"}" "${p/#~/TILDE}" "${p/~/T}"; echo "${u:-~/def}" "${u:-"~/def"}"; echo ${u:-~/def}
case $HOME/x in ~/x) echo match;; *) echo no;; esac; case "~/x" in ~/x) echo match;; *) echo no;; esac; [[ $HOME == ~ ]] && echo eq; [[ "~" == ~ ]] || echo ne
for f in ~/w/a.txt "~/w/a.txt"; do [[ -f $f ]] && echo "file $f" || echo "none $f"; done
cat < ~/w/a.txt | head -n 1; cat < "~/w/a.txt" 2>&1 | head -n 1; echo data > ~/w/t1.txt; echo data > "~/t2.txt" 2>&1; ls
ls ~/w/a.txt; ls "~/w/a.txt" 2>&1; cp ~/w/a.txt "~x"; ls; cp "~/w/a.txt" . 2>&1; echo "rc=$?"
touch "~/f" 2>&1; echo "rc=$?"; mkdir "~"; touch "~/f"; echo "rc=$?"; find . -name f; find "~" -type f; rm -r "~"; ls -d "~" 2>&1
a=(~/x "~/y" ~); echo "${a[@]}"; echo ~/w/*.txt | wc -w; echo "~/w/"*.txt; printf '%s\n' ~/"fix dir" ~"/x" ~\/x
test -e "~/w" && echo yes || echo no; test -e ~/w && echo yes || echo no; [ -f '~/w/a.txt' ] || echo "no file"; stat -c %n "~" 2>&1; realpath "~/x" | sed 's|.*/w/|w/|'; basename "~/x"; dirname "~/x"
OUT="${1:-~/results}"; echo "$OUT"; mkdir -p "$OUT/sub"; ls -d ./~ 2> /dev/null; ls -d ~/results 2>&1 | sed 's/^ls: //'
tar_dir="~/archive"; mkdir -p "$tar_dir" && cd "$tar_dir" && pwd | sed 's|.*/w/|w/|'; cd - > /dev/null; ls
while read -r p; do ls "$p" 2>&1; done <<< "~/w/a.txt"; eval "ls ~/w/a.txt"; p='~/w/a.txt'; eval "ls $p"; echo '~/w/a.txt' | xargs ls 2>&1
pushd "~" 2>&1 | head -n 1; pushd ~ > /dev/null; pwd; popd > /dev/null; source "~/x.sh" 2>&1 | head -n 1; bash "~/x.sh" 2>&1 | head -n 1
cd ~/w/d2; cd ~-; pwd | sed 's|.*/||'; echo ~- | sed 's|.*/||'; echo ~+ | sed 's|.*/||'; cd ~+/d1; pwd | sed 's|.*/||'
ls -d "~"* 2>&1; touch "~a" "~b"; ls -d "~"*; ls -d ./~*; ls -d \~*; rm \~a "~b"; ls
du -s "~" 2>&1; echo "rc=$?"; chmod 644 "~/x" 2>&1; echo "rc=$?"; mv "~/a" b 2>&1; echo "rc=$?"; rmdir "~" 2>&1; echo "rc=$?"; file "~" 2>&1; md5sum "~/x" 2>&1; echo "rc=$?"
x=$(cd "~" 2>&1; pwd); echo "$x" | tail -n 1 | sed 's|.*/||'; (cd ~ && pwd); [[ -d ~/w && ! -e "~/w" ]] && echo right
echo text | tee "~t.txt" > /dev/null; cat "~t.txt"; echo more >> "~t.txt"; wc -l "~t.txt"; sort -o "~s.txt" "~t.txt"; cat ./~s.txt; diff "~t.txt" "~s.txt" > /dev/null; echo "rc=$?"
''')

more('environment-of-programs', r'''
export V=x; awk 'BEGIN { print "[" ENVIRON["V"] "]" }'; V2=y awk 'BEGIN { print "[" ENVIRON["V2"] "]" }'; awk 'BEGIN { print "[" ENVIRON["V2"] "]" }'; W=plain; awk 'BEGIN { print "[" ENVIRON["W"] "]" }'
export A=1; unset A; awk 'BEGIN { print "[" ENVIRON["A"] "]" }'; export B=2; export -n B; awk 'BEGIN { print "[" ENVIRON["B"] "]" }'; declare -x C=3; awk 'BEGIN { print "[" ENVIRON["C"] "]" }'; D=4; export D; awk 'BEGIN { print "[" ENVIRON["D"] "]" }'
export S=sub; ( S=changed; awk 'BEGIN { print ENVIRON["S"] }' ); awk 'BEGIN { print ENVIRON["S"] }'; echo "$(S=inner awk 'BEGIN { print ENVIRON["S"] }')"; bash -c 'awk "BEGIN { print ENVIRON[\"S\"] }"'
export Q='a b  c'; awk 'BEGIN { print "[" ENVIRON["Q"] "]" }'; export E=; awk 'BEGIN { print ("E" in ENVIRON) ? "set" : "unset", "[" ENVIRON["E"] "]" }'; export U='é ü'; awk 'BEGIN { print ENVIRON["U"] }'; export N=$'two\nlines'; awk 'BEGIN { print ENVIRON["N"] }'
a=(1 2 3); export a; awk 'BEGIN { print "[" ENVIRON["a"] "]" }'; declare -A h=([k]=v); export h; awk 'BEGIN { print "[" ENVIRON["h"] "]" }'; declare -i n=5; export n; awk 'BEGIN { print ENVIRON["n"] }'; n+=2; awk 'BEGIN { print ENVIRON["n"] }'
set -a; AUTO=yes; set +a; awk 'BEGIN { print ENVIRON["AUTO"] }'; NOT=no; awk 'BEGIN { print "[" ENVIRON["NOT"] "]" }'; readonly RO=r; export RO; awk 'BEGIN { print ENVIRON["RO"] }'
export X=1; X=2 awk 'BEGIN { print ENVIRON["X"] }'; awk 'BEGIN { print ENVIRON["X"] }'; X=3; awk 'BEGIN { print ENVIRON["X"] }'; echo a | X=4 awk '{ print ENVIRON["X"] }'; X=5 Y=6 awk 'BEGIN { print ENVIRON["X"] ENVIRON["Y"] }'
export K=v; echo a | xargs -I{} awk 'BEGIN { print ENVIRON["K"] "{}" }'; find a.txt -exec awk 'BEGIN { print ENVIRON["K"] }' {} \; ; timeout 5 awk 'BEGIN { print ENVIRON["K"] }'; command awk 'BEGIN { print ENVIRON["K"] }'; env awk 'BEGIN { print ENVIRON["K"] }'
export K=v; printf 'x\n' | while read -r l; do awk -v l="$l" 'BEGIN { print ENVIRON["K"] l }'; done; for i in 1 2; do K=$i awk 'BEGIN { print ENVIRON["K"] }'; done; awk 'BEGIN { print ENVIRON["K"] }'
export LC_ALL=C; awk 'BEGIN { print ENVIRON["LC_ALL"] }'; printf 'b\nA\na\nB\n_\n1\n' | sort | paste -sd,; printf 'é\ne\nf\n' | sort | paste -sd,; printf 'é\n' | wc -m; printf 'éa\n' | cut -c1 | od -An -c | tr -s ' '; echo 'é' | sed 's/./X/g'; echo 'aé' | grep -o . | wc -l
printf 'é\n' | wc -m; printf 'é\n' | LC_ALL=C wc -m; printf 'é\n' | LC_ALL=C.UTF-8 wc -m; echo 'é' | LC_ALL=C sed 's/./X/g'; echo 'é' | sed 's/./X/g'; echo 'aé' | LC_ALL=C grep -o . | wc -l; echo 'aé' | grep -o . | wc -l; echo 'É' | LC_ALL=C grep -ic 'é'; echo 'É' | grep -ic 'é'
printf 'b\na\nB\nA\n' | LC_ALL=C sort -f | paste -sd,; printf 'é\nz\n' | LC_ALL=C sort | paste -sd,; printf 'a\tb\n' | LC_ALL=C cut -f2; printf 'é\n' | LC_ALL=C tr -d 'é' | od -An -c | tr -s ' '; printf 'ÉA\n' | LC_ALL=C tr 'A-Z' 'a-z'
export TMPDIR="$PWD/tmpd"; mkdir -p "$TMPDIR"; seq 2000 | sort -rn | head -n 2; ls "$TMPDIR" | wc -l; export TMPDIR=/nonexistent/dir; seq 2000 | sort -rn | tail -n 1; unset TMPDIR; seq 5 | sort -r | head -n 1
export POSIXLY_CORRECT=1; echo 'a b' | awk '{ print $2 }'; printf 'a\nb\n' | grep -c a; seq 3 | sed -n '2p'; unset POSIXLY_CORRECT; printf 'x\n' | sort
''')

more('getopt', r'''
getopt -o ab:c:: --long alpha,beta:,gamma:: -n prog -- -a -b val -cX -c --alpha --beta=1 --beta 2 --gamma --gamma=g file1 file2; echo "rc=$?"
getopt -o ab: -- -a x -b "it's" y -- -z; echo "rc=$?"; getopt -o ab: -- -x; echo "rc=$?"; getopt -o ab: -- -b; echo "rc=$?"
getopt -o '' --long help,input:,output: -- --input in.txt --output=out.txt --help extra; echo "rc=$?"; getopt -o '' -l help -- --hel; getopt -o '' -l help,helper -- --hel; echo "rc=$?"; getopt -o '' -l help,helper: -- --hel; echo "rc=$?"
getopt -o a -l alpha -- --beta; echo "rc=$?"; getopt -o a -l alpha -- --alpha=3; echo "rc=$?"; getopt -o a -l beta: -- --beta; echo "rc=$?"; getopt -n my.sh -o a -- -q; echo "rc=$?"
getopt ab:c -a -b v x -c y; echo "rc=$?"; getopt ab: -b "two words" "x y"; getopt -u -o ab: -- -b "two words" "x y"; getopt +ab -a x -b; getopt -- ab -a x
getopt -o +ab: -- -a x -b y; getopt -o -ab: -- -a x -b y z -- w; POSIXLY_CORRECT=1 getopt -o ab: -- -a x -b y; getopt -o :ab: -- -x -b; echo "rc=$?"
getopt -q -o ab: -- -x -a; echo "rc=$?"; getopt -Q -o ab: -- -a -x; echo "rc=$?"; getopt -Q -q -o a -- -x; echo "rc=$?"; getopt -T; echo "rc=$?"; getopt -T -o a -- x; echo "rc=$?"
getopt -a -o ab: -l alpha,beta: -- -alpha -beta 3 -a -b 4 -al; echo "rc=$?"; getopt -a -o ab -l bx -- -b -bx -ab; echo "rc=$?"; getopt -a -o a -l all -- -x; echo "rc=$?"
getopt -o a --long 'alpha, beta: gamma::' -- --alpha --beta 1 --gamma; getopt -o a -l alpha -l beta -- --beta --alpha; getopt --options=ab: --longoptions=xx --name=nm -- -b 1 --xx
getopt -s bash -o a: -- -a "x'y" 'a b' '$HOME' '!x' 'back\slash'; getopt -s sh -o a -- "q'q"; getopt -s tcsh -o a: -- -a 'x!y' 'a b' 'back\slash' "q'q"; getopt -s csh -o a -- $'new\nline'
getopt -o ab: -- - -a -- -b; getopt -o a -- '' x ''; getopt -o a: -- -a '' ; getopt -o a:: -- -a x -ay; getopt -o a -- -aa -a; getopt -o ab:c -- -abcd -c
getopt; echo "rc=$?"; getopt -o; echo "rc=$?"; getopt -o a; echo "rc=$?"; getopt -o a --; echo "rc=$?"; getopt -x; echo "rc=$?"; getopt --bogus -o a -- x; echo "rc=$?"; getopt -s zsh -o a -- x; echo "rc=$?"; getopt -l a:,: -o a -- x; echo "rc=$?"
getopt --opt ab --long x -- -a --x y; getopt --q -o a -- -a; echo "rc=$?"; getopt --quiet -o a -- -z; echo "rc=$?"; getopt --quiet-output -o a -- -a; echo "rc=$?"; getopt --unquoted --options a: -- -a 'x y'; getopt --alt -o a -l abc -- -abc
getopt -o a -l out:,outdir -- --out; echo "rc=$?"; getopt -o a -l out:,outdir: -- --ou 1; echo "rc=$?"; getopt -o a -l verbose,version -- --ver --verb --vers; echo "rc=$?"; getopt -o a -l x -- --x=; echo "rc=$?"; getopt -o a -l x: -- --x=; echo "rc=$?"
getopt -o hv -l help -- -h -v --help -hv -vh positional -- --help; getopt -o i:o: -- -i in -o out -iin2 -oout2 -i -o; getopt -o f: -- -f -- x; getopt -o f: -l file: -- --file -- x; getopt -o f -- -- -f; getopt -o f -- x -- -f; getopt -o f -- x -f -- -f
getopt -o a 2>&1 -- -a; getopt -o 'a b' -- -a -' ' -b; getopt -o a: -- -a=5 -a =5; getopt -o 'a-' -- -a- -a; echo "rc=$?"; getopt -o a: -l a: -- -a 1 --a 2 --a=3; getopt -o W -- -W x
### getopt-script
set -- -v --min-qual 30 -o "my out.txt" a.txt "b c.txt" --output=z.txt -- -x
set -euo pipefail
usage() { echo "usage: $0 [-v] [-o FILE] [--min-qual N] FILE..." >&2; exit 2; }
OPTS=$(getopt -o hvo: --long help,verbose,output:,min-qual: -n "run.sh" -- "$@") || usage
eval set -- "$OPTS"
VERBOSE=0; OUT=out.txt; MINQ=20
while true; do
  case "$1" in
    -h|--help) usage ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -o|--output) OUT=$2; shift 2 ;;
    --min-qual) MINQ=$2; shift 2 ;;
    --) shift; break ;;
    *) echo "internal error" >&2; exit 3 ;;
  esac
done
echo "verbose=$VERBOSE out=$OUT minq=$MINQ files=$# first=${1:-none}"
for f in "$@"; do echo "file: [$f]"; done
### end
### getopt-script-err
OPTS=$(getopt -o o: --long output: -n "run.sh" -- --nosuch -o 2>&1); echo "rc=$?"; echo "$OPTS"
if ! OPTS=$(getopt -o a --long all -- -z 2> /dev/null); then echo "bad options"; fi
eval set -- "$(getopt -o ab: -l file: -- -b "has 'quote'" --file "sp ace" rest "more rest")"; printf '[%s]\n' "$@"
### end
### getopt-test-idiom
getopt -T > /dev/null 2>&1 && rc=0 || rc=$?
if [[ $rc -ne 4 ]]; then echo "old getopt"; exit 1; fi
echo "enhanced getopt"
PARSED=$(getopt --options=vo: --longoptions=verbose,out: --name "$0" -- -v --out results/x a b) || exit 2
eval set -- "$PARSED"
v=n; o=-
while true; do case "$1" in -v|--verbose) v=y; shift;; -o|--out) o="$2"; shift 2;; --) shift; break;; *) echo "error"; exit 3;; esac; done
echo "v=$v o=$o rest=$*"
### end
tty < /dev/null; echo "rc=$?"; echo x | tty; echo "rc=$?"; tty -s < a.txt; echo "rc=$?"; tty -x 2>&1 | head -n 1; tty extra 2>&1 | head -n 1
sync; echo "rc=$?"; stdbuf -oL echo hi; stdbuf -o0 -e0 printf '%s\n' a b | wc -l; stdbuf -i0 -oL -eL cat a.txt | head -n 1; stdbuf; echo "rc=$?"; stdbuf -oL nosuchprog; echo "rc=$?"; stdbuf --output=L seq 2
env -i LANG=C.UTF-8 /usr/bin/locale; env -i LANG=C.UTF-8 LC_ALL=C /usr/bin/locale | head -n 4; env -i /usr/bin/locale | head -n 3; env -i LANG=C.UTF-8 LC_TIME=C /usr/bin/locale | grep -n TIME; env -i LC_ALL=C /usr/bin/locale charmap; env -i LANG=C.UTF-8 /usr/bin/locale charmap; env -i LANG=C.UTF-8 LC_ALL=C LC_TIME=POSIX /usr/bin/locale | grep -n -e TIME -e ALL
command -v getopt > /dev/null && echo have-getopt; command -v stdbuf > /dev/null && echo have-stdbuf; command -v tty locale sync > /dev/null && echo have-three; type -t getopt tty
''')

more('wc-widths', r'''
wc <<< "a b c"; wc < a.txt; cat a.txt | wc; cat a.txt | wc -lw; cat a.txt | wc -l; cat a.txt | wc -c; cat a.txt | wc -; cat a.txt | wc - b.txt; wc a.txt b.txt
{ wc; } < a.txt; cat a.txt | { wc; }; f() { wc; }; cat a.txt | f; f < a.txt; echo "$(cat a.txt | wc)"; wc -lc < a.txt; cat a.txt | wc -m -l; cat a.txt | wc -L -l; printf "x" | wc; : | wc
x=$(seq 1 800); wc <<< "$x"; x=$(seq 1 12500); wc <<< "$x"; x=$(seq 1 13000); wc <<< "$x"; x=$(head -c 65535 /dev/zero | tr "\0" a); wc <<< "$x"; x=$(head -c 65536 /dev/zero | tr "\0" a); wc <<< "$x"
### wc-heredoc
wc <<EOF2
one two
three
EOF2
cat <<EOF3 | wc
four
EOF3
wc -l <<< "x"; wc -lw <<< "x"
### end
echo "a b" | wc; echo "a b" | wc -w; grep -c a a.txt | wc; ls | wc; ls | wc -l; seq 100000 | wc; seq 1000000 | wc -l
while read -r l; do echo "$l" | wc -c; done < a.txt; cat a.txt b.txt | wc | awk '{ print $1, $2, $3 }'; n=$(cat a.txt | wc -l); echo "n=$n"; n=$(wc -l < a.txt); echo "n=$n"; read -r a b c < <(cat a.txt | wc); echo "$a/$b/$c"
cat a.txt | wc > counts.txt; cat counts.txt | od -An -c | tr -s ' '; wc a.txt > c2.txt; cat c2.txt; cat a.txt | tee copy.txt | wc; cat a.txt | sort | uniq -c | wc; cat a.txt | head -n 2 | wc; cat a.txt | wc | wc
bash -c 'cat a.txt | wc'; bash -c 'wc' < a.txt; echo x | bash -c 'wc'; cat a.txt | xargs echo | wc; cat a.txt | (wc); (cat a.txt) | wc; cat a.txt | if true; then wc; fi; cat a.txt | while read -r l; do echo "$l"; done | wc
wc < /dev/null; wc /dev/null; cat /dev/null | wc; wc -l /dev/null a.txt; echo hi | wc /dev/stdin; echo hi | wc -c /dev/stdin; exec 3< a.txt; wc <&3; exec 3<&-; cat a.txt | wc -lwc; cat a.txt | wc --lines --bytes
''')

more('time-caller-builtin', r'''
{ time -p true; } 2>&1 | sed 's/[0-9]/N/g'; { time true; } 2>&1 | sed 's/[0-9]/N/g'; TIMEFORMAT=%R; { time true; } 2>&1 | sed 's/[0-9]/N/g'; TIMEFORMAT='%1R|%0U|%2lS|%%|%3R|%lR|%5R'; { time true; } 2>&1 | sed 's/[0-9]/N/g'
TIMEFORMAT=; { time true; } 2>&1 | wc -c; unset TIMEFORMAT; { time true; } 2>&1 | wc -l; TIMEFORMAT='took %R s'; t=$( { time sleep 0.2; } 2>&1 ); [[ $t =~ ^took\ ([0-9]+)\.([0-9]{3})\ s$ ]] && (( 10#${BASH_REMATCH[1]}${BASH_REMATCH[2]} >= 200 )) && echo "took 0.2 s or a little more"; t=$( { time -p true; } 2>&1 | awk '/real/ { print $2 }' ); [[ $t =~ ^[0-9]+\.[0-9][0-9]$ ]] && echo "elapsed ok"
{ time -p echo x; } 2>&1 | sed 's/[0-9]/N/g'; { time -p { echo a; echo b; }; } 2>&1 | sed 's/[0-9]/N/g'; { ! time -p false; } 2>&1 | sed 's/[0-9]/N/g'; echo "rc=$?"; { time -p echo a | tr a b; } 2>&1 | sed 's/[0-9]/N/g'
f() { caller 0; caller; caller 1; echo "rc=$?"; }; g() { f; }; g; caller; echo "rc=$?"; caller 0; echo "rc=$?"; caller x; echo "rc=$?"
die() { local frame=0; while caller $frame; do ((++frame)); done; echo "died: $*"; }; a() { b; }; b() { die oops; }; a
builtin echo hi; builtin cd d1 && pwd | sed 's|.*/||'; builtin nosuch; echo "rc=$?"; builtin ls; echo "rc=$?"; builtin printf '%s\n' x; cd() { builtin cd "$@" && echo "now in ${PWD##*/}"; }; cd ../d2; builtin; echo "rc=$?"
while getopts ab: o -a -z -b; do echo "o=$o arg=${OPTARG-unset}"; done; OPTIND=1; OPTERR=0; while getopts ab: o -a -z -b; do echo "o=$o arg=${OPTARG-unset}"; done; OPTIND=1; OPTERR=1; while getopts :ab: o -z -b; do echo "o=$o arg=${OPTARG-unset}"; done
### caller-in-script
#!/usr/bin/env bash
set -euo pipefail
log() { echo "[$(caller 0 | cut -d' ' -f1,2)] $*"; }
fail() {
  local i=0 line fn file
  echo "error: $*"
  while read -r line fn file < <(caller $i); do
    echo "  at $fn (${file##*/}:$line)"
    i=$((i + 1))
  done
  return 1
}
step_one() { log "starting"; step_two; }
step_two() { fail "something broke" || echo "handled, rc=$?"; }
step_one
log "done"
### end
''')

# From the third and the fourth independent check and from mending what they found: the empty name ("") is no
# file, hash, the status of a loop after break, the parts of a pipeline as subshells, set -u in a sourced file and in a
# here-document, carriage returns in a script (the line ends of Windows), the options of bash, quotes inside ${ },
# a ~ in PATH, an array that is given a text (its element 0); paths read name by name (FILE/ and nosuch/../x name
# nothing), mv of ".", the folder one is in removed, cd in a subshell and cd -, an empty command name, ${a[k]:=v},
# numbers that end in a carriage return, mapfile -dX, set with a letter it does not know, sed -i and what comes after.
more('empty-names-hash-loop-status', r'''
[ -e "" ]; echo "e $?"; [ -f "" ]; echo "f $?"; [ -d "" ]; echo "d $?"; [ -r "" ]; echo "r $?"; [ -w "" ]; echo "w $?"; [ -x "" ]; echo "x $?"; [ -s "" ]; echo "s $?"; [[ -e "" ]]; echo "E $?"; test -d ""; echo "T $?"; [ "" -ef . ]; echo "ef $?"; [ "" -nt a.txt ]; echo "nt $?"; [ a.txt -nt "" ]; echo "nt2 $?"
for t in sort nosuchtool nosuchtool2; do if [ -x "$(command -v $t)" ]; then echo "$t ok"; else echo "$t MISSING"; fi; done; OUTDIR=; if [ -d "$OUTDIR" ]; then echo "exists"; else echo "must create"; fi
hash nosuch; echo "rc=$?"; hash ls; echo "rc=$?"; hash -t ls | sed 's|.*/||'; hash -t nosuch 2> /dev/null; echo "rc=$?"; hash cd; echo "cd rc=$?"; f() { :; }; hash f; echo "fn rc=$?"; hash ./s.sh; echo "slash rc=$?"; hash -d ls; echo "d rc=$?"; hash -d ls 2> /dev/null; echo "d2 rc=$?"; hash -r; echo "r rc=$?"; hash; hash ls awk nosuch2 sed 2> /dev/null; echo "multi rc=$?"; hash -x 2>&1 | tail -n 1; echo "rc=${PIPESTATUS[0]}"
for t in sort awk nosuch-tool-a nosuch-tool-b; do hash "$t" 2> /dev/null || { echo "missing: $t"; }; done; echo checked
### hash-errexit
set -e; hash sort; echo "sort ok"; hash definitely-not-installed; echo "not reached"
### end
for x in 1 2 3; do [[ $x == 2 ]] && break; done; echo "and-form: $?"; for x in 1 2 3; do false; break; done; echo "plain: $?"; for x in 1 2 3; do [[ $x == 5 ]] && break; done; echo "never: $?"; for x in 1 2 3; do [[ $x != 3 ]] || continue; false; done; echo "cont-last: $?"; for x in 1 2; do (exit 5); continue; done; echo "cont: $?"; for x in 1 2; do (exit 5); done; echo "last: $?"
while true; do false; break; done; echo "w: $?"; until false; do (exit 3); break; done; echo "u: $?"; for i in 1 2; do for j in 1 2; do false; break 2; done; done; echo "b2: $?"; while read -r l; do [[ $l == b* ]] && break; done < a.txt; echo "read: $? $l"; f() { for x in 1 2; do false; continue; done; }; f; echo "fn: $?"; i=0; while (( i < 3 )); do (( i++ )); (( i == 2 )) && continue; false; done; echo "wc: $?"
if for x in 1 2 3; do [[ $x == 2 ]] && break; done; then echo "loop true"; else echo "loop false"; fi; for f in a.txt b.txt; do grep -q BETA "$f" && break; done; echo "grep-and-break rc=$? f=$f"; for x in 1 2; do [[ $x == 2 ]] && break; done && echo "and-list ok" || echo "and-list failed"; for x in 1; do break 0 2> /dev/null; done; echo "b0: $?"
### break-errexit
set -e
pick() { local f; for f in nosuch.fa small.fa; do [[ -s $f ]] && break; done; echo "picked $f"; }
pick
for s in a b c; do [[ $s == b ]] && break; done
echo "after loop"
### end
n=1; echo $((n++)) | cat; echo "n=$n"; c=0; log() { echo "[$((++c))] $*" | tee -a log.txt; }; log one; log two; echo "c=$c"; unset x; : ${x:=5} | cat; echo "[${x-unset}]"; a=(p q); i=0; echo "${a[i++]}" | cat; echo "i=$i"; y=1; cat a.txt | head -n $((y+=1)) | wc -l; echo "y=$y"
n=1; echo $((n++)); echo "n=$n"; (( n++ )) | cat; echo "n=$n"; m=1; { echo $((m++)); } | cat; echo "m=$m"; k=1; echo a | { read -r v; echo $((k++)); }; echo "k=$k"; s=1; if echo $((s++)) | grep -q 1; then echo "s=$s"; fi; t=1; while echo $((t++)) | grep -q 9; do :; done; echo "t=$t"
### exit-in-pipeline
exit 9 | cat; echo "still here $? ${PIPESTATUS[*]}"; f() { return 7 | cat; echo "rc=$? ${PIPESTATUS[*]}"; }; f; true | exit 3 | cat; echo "$? ${PIPESTATUS[*]}"; exit 4 | exit 5; echo "$? ${PIPESTATUS[*]}"; echo x | exit 6; echo "last $?"; { exit 3; } | cat; echo "$? ${PIPESTATUS[*]}"
### end
### exit-in-pipeline-errexit
set -e; exit 9 | cat; echo "goes on $?"
### end
### source-unset
set -uo pipefail
cat > config.sh <<'C'
OUT=$OUTDIR/results
echo "config loaded: $OUT"
C
. ./config.sh
echo "script goes on with OUT=[${OUT-unset}] rc=$?"
### end
### source-unset-in-function
set -u
printf 'echo "t: $NOPE"\n' > t.sh
load() { . ./t.sh; echo "load goes on"; }; load; echo "after load $?"
### end
### source-ok-and-need
set -u
printf 'A=1\nB=${A:-x}\necho "sourced A=$A B=$B"\n' > ok.sh
. ./ok.sh; echo "after rc=$?"
printf 'echo "${X:?X must be set}"\necho next\n' > need.sh
( . ./need.sh ); echo "sub rc=$?"
X=1; . ./need.sh; echo "rc=$?"
### end
### heredoc-unset
set -u
cat <<EOF
x: $undef
EOF
echo "rc=$? after"
cat > f.txt <<EOF
y: $undef2
EOF
echo "rc=$?"
cat <<< "hs: $undef3"
echo "rc=$? after here-string"
f() { cat <<EOF
in function: $undef
EOF
echo "f goes on rc=$?"; }
f; echo "after f rc=$?"
x=$(cat <<EOF
in cs: $undef
EOF
); echo "after cs rc=$? [$x]"
echo "plain: $undef4"
echo "not reached"
### end
### heredoc-unset-errexit
set -eu
cat <<EOF
x: $undef
EOF
echo "not reached"
### end
### heredoc-unset-loop
set -u
while read -r l; do echo "$l"; done <<EOF
loop: $undef
EOF
echo "after loop rc=$?"
### end
bash -s -- one "two words" <<< 'echo "$# [$1] [$2]"'; printf 'echo "$# [$1]"\n' > t.sh; bash -- t.sh a b; bash -s - p q <<< 'echo "$# [$1]"'; bash -c 'echo "$0 $1"' -- x; bash -e -- t.sh z
declare -A cfg=([ref]=~/big/ref.fa [out]=~/out); echo "${cfg[ref]}|${cfg[out]}"; a=([0]=~/x ~/y [5]=~); echo "${a[0]}|${a[1]}|${a[5]}"; declare -A q; q=([k]=~/v); q[j]=~/w; q+=([z]=~/zz); echo "${q[k]}|${q[j]}|${q[z]}"; f() { local -A L=([k]=~/lv); echo "${L[k]}"; local -a M=([0]=~/mv); echo "${M[0]}"; }; f; declare -A s=(k1 ~/kv k2 "v 2" k3); echo "${s[k1]}|${s[k2]}|[${s[k3]}]|${#s[@]}"
shopt -s globstar; for d in **/; do echo "[$d]"; done; dirs=(**/); echo "${#dirs[@]}"; echo d1/**/ ; echo **/x.txt; echo ** | wc -w; shopt -u globstar; echo */
wc < <(cat a.txt); wc -lc < <(cat a.txt); echo "$(wc < <(cat a.txt))"; wc < a.txt; cat a.txt | wc
command -v ls nosuch > /dev/null; echo "a $?"; command -v nosuch ls > /dev/null; echo "b $?"; command -v nosuch nosuch2; echo "c $?"; command -V nosuch ls > /dev/null 2>&1; echo "d $?"; type ls nosuch > /dev/null 2>&1; echo "f $?"; type -t ls nosuch; echo "h $?"; command -v cd if nosuch; echo "$?"
{ time -- true; } 2>&1 | sed 's/[0-9]/N/g'; stdbuf true 2>&1 | head -n 1; echo "j ${PIPESTATUS[0]}"; stdbuf -oX true 2>&1; echo "k $?"; stdbuf -o L true; echo "l $?"; stdbuf -o1M -e0 -iL true 2>&1 | head -n 1; echo "m ${PIPESTATUS[0]}"; stdbuf -o 4096 -e 0 echo fine; stdbuf --output=L --error=0 echo fine2
set -- a b c; echo "${!#:-none}" "${!#}" "${!#%c}x" "${!#/c/C}"; set --; echo "${!#:-none}" | sed 's|.*/||'; set -- x.fastq.gz; echo "${!#%.gz}" "${!#:+has}"
x=straße; echo "${x^^}" "${x^}" "${x,,}"; declare -u up=straße; echo "$up"; y='ÀÉÎ õü ǆ'; echo "${y,,}" "${y^^}"; z=İstanbul; echo "${z,,}" | od -An -tx1 | tr -s ' '; w="hello wORLD"; echo "${w^^}" "${w,,}" "${w^}" "${w~~}" "${w@U}" "${w@u}" "${w@L}"
while getopts "a:b" o -a 1 -b; do :; done; echo "[${OPTARG-unset}] $OPTIND"; OPTIND=1; while getopts ":a:" o -a; do echo "$o $OPTARG"; done; echo "[${OPTARG-unset}]"
''')

more('empty-names-carriage-returns-bash-options', r'''
ls "" 2>&1; echo "rc=$?"; cp a.txt "" 2>&1; echo "rc=$?"; mv a.txt "" 2> /dev/null; echo "rc=$?"; ls a.txt; stat "" 2>&1; du "" 2>&1; echo "rc=$?"; truncate -s 0 "" 2>&1; echo "rc=$?"; nl "" a.txt 2>&1; touch "" 2>&1; mkdir "" 2>&1; rm "" 2>&1; rm -f ""; echo "rc=$?"; rmdir "" 2>&1; cd ""; echo "cd rc=$?"; ls | wc -l
OUT=""; mv b.txt "$OUT" 2> /dev/null || echo "mv refused"; cp in.txt "$OUT" 2> /dev/null || echo "cp refused"; mkdir -p "$OUT" 2> /dev/null || echo "mkdir refused"; touch "$OUT" 2> /dev/null || echo "touch refused"; rm -rf "$OUT"; echo "rm -rf rc=$?"; ls | wc -l; [[ -s b.txt && -s in.txt ]] && echo "files kept"; pwd | sed 's|.*/||'
du -s "" d1 2>&1 | cut -f 2; echo "rc=${PIPESTATUS[0]}"; stat -c %n "" a.txt 2>&1; echo "rc=$?"; sha256sum "" a.txt 2>&1 | cut -c1-20; realpath "" a.txt 2>&1 | sed 's|.*/||'; tee "" x1 < a.txt 2>&1 | head -n 2; cat x1 | wc -l; head -n 1 "" a.txt 2>&1; tac "" a.txt 2>&1 | head -n 2; wc -l "" a.txt 2>&1
printf 'echo one\r\necho two\r\n' > w1.sh; bash w1.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'x=5\r\necho "[$x]"\r\n' > w2.sh; bash w2.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'if true; then\r\n  echo yes\r\nfi\r\n' > w3.sh; bash w3.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'echo a\r\n\r\necho b\r\n' > w4.sh; bash w4.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"
printf 'for f in a b; do\r\n  echo "$f"\r\ndone\r\n' > w5.sh; bash w5.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'cd d1\r\npwd\r\n' > w6.sh; bash w6.sh 2>&1 | sed 's|/.*/||' | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'set -euo pipefail\r\necho ok\r\n' > w7.sh; bash w7.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf '#!/bin/bash\r\nwc -l a.txt\r\n' > w8.sh; bash w8.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"
printf 'f() {\r\n  echo in f\r\n}\r\nf\r\n' > w9.sh; bash w9.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'cat <<EOF\r\nbody\r\nEOF\r\necho after\r\n' > w10.sh; bash w10.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'VAR=value\r\nexport VAR\r\necho "[$VAR]"\r\n' > w11.sh; bash w11.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; bash -c $'echo c1\r\necho c2' 2>&1 | cat -A; printf 'echo sourced\r\n' > w12.sh; source w12.sh 2>&1 | cat -A; eval $'echo e1\r' | cat -A
printf '# comment\r\necho after comment\r\n' > w13.sh; bash w13.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'echo "quoted\r\nstill quoted"\r\n' > w14.sh; bash w14.sh 2>&1 | cat -A; printf 'grep -c alpha a.txt\r\n' > w15.sh; bash w15.sh 2>&1 | cat -A; echo "rc=${PIPESTATUS[0]}"; printf 'n=$(wc -l < a.txt)\r\necho "n=$n"\r\n' > w17.sh; bash w17.sh 2>&1 | cat -A; printf 'mkdir -p out\r\nls -d out*\r\n' > w18.sh; bash w18.sh 2>&1 | cat -A; ls | cat -A | grep -i out
printf 'a,b\r\nc,d\r\n' > c.csv; while IFS=, read -r x y; do printf '[%s][%s]\n' "$x" "$y" | cat -A; done < c.csv; x=$(printf 'v\r'); echo "${#x}"; for w in $(cat c.csv); do echo "$w" | cat -A; done; mapfile -t L < c.csv; echo "${#L[0]}"; read -r first < c.csv; [[ $first == "a,b" ]] && echo same || echo "differs (${#first})"; tr -d '\r' < c.csv | while IFS=, read -r x y; do echo "[$y]"; done; sed 's/\r$//' c.csv | cat -A
bash -a -c 'echo "a: $-"'; bash -f -c 'echo "f: $-" *'; bash -C -c 'echo "C: $-"'; bash -E -c 'echo "E: $-"'; bash -euo pipefail -c 'echo "combo: $-"; shopt -o -p pipefail'; bash -eu -o pipefail -c 'echo "sep: $-"'; bash +e -c 'echo "plus: $-"'; bash -s a b <<< 'echo "s: $1 $2 $-"'; echo 'echo "piped: $0 $-"' | bash; echo 'echo "piped args: $1"' | bash -s -- x; bash -C -c 'echo x > a.txt' 2>&1 | sed 's/^.*: line [0-9]*: //'; bash -a -c 'V=1; bash -c "echo exported: \$V"'
bash -q -c 'echo q' 2>&1 | sed -n '1,2p'; echo "rc=${PIPESTATUS[0]}"; bash --nosuchlong -c 'echo q' 2>&1 | sed -n '1,2p'; echo "rc=${PIPESTATUS[0]}"; bash -o nosuchopt -c 'echo q' 2>&1; echo "rc=$?"; bash -O nosuchshopt -c 'echo q' 2>&1; echo "rc=$?"; bash -e nosuch.sh 2>&1; echo "rc=$?"; bash nosuch.sh 2>&1; echo "rc=$?"; bash d1 2>&1; echo "rc=$?"; bash -x -c 'echo traced' 2>&1; bash -v -c 'echo verbose' 2>&1; bash -n -c 'echo not run'; echo "rc=$?"
bash -c 'f() echo x; f' 2>&1; echo "rc=$?"; bash -c 'function g echo x; g' 2>&1; echo "rc=$?"; bash -c 'f() if true; then echo if-body; fi; f; g() (echo sub-body); g; h() [[ -n x ]]; h; echo "h=$?"; k() ((1 > 2)); k; echo "k=$?"; w() for i in 1 2; do echo "for $i"; done; w; c() case x in x) echo case-body;; esac; c; u() until true; do :; done; u; echo "u=$?"; r() { echo redirected; } > r.txt; r; cat r.txt'
od -cz a.txt 2>&1 | sed -n '1p'; od --bogus a.txt 2>&1 | sed -n '1p'; od -cAn -N 4 a.txt; od -An -c -N 3 a.txt; od -bAd -N 2 a.txt
### dollar-dash
echo "script: $-"; ( echo "subshell: $-" ); echo "cs: $(echo $-)"; set -eu; echo "eu: $-"; set +e; echo "u: $-"; f() { echo "fn: $-"; }; f; bash -c 'echo "c: $-"; (echo "c-sub: $-")'; case $- in *i*) echo interactive;; *) echo "not interactive";; esac
exit 0
### end
### windows-script
cat > win.sh <<'W'
#!/usr/bin/env bash
set -euo pipefail
OUT=results
mkdir -p "$OUT"
for s in a b; do
  wc -l < "$s.txt" > "$OUT/$s.count"
done
cat "$OUT"/*.count
echo "done"
W
sed 's/$/\r/' win.sh > win_crlf.sh
bash win.sh; echo "unix rc=$?"
bash win_crlf.sh 2>&1 | cat -A | head -n 6; echo "windows rc=${PIPESTATUS[0]}"
sed -i 's/\r$//' win_crlf.sh; bash win_crlf.sh | tail -n 1; cmp win.sh win_crlf.sh && echo "same again"
exit 0
### end
''')

more('quotes-inside-braces', r'''
unset u; echo "1 ${u:-'a}b'}"; echo 2 ${u:-'a}b'}; x='a{{S}}b'; echo "3 ${x//'{{S}}'/Z}"; echo 4 ${x//'{{S}}'/Z}; x='a}b'; echo "5 ${x//'}'/Z}"; echo "6 ${x%'}'*}"
unset u; echo "7 ${u:-{a,b}}"; echo "8 ${u:-a{b}c}"; echo "9 ${u:-"a}b"}"; echo 11 ${u:-$'a}b'}; x="it's"; echo "12 ${x//\'/Q}"; echo "13 ${u:-a\}b}"
unset u; echo "14 ${u:+'x'}|${u:-`echo '}'`}|${u:-$(echo '}')}"; x=abc; echo "15 ${x/b/'}'}" ${x/b/'}'}; echo "${u:-$'tab\there'}" | od -An -c | tr -s ' '
out='Sample: {{SAMPLE}} has {{READS}}'; SAMPLE=NA12878; READS=200; out=${out//'{{SAMPLE}}'/$SAMPLE}; out=${out//'{{READS}}'/$READS}; echo "$out"; t="a{b}c"; echo "${t//'{'/[}" "${t//'}'/]}" "${t//[\{\}]/_}" "${t#*'{'}" "${t%'}'*}"
v="x'y"; echo "${v//\'/}" "${v//"'"/Q}" ${v//\'/-}; w='a"b'; echo "${w//\"/}" ${w//'"'/Q}; j='{"k": "v"}'; echo "${j//'"'/}" "${j#'{'}" "${j%'}'}"
### brace-quote-errors
unset u
echo "ok ${u:-fine}"
echo "16 ${u:-'}"
echo "17 not reached?"
### end
''')

more('tilde-in-path', r'''
mkdir -p ~/bin2; printf '#!/bin/bash\necho tool2-ran "$@"\n' > ~/bin2/mytool2; chmod +x ~/bin2/mytool2; PATH=~/bin2:$PATH; mytool2 a; env mytool2 b; which mytool2; echo x | xargs mytool2; timeout 5 mytool2 c; export PATH; bash -c 'mytool2 d'; rm -rf ~/bin2
echo "$(< ~/w/a.txt)" | head -n 1; cat <<< ~/x | sed 's|.*/||'; x=$(<~/w/a.txt); echo "${x%%$'\n'*}"; echo ~/w* | sed 's|.*/||'; a=~/w; echo "${a##*/}"; [[ ~/w -ef $HOME/w ]] && echo same; [ ~ = "$HOME" ] && echo eq
touch -d '2024-03-05 12:34:56' a.txt; touch -d '2023-11-30 01:02:03' b.txt; TZ=UTC diff -c a.txt b.txt | head -n 2; TZ=UTC LC_ALL=C diff -c a.txt b.txt | head -n 2; TZ=UTC LC_ALL=C diff -u a.txt b.txt | head -n 2; TZ=UTC diff -u a.txt b.txt | head -n 2
''')

more('control-characters-read-exec', r'''
echo $'\cA\cZ\c[' | od -An -tx1; echo $'a\c?b' | od -An -tx1; x=$'\ca'; printf '%s' "$x" | od -An -tx1; echo $'tab\there \\c literal'; echo $'x\cIy' | od -An -c | tr -s ' '
### exec-not-found
echo before
(exec nosuchcmd); echo "sub rc=$?"
f() { echo fn; }; (exec f); echo "fn rc=$?"
exec nosuchcmd2
echo "not reached"
### end
### exec-found
echo before
exec echo replaced
echo "not reached"
### end
### exec-in-pipeline
echo a | (exec cat); echo "rc=$?"
x=$(exec echo inner); echo "[$x]"
(exec > e.txt; echo to-file); cat e.txt
if (exec true); then echo yes; fi
(exec false) || echo "false rc=$?"
### end
''')

more('arrays-given-a-text', r'''
a=(x y z); a=new; echo "${a[@]}|${#a[@]}"; declare -p a; b=(x y); b+=tail; echo "${b[@]}"; declare -p b; c=(1 2 3); c=; echo "[${c[0]}] ${#c[@]}"; unset c; c=plain; c[1]=second; declare -p c
declare -A m=([k]=v); m=scalar; declare -p m | tr ' ' '\n' | sort | tr '\n' ' '; echo; echo "${m[0]}|${m[k]}|${#m[@]}"; m+=more; echo "${m[0]}"
f() { local -a L=(p q); L=one; echo "${L[*]}"; }; f; d=(1 2 3); read -r d <<< "viaread"; declare -p d; e=(1 2 3); for e in A B; do :; done; declare -p e; g=(1 2 3); printf -v g '%s' fmt; declare -p g
h=(1 2 3); h=$(echo sub); echo "${h[@]}"; export i=(1 2); i=x; echo "${i[@]}"; j=(a b c); (( j = 5 )); echo "${j[@]}"; (( j++ )); echo "${j[@]}"; let j+=10; echo "${j[@]}"; k=(a b c); k="${k[*]} d"; echo "${k[@]}|${#k[@]}"
declare -a n; n=first; n+=(second); echo "${n[@]}|${#n[@]}"; declare -i num=(1 2); num=7+1; echo "${num[@]}"; g() { local a=inner; echo "$a|${#a[@]}"; }; a=(o1 o2); g; echo "${a[@]}"; h() { local -a a; a=x; a+=(y); echo "${a[@]}"; }; h; echo "${a[@]}"
files=(one two three); files="$(printf '%s\n' "${files[@]}" | sort | head -n 1)"; echo "$files|${files[@]}|${#files[@]}"; unset files; files="one"; echo "${#files[@]} ${files[0]}"; arr=(a b); arr=(); arr=z; declare -p arr; s=text; s=(now an array); s=back; declare -p s
bash nosuch.sh 2>&1; echo "rc=$?"; x=$(bash nosuch.sh 2>&1); echo "[$x]"; if ! bash nosuch.sh 2> /dev/null; then echo failed; fi; bash -e nosuch.sh 2>&1; echo "rc=$?"; bash d1 2>&1; echo "rc=$?"; bash -n nosuch.sh 2>&1; echo "rc=$?"; f() { bash nosuch2.sh; }; f 2>&1; echo "rc=$?"; bash -c 'bash nosuch4.sh' 2>&1; echo "rc=$?"; bash -c 'source nosuch5.sh' 2>&1; echo "rc=$?"; printf 'bash nosuch6.sh\nnosuchcmd2\n' > inner.sh; bash inner.sh 2>&1; echo "rc=$?"
### arrays-in-scripts
#!/usr/bin/env bash
set -euo pipefail
samples=(a b)
declare -A counts=()
total=0
for s in "${samples[@]}"; do
  n=$(wc -l < "$s.txt")
  counts[$s]=$n
  total=$((total + n))
done
samples+=("in")
last=${samples[-1]}
samples=("${samples[@]:1}")
for k in "${!counts[@]}"; do echo "$k ${counts[$k]}"; done | sort
echo "total=$total last=$last left=${samples[*]} n=${#samples[@]}"
files=(*.txt); first=$files; files=("${files[@]/%.txt/.bak}"); echo "$first ${files[0]} ${#files[@]}"
read -r -a parts <<< "x y z"; parts=("${parts[@]^^}"); echo "${parts[*]}"
i=0; while read -r line; do lines[i++]=$line; done < a.txt; echo "${#lines[@]} ${lines[1]}"
args=(-n 2); head "${args[@]}" a.txt | tail -n 1
unset 'lines[0]'; echo "${#lines[@]} ${!lines[*]}"
lines=("${lines[@]}"); echo "${!lines[*]}"
### end
### loop-variable-and-arrays
set -u
names=(alpha beta)
for names in one two; do :; done
echo "${names[@]}|${#names[@]}"
opts=(-l -c); opts="-w"; wc "${opts[@]}" a.txt
declare -A seen=([a]=1); for seen in x; do :; done; echo "${seen[0]}|${seen[a]}|${#seen[@]}"
out=(); out=$(echo captured); echo "${out[0]}|${#out[@]}"
IFS=, read -r col rest <<< "a,b,c"; cols=(1 2 3); IFS=, read -r cols <<< "x,y"; echo "${cols[@]}"
### end
''')

more('paths-name-by-name-and-the-working-folder', r'''
rm -f a.txt/; echo "rc=$?"; rm a.txt/ 2> /dev/null; echo "rc=$?"; rm -rf a.txt/; echo "rc=$?"; echo hi > a.txt/; echo "rc=$?"; echo hi >> a.txt/; echo "rc=$?"; : > a.txt/; echo "rc=$?"; truncate -s 0 a.txt/ 2> /dev/null; echo "rc=$?"; sort -o a.txt/ b.txt 2> /dev/null; echo "rc=$?"; echo x | tee a.txt/ 2> /dev/null; echo "rc=${PIPESTATUS[1]}"; chmod 600 a.txt/ 2> /dev/null; echo "rc=$?"; wc -c < a.txt; ls | wc -l
cat a.txt/; echo "rc=$?"; wc -l a.txt/; echo "rc=$?"; head -n 1 a.txt/; echo "rc=$?"; grep alpha a.txt/; echo "rc=$?"; md5sum a.txt/; echo "rc=$?"; stat -c %s a.txt/; echo "rc=$?"; cut -c1 a.txt/; echo "rc=$?"; tail -n 1 a.txt/; echo "rc=$?"; sed -n 1p a.txt/; echo "rc=$?"; diff a.txt/ b.txt; echo "rc=$?"; cat < a.txt/; echo "rc=$?"; ls a.txt/; echo "rc=$?"; du a.txt/; echo "rc=$?"; realpath a.txt/; echo "rc=$?"; cd a.txt/; echo "rc=$?"; rmdir a.txt/; echo "rc=$?"
[ -f a.txt/ ]; echo "f $?"; [ -e a.txt/ ]; echo "e $?"; [ -d a.txt/ ]; echo "d $?"; [ -s a.txt/ ]; echo "s $?"; [[ -r a.txt/ ]]; echo "r $?"; [ -d d1/ ]; echo "dir $?"; [ -e d1/. ]; echo "dot $?"; [ -f d1/../a.txt ]; echo "up $?"; [ -e nosuch/../a.txt ]; echo "missing-up $?"; [ -f a.txt/../b.txt ]; echo "file-up $?"; basename a.txt/; dirname a.txt/
cp a.txt/ c.txt 2> /dev/null; echo "rc=$?"; cp b.txt a.txt/ 2> /dev/null; echo "rc=$?"; mv a.txt/ c.txt 2> /dev/null; echo "rc=$?"; mv b.txt a.txt/ 2> /dev/null; echo "rc=$?"; touch a.txt/ 2>&1; echo "rc=$?"; mkdir a.txt/ 2> /dev/null; echo "rc=$?"; find a.txt/ -delete 2> /dev/null; echo "rc=$?"; source a.txt/ 2> /dev/null; echo "rc=$?"; bash a.txt/ 2>&1; echo "rc=$?"; ./a.txt/ 2> /dev/null; echo "rc=$?"; wc -c < a.txt; wc -c < b.txt; ls | wc -l
rm -f nosuch/../a.txt; echo "rc=$?"; rm nosuch/../a.txt; echo "rc=$?"; echo x > nosuch/../t.txt; echo "rc=$?"; cat nosuch/../a.txt; echo "rc=$?"; cp a.txt nosuch/../c.txt; echo "rc=$?"; ls nosuch/..; echo "rc=$?"; cd nosuch/..; echo "rc=$?"; mkdir nosuch/../made; echo "rc=$?"; cat a.txt/../b.txt; echo "rc=$?"; rm -f a.txt/../b.txt; echo "rc=$?"; wc -l < d1/sub/../../a.txt; cat d1/../a.txt | wc -l; ls | wc -l; wc -c < a.txt
mkdir -p nosuch/../made2; ls -d made2 nosuch; touch nosuch/../tt; ls tt; touch new/; echo "rc=$?"; ls new 2> /dev/null; echo x > new2/; echo "rc=$?"; ls new2 2> /dev/null; mkdir new3/; ls -d new3; mkdir -p new4/sub/; ls -d new4/sub; cp a.txt new5/ 2> /dev/null; echo "rc=$?"; mv a.txt new6/ 2> /dev/null; echo "rc=$?"; cp -r d1 new7/; ls new7; mv d2 new8/; ls -d new8; ls -d d1/sub/..; rm -rf a.txt/.; echo "rc=$?"; rm -rf a.txt/..; echo "rc=$?"; wc -c < a.txt
cat ./a.txt | wc -l; cat .//a.txt | wc -l; cat ././a.txt | wc -l; cat d1/../d1/x.txt | wc -l; wc -l d1/./x.txt; ls d1/. | wc -l; cd d1/sub/..; pwd | sed 's|.*/||'; cd ./../d2/; pwd | sed 's|.*/||'; cd ..; ls ./d1/../a.txt; realpath -m nosuch/../x | sed 's|.*/||'; realpath d1/../a.txt | sed 's|.*/||'
mkdir -p e/f; cd e; mv . ../g 2> /dev/null; echo "rc=$?"; mv ./ ../g 2> /dev/null; echo "rc=$?"; mv f/. ../g 2> /dev/null; echo "rc=$?"; mv f/.. ../g 2> /dev/null; echo "rc=$?"; mv . x 2> /dev/null; echo "rc=$?"; cd ..; mv e/. g 2> /dev/null; echo "rc=$?"; mv e/f/.. g 2> /dev/null; echo "rc=$?"; ls -d e g 2> /dev/null; cp -r e/. g; ls g; cd e; cp -r . ../g2; ls ../g2
mkdir work; cd work; touch f1; rm -rf ../work; echo "rc=$?"; echo x > f.txt; echo "write rc=$?"; mkdir sub 2> /dev/null; echo "mkdir rc=$?"; cat ../a.txt | head -n 1; cd ..; echo "cd rc=$?"; pwd | sed 's|.*/||'; ls -d work 2> /dev/null; echo "ls rc=$?"
mkdir w4; cd w4; rm -rf "$PWD"; echo "rc=$?"; touch t 2> /dev/null; echo "touch rc=$?"; wc -l < ../a.txt; cd ~/w; ls -d w4 2> /dev/null; echo "ls rc=$?"; mkdir w5; cd w5; rmdir ../w5; echo "rmdir rc=$?"; cd ..; pwd | sed 's|.*/||'
cd d1; ( cd sub ); cd - > /dev/null; pwd | sed 's|.*/||'; cd d1; x=$(cd sub; pwd); echo "${OLDPWD##*/}"; cd sub | cat; echo "${OLDPWD##*/}"; bash -c "cd sub"; echo "${OLDPWD##*/}"; f() { cd sub; }; f; echo "${OLDPWD##*/} ${PWD##*/}"; cd - > /dev/null; echo "${PWD##*/}"
"$TOOLX" view 2> /dev/null; echo "rc=$?"; x=""; if "$x" 2> /dev/null; then echo yes; else echo "else $?"; fi; "" 2> /dev/null; echo "rc=$?"; echo a | "" 2> /dev/null | cat; echo "${PIPESTATUS[1]} ${PIPESTATUS[2]}"; $NOPE; echo "unquoted rc=$?"; "$A$B" x 2> /dev/null; echo "rc=$?"; "" 2>&1 | sed 's/^.*line [0-9]*: //; s/^bash: //'
a=(1 2 3); : "${a[7]:=seven}"; declare -p a; declare -A conf=([a]=1); : "${conf[b]:=2}"; echo "${conf[b]:-unset} ${#conf[@]}"; unset b; : "${b[0]:=zero}"; declare -p b; k=x; declare -A n; : "${n[$k]:=0}"; n[$k]=$(( n[$k] + 1 )); declare -p n; unset c; echo "${c[2]:=two}|${c[2]}|${#c[@]}"; s=plain; : "${s[1]:=more}"; declare -p s
x=$'5\r'; if [ "$x" -ge 5 ] 2> /dev/null; then echo yes; else echo "no rc=$?"; fi; [ " 5" -eq 5 ] && echo lead; [ "5 " -eq 5 ] && echo trail; [ $'5\n' -eq 5 ] 2> /dev/null; echo "nl rc=$?"; [ $'\n5' -eq 5 ]; echo "lead nl rc=$?"; [[ " 5 " -eq 5 ]] && echo dbl; y=$'3\n'; echo $((y + 1)); z=" 7 "; echo $((z * 2)); echo $(( 1 +	2 )); w=$'\t8'; echo $((w + 1))
mapfile -d: -t P <<< "a:b:c"; echo "${#P[@]}"; mapfile -td, R <<< "a,b"; echo "${#R[@]}"; mapfile -t -n2 S < a.txt; echo "${#S[@]}"; mapfile -ts1 T < a.txt; echo "${T[0]}"; mapfile -t -d '' Z < <(printf 'p\0q\0'); echo "${#Z[@]} ${Z[1]}"; mapfile -z X 2>&1 | head -n 1 | sed 's/^.*line [0-9]*: //; s/^bash: //'
a=(1 2 3); a=tmp printenv a; echo "rc=$?"; a=tmp bash -c 'echo "[$a]"'; a=tmp eval 'echo "$a ${a[@]}"'; echo "${a[@]}"; f() { echo "$a|${a[*]}"; }; a=tmp f; echo "${a[@]}"; declare -A m=([k]=v); m=x env | grep -c '^m=x$'; echo "${m[k]}"
echo x > a.txt > ""; echo "rc=$?"; wc -c < a.txt; echo y > new.txt > ""; ls new.txt; echo z > b.txt > nodir/y; wc -c < b.txt; echo q > in.txt > $nope; wc -c < in.txt
gzip d1 2>&1; echo "rc=$?"; ls d1.gz 2> /dev/null; gzip -k a.txt; gzip -k a.txt < /dev/null; echo "rc=$?"; gzip -kf a.txt; echo "rc=$?"; gzip nosuch.txt; echo "rc=$?"; zcat nosuch2; echo "rc=$?"; ls a.txt*
od -Anc <<< abc; od -An -c <<< abc; od -Ad -c <<< ab | head -n 1; od -Ax <<< ab | head -n 1; od -cAn <<< ab
printf 'getopts v o && echo v=1\necho "OPTIND=$OPTIND rest=$*"\n' > xo; chmod +x xo; OPTIND=3 ./xo -v x; export OPTIND=5; bash -c 'echo $OPTIND'
bash -c -e 'echo $-'; bash -e -c 'echo $-'; bash -c -x 'echo traced' 2>&1; bash -c -eu 'echo "$0 $1 $-"' name arg; bash -e d1 2> /dev/null; echo "rc=$?"
export -z x 2>&1 | sed 's/^.*line [0-9]*: //; s/^bash: //'; declare -z x 2>&1 | sed 's/^.*line [0-9]*: //; s/^bash: //'; declare -z y; echo "rc=$?"; export -q y; echo "rc=$?"
### set-invalid-letter
set -ez 2> /dev/null; echo "after: $-"
set -uz 2> /dev/null; echo "[$nope] after"
set -e -z 2> /dev/null; echo "after2: $-"
set -z 2>&1 | sed 's/^.*line [0-9]*: //'
set -eo nosuch 2> /dev/null; echo "not reached: $-"
### end
### too-many-arguments
f() { return 1 2; echo "in f after"; }
f 2> /dev/null; echo "same line: not reached"
echo "next line rc=$?"
g() { return x 2> /dev/null; echo "in g after"; }; g; echo "after g rc=$?"
( exit 1 2 ) 2> /dev/null; echo "subshell rc=$?"
exit 3 4 2> /dev/null; echo "same line: not reached"
echo "the script goes on rc=$?"
exit abc 2> /dev/null
echo "not reached"
### end
### arithmetic-carriage-return
printf 'NA1,25\r\nNA2,10\r\n' > sheet.csv
pass=0; fail=0; errors=0
while IFS=, read -r name depth; do
  if (( depth >= 20 )) 2> /dev/null; then pass=$((pass + 1)); else fail=$((fail + 1)); fi
done < sheet.csv
echo "pass=$pass fail=$fail"
x=$'5\r'
echo $((x + 1)) 2> /dev/null
echo "after rc=$?"
tr -d '\r' < sheet.csv | while IFS=, read -r name depth; do (( depth >= 20 )) && echo "$name ok"; done
printf 'exit 3\r\n' > c.sh; bash c.sh 2> /dev/null; echo "rc=$?"
### end
### cleanup-in-working-folder
set -euo pipefail
work=$(mktemp -d -p "$PWD")
trap 'rm -rf "$work"' EXIT
cd "$work"
printf 'a\nb\n' > part.txt
wc -l < part.txt
cp part.txt ../kept.txt
rm -rf "$work"
echo "cleaned rc=$?"
cd ..
ls kept.txt
### end
### subshell-cd-and-return
set -e
mkdir -p proj/data proj/out
cd proj
( cd data && printf '1\n2\n' > n.txt )
wc -l < data/n.txt > out/n.count
cd - > /dev/null
cat proj/out/n.count
pushd proj > /dev/null; ( cd data; pwd | sed 's|.*/||' ); popd > /dev/null
pwd | sed 's|.*/||'
### end
### sed-in-place-then-move
set -euo pipefail
printf 'chr1\t1\nchr2\t2\n' > t.tsv
sed -i 's/chr/Chr/' t.tsv
gzip t.tsv
gunzip t.tsv.gz
cat t.tsv
sed -i '1d' t.tsv; mv t.tsv t2.tsv
sort a.txt -o t.tsv; head -n 1 t.tsv
rm t.tsv; [ -e t.tsv ] || echo "gone"; cat t.tsv 2> /dev/null || echo "really gone"
seq 3 > t.tsv; wc -l < t.tsv
### end
''')


# ---- October 2026, the fifth round: random sequences of file commands pointed at these ----
# A file that cannot be opened fails its own command, not the pipeline it stands in (the status of a writer BEFORE
# such a command depends on timing in real bash – those forms are in t_typical2.py); what a block, a loop or a
# function prints into a file is in the file when the next command looks; gzip leaves alone what has its suffix,
# and only decompresses what has it; a copy keeps its bytes whatever happens to the original; exec NAME.
more('pipelines-where-a-file-cannot-be-opened', r'''
sort < nosuch.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
tr a-z A-Z < nosuch.txt | head -c 30 | md5sum; echo "rc=$? ${PIPESTATUS[*]}"
n=$(grep -c a < nosuch.txt | cat); echo "n=[$n] rc=$?"
set -o pipefail; sort < nosuch.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
cat < nosuch.txt | wc -c > count.txt; echo "rc=$? ${PIPESTATUS[*]}"; cat count.txt
wc -l < nosuch.txt | cat > made.txt; echo "rc=$?"; ls made.txt; wc -c < made.txt
sort < nosuch.txt 2> /dev/null | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
{ sort < nosuch.txt; echo "in block $?"; } | wc -l; echo "rc=$?"
while read -r l; do echo "$l"; done < nosuch.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
if sort < nosuch.txt | grep -q x; then echo yes; else echo "no $?"; fi
sort < nosuch.txt | tee copy.txt | wc -l; echo "rc=$?"; ls copy.txt; wc -c < copy.txt
for f in a.txt nosuch.txt b.txt; do tr a-z A-Z < "$f" | wc -l; done; echo "rc=$?"
cut -f 1 < nosuch.tsv | sort | uniq -c | sort -k1,1nr | head -n 3; echo "rc=$? ${PIPESTATUS[*]}"
### setE_pipeline_with_missing_input
set -e
n=$(sort < nosuch.txt | wc -l)
echo "still here n=$n"
### end
### pipefail_missing_input
set -eo pipefail
n=$(sort < nosuch.txt | wc -l) || echo "caught $?"
echo "n=[$n]"
m=$(sort < nosuch.txt | wc -l)
echo "not reached"
### end
''')

more('pipelines-where-a-file-cannot-be-opened-more', r'''
sort 2> /dev/null < nosuch.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
sort 2> err.txt < nosuch.txt; echo "rc=$?"; sed 's/^.*line [0-9]*: //; s/^bash: //' err.txt
sort 2>> err.txt < nosuch.txt; sort 2>> err.txt < nosuch2.txt; wc -l < err.txt
sort > out1.txt < nosuch.txt; echo "rc=$?"; ls out1.txt
sort < nosuch.txt > out2.txt; echo "rc=$?"; ls out2.txt 2>&1 | sed 's/^ls: //'
echo x > nodir/a > made.txt; echo "rc=$?"; ls made.txt 2>&1 | sed 's/^ls: //'
echo x > made2.txt > nodir/a; echo "rc=$?"; ls made2.txt; wc -c < made2.txt
echo keep > c.txt; set -C; echo b > c.txt > other.txt; echo "rc=$?"; ls other.txt 2>&1 | sed 's/^ls: //'; cat c.txt
echo x > d1 > after.txt; echo "rc=$?"; ls after.txt 2>&1 | sed 's/^ls: //'
cat < nosuch1 < a.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
cat < a.txt < nosuch2 | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
wc -l < a.txt < b.txt; echo "rc=$?"
sort < nosuch.txt | sort < nosuch2.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
sort nosuch.txt | wc -l; echo "rc=$? ${PIPESTATUS[*]}"
grep -c alpha < a.txt | cat > n1.out; cat n1.out; grep -c alpha < nosuch | cat > n2.out; echo "rc=$?"; wc -c < n2.out
head -n 1 < nosuch.txt > first.txt 2> errs.txt; echo "rc=$?"; ls first.txt errs.txt 2>&1 | sed 's/^ls: //'
head -n 1 2> errs2.txt > first2.txt < nosuch.txt; echo "rc=$?"; ls first2.txt errs2.txt; wc -l < errs2.txt
x=$(cat < nosuch.txt | tr a-z A-Z); echo "[$x] rc=$?"
if cat < nosuch.txt | grep -q .; then echo yes; else echo "no $?"; fi
cat < nosuch.txt | while read -r l; do echo "got $l"; done; echo "rc=$? ${PIPESTATUS[*]}"
cat < nosuch.txt | { wc -l; echo "block"; }; echo "rc=$?"
set -o pipefail; cat a.txt | sort < nosuch.txt | wc -l || echo "failed $?"
seq 100000 | wc -l < nosuch | cat; echo "rc=$? ${PIPESTATUS[*]}"
: | cat < nosuch | cat; echo "rc=$? ${PIPESTATUS[*]}"
true | cat > nodir/z | cat; echo "rc=$? ${PIPESTATUS[*]}"
### counts_of_files_that_may_be_missing
set -euo pipefail
for f in a.txt missing.txt b.txt; do
  n=$(wc -l < "$f" || true)
  echo "$f: ${n:-none}"
done
total=$(cat a.txt b.txt | wc -l)
echo "total $total"
m=$(sort < missing.txt | uniq | wc -l) || echo "pipeline failed with $?"
echo "m=[$m]"
echo "end"
### end
### missing_input_without_pipefail
set -e
lines=$(tr -d '\r' < missing.csv | wc -l)
echo "lines=$lines"
if [ "$lines" -eq 0 ]; then echo "nothing to do"; exit 3; fi
echo "not reached"
### end
''')

more('output-of-a-block-read-inside-the-block', r'''
{ echo start; wc -l < out.log; } > out.log; cat out.log
for i in 1 2 3; do echo "line $i"; wc -l < loop.log; done > loop.log; cat loop.log
{ echo a; echo b; } >> app.log; { echo c; grep -c . app.log; } >> app.log; cat app.log
exec 3> fd.log; echo one >&3; wc -l < fd.log; echo two >&3; exec 3>&-; cat fd.log
echo a > t.log; (echo b; cat t.log) >> t.log; cat t.log; echo "rc=$?"
f() { echo x; wc -c < f.log; }; f > f.log; cat f.log
{ echo one; cp blk.txt snap.txt; echo two; } > blk.txt; cat snap.txt; echo ---; cat blk.txt
{ echo one; ls -l blk2.txt | awk '{ print $5 }'; [ -s blk2.txt ] && echo "has size"; } > blk2.txt; cat blk2.txt
while read -r l; do echo "$l"; wc -l < w.log; done < names.txt > w.log; cat w.log
if true; then echo yes; cat c.log; fi > c.log 2>&1; cat c.log | sed 's/cat: .*: /cat: /'
{ echo "to err" >&2; wc -c < e.log; } 2> e.log; cat e.log
{ seq 3; md5sum < seq.txt | cut -c 1-8; } > seq.txt; cat seq.txt
### exec_log_read_back
exec > run.log 2>&1
echo "step 1"
echo "step 2"
wc -l < run.log
cp run.log copy.log
echo "step 3"
grep -c step run.log
### end
### exec_log_then_show
exec 3>&1 > run.log 2>&1
echo "work"
ls nosuch
exec 1>&3 3>&-
echo "the log has $(wc -l < run.log) lines"
cat run.log
### end
### exec_append_log
echo "old" > keep.log
exec >> keep.log
echo "new 1"
tail -n 1 keep.log
echo "new 2"
wc -l < keep.log
### end
### log_function_and_summary
log() { echo "[log] $*" >> pipeline.log; }
log "start"
for s in A B; do log "sample $s"; done
n=$(grep -c sample pipeline.log)
log "samples: $n"
cat pipeline.log
### end
### block_log_tail
{
  echo "begin"
  echo "middle"
  tail -n 1 block.log
  echo "end"
} > block.log 2>&1
cat block.log
### end
### exec_tee_log
exec > >(tee tee.log) 2>&1
echo "first"
echo "second"
### end
''')

more('gzip-suffixes-folders-statuses', r'''
gzip -k a.txt; gzip -f a.txt.gz; echo "rc=$?"; ls a.txt*
gzip -k b.txt; gzip b.txt.gz; echo "rc=$?"; ls b.txt*
cp in.txt x.gz; gzip x.gz; echo "rc=$?"; ls x.gz*
cp in.txt y.gz; gunzip y.gz; echo "rc=$?"; ls y*
cp in.txt z.txt; gunzip z.txt; echo "rc=$?"; ls z*
gzip -k nums.txt; cp nums.txt.gz n.tgz; gunzip n.tgz; echo "rc=$?"; ls n.t*
gzip -c names.txt > n.Z; gunzip n.Z; echo "rc=$?"; ls n.*
for f in d1/*; do [ -f "$f" ] && gzip -f "$f"; done; ls d1; for f in d1/*; do [ -f "$f" ] && gzip -f "$f"; done; echo "rc=$?"; ls d1
gzip -k tab.tsv; gzip -dk tab.tsv.gz; echo "rc=$?"; gzip -dkf tab.tsv.gz; echo "rc=$?"; ls tab*
gzip -c a.txt b.txt | gzip -dc | wc -l; gzip -c < a.txt | gunzip | wc -l; gzip < a.txt > q.gz; gunzip < q.gz | wc -l; zcat q.gz | wc -l
cp -p a.txt p.txt; [ a.txt -nt p.txt ] || [ p.txt -nt a.txt ] || echo "same time"; sed -i 1d p.txt; [ p.txt -nt a.txt ] && echo "newer now"
cp in.txt z.txt; gunzip -f z.txt; echo "rc=$?"; ls z*
gzip -d -c z.txt | wc -c; echo "rc=${PIPESTATUS[0]}"; gzip -dcf z.txt | wc -c; echo "rc=${PIPESTATUS[0]}"
gzip -t z.txt; echo "rc=$?"; gzip -k a.txt; gzip -t a.txt.gz; echo "rc=$?"
gzip -k b.txt; rm b.txt; gunzip b.txt; echo "rc=$?"; ls b.txt*
gzip -k nums.txt; gunzip nums.txt; echo "rc=$?"; ls nums*
cp a.txt.gz x.tgz; gzip x.tgz; echo "rc=$?"; cp a.txt.gz X.GZ; gzip X.GZ; echo "rc=$?"; ls x* X*
gzip -k a.txt.gz; echo "rc=$?"; ls a.txt*
gzip -c a.txt.gz | wc -c | sed "s/[0-9]*/N/"; echo "rc=${PIPESTATUS[0]}"
gzip a.txt.gz in.txt names.txt.gz names.txt; echo "rc=$?"; ls in.txt* names.txt*
gzip *; echo "rc=$?"; ls | head -n 30
gzip -d *; echo "rc=$?"; ls | head -n 30
gunzip *.gz; echo "rc=$?"; gunzip *.gz; echo "rc=$?"
gzip -q a.txt.gz; echo "rc=$?"; gunzip -q csv.csv; echo "rc=$?"
gzip -fk a.txt; gzip -fk a.txt; echo "rc=$?"; gzip -k a.txt < /dev/null; echo "rc=$?"
echo text | gzip > piped.gz; gzip -dc piped.gz; echo text | gzip -c | gunzip -c; echo text | gzip | zcat
gzip nosuch.txt in.txt; echo "rc=$?"; ls in.txt*; gunzip nosuch.gz in.txt.gz; echo "rc=$?"; ls in.txt*
gzip d1/x.txt d2; echo "rc=$?"; ls d1; gzip -r d1 2>&1 | head -n 2; echo "rc=${PIPESTATUS[0]}"
gzip -k a.txt; gzip -q a.txt.gz d1 csv.csv; echo "rc=$?"; ls a.txt* csv*
gzip -dq in.txt; echo "rc=$?"; gzip -dq in.txt d2; echo "rc=$?"
gzip -k b.txt; for s in tgz taz Z z GZ Gz; do cp b.txt.gz "n.$s"; gunzip "n.$s"; echo "$s rc=$?"; ls n* | tr "\n" " "; echo; rm -f n n.*; done
cp b.txt.gz n-gz; gunzip n-gz; echo "rc=$?"; ls n*; rm -f n*; cp b.txt.gz n_z; gunzip n_z; echo "rc=$?"; ls n*; rm -f n*; cp b.txt.gz n-z; gunzip -k n-z; echo "rc=$?"; ls n*; rm -f n*
cp b.txt.gz data_z; gzip data_z; echo "rc=$?"; cp in.txt sample-gz; gzip sample-gz; echo "rc=$?"; gzip -f sample-gz; echo "rc=$?"; ls data* sample*
cp b.txt.gz n.tgz; echo x > n.tar; gunzip n.tgz; echo "rc=$?"; gunzip -f n.tgz; echo "rc=$?"; ls n.*; md5sum < n.tar; md5sum < b.txt
gunzip nosuch; echo "rc=$?"; gunzip nosuch.gz; echo "rc=$?"; gunzip nosuch.tgz; echo "rc=$?"; gzip nosuch.gz; echo "rc=$?"
gzip -k names.txt; rm names.txt; gunzip -k names.txt; echo "rc=$?"; ls names*; gzip -dc names.txt | wc -l; echo "rc=${PIPESTATUS[0]}"; zcat names.txt | wc -l; gzip -t names.txt; echo "rc=$?"
gzip -c a.txt > .gz; gunzip .gz; echo "rc=$?"; ls -a | grep -c "^\.gz$"
gzip nums.txt; gzip -d nums.txt.gz nums.txt.gz; echo "rc=$?"; ls nums*
cp tab.tsv t1; cp tab.tsv t2; gzip t1 t2 t1; echo "rc=$?"; ls t1* t2*
cp tab.tsv u1; gzip -k u1; gzip u1 csv.csv; echo "rc=$?"; ls u1* csv*
gzip -r d1; echo "rc=$?"; find d1 | sort; gzip -r d1; echo "rc=$?"; find d1 | sort
gzip -dr d1; echo "rc=$?"; find d1 | sort; cat d1/sub/z.txt
gzip -r d2 a.txt nosuch; echo "rc=$?"; find d2 | sort; ls a.txt*
gunzip -r d2/ a.txt.gz; echo "rc=$?"; find d2 | sort
gzip -rk d1; gzip -rc d1 | gzip -d | wc -l; gzip -rt d1; echo "rc=$?"; gzip -rd d1; echo "rc=$?"; gzip -rdf d1; echo "rc=$?"; find d1 | sort
mkdir -p e/f/g; gzip -r e; echo "rc=$?"; gzip --recursive .; echo "rc=$?"; ls | head -n 8; gunzip -r . ; echo "rc=$?"; ls | head -n 8
''')

more('copies-keep-their-own-bytes', r'''
tr 'a-m' '\200-\214' < in.txt > bin.dat; cp bin.dat c1.dat; truncate -s 4 bin.dat; wc -c < c1.dat; wc -c < bin.dat
tr 'a-m' '\200-\214' < in.txt > bin.dat; cp bin.dat c2.dat; printf "\377\376\n" > bin.dat; wc -c < c2.dat; wc -c < bin.dat
tr 'a-m' '\200-\214' < in.txt > bin.dat; mv bin.dat m3.dat; printf "\377\n" > bin.dat; wc -c < m3.dat; wc -c < bin.dat
tr 'a-m' '\200-\214' < in.txt > bin.dat; mv bin.dat m4.dat; truncate -s 2 bin.dat; od -An -c bin.dat; wc -c < m4.dat
tr 'a-m' '\200-\214' < in.txt > part.aa; mv part.aa keep.dat; head -n 2 nums.txt | split -l 1 - part.; wc -c < keep.dat; cat part.aa
seq 60000 > big.txt; cp big.txt c6.txt; truncate -s 10 big.txt; wc -c < c6.txt; wc -c < big.txt
seq 60000 > big.txt; cp big.txt c7.txt; echo short > big.txt; wc -c < c7.txt; echo more >> c7.txt; wc -c < big.txt; tail -n 2 c7.txt
tr 'a-m' '\200-\214' < in.txt > bin.dat; mv bin.dat old.dat; printf "AAEC/w==" | base64 -d > bin.dat; wc -c < old.dat; wc -c < bin.dat
tr 'a-m' '\200-\214' < in.txt > bin.dat; cp bin.dat c9.dat; truncate -s 4 c9.dat; wc -c < bin.dat; wc -c < c9.dat
seq 60000 > big.txt; mv big.txt moved.txt; truncate -s 5 big.txt; wc -c < moved.txt; md5sum < moved.txt
seq 60000 > big.txt; cp big.txt a.copy; cp a.copy b.copy; rm big.txt; mv b.copy big.txt; truncate -s +3 a.copy; wc -c < big.txt; wc -c < a.copy; md5sum < big.txt
seq 60000 > big.txt; cp big.txt keep.txt; head -n 4 big.txt | split -l 2 - big.txt; ls big.txt*; wc -c < keep.txt
seq 60000 > big.txt; mkdir sub; cp big.txt sub/; mv sub sub2; truncate -s 0 big.txt; printf "\000\001" > big.txt; wc -c < sub2/big.txt; md5sum < sub2/big.txt
seq 60000 > big.txt; cp big.txt one.txt; cp big.txt two.txt; printf "x\377y\n" > big.txt; cmp one.txt two.txt; echo "cmp=$?"; wc -c < one.txt; wc -c < big.txt
tr 'a-m' '\200-\214' < in.txt > bin.dat; cp bin.dat bin2.dat; { printf "\001\002"; cat a.txt; } > bin.dat; wc -c < bin2.dat; wc -c < bin.dat
''')

more('exec-of-a-program-that-is-not-there', r'''
bash -c 'exec nosuchcmd-xyz 2> /dev/null; echo after rc=$?'; echo "rc=$?"
bash -c 'exec nosuchcmd-xyz 2> nodir/x; echo after rc=$?'; echo "rc=$?"
bash -c 'exec nosuchcmd-xyz 2> err.txt; echo after'; echo "rc=$?"; sed 's/^.*line [0-9]*: //' err.txt
bash -c 'exec nosuchcmd-xyz > out.txt 2>&1; echo after'; echo "rc=$?"; sed 's/^.*line [0-9]*: //' out.txt
bash -c 'exec nosuchcmd-xyz; echo after' 2>&1 | sed 's/^.*line [0-9]*: //'; echo "rc=${PIPESTATUS[0]}"
bash -c 'shopt -s execfail; exec nosuchcmd-xyz 2> /dev/null; echo after rc=$?'; echo "rc=$?"
bash -c 'exec d1 2> /dev/null; echo after rc=$?'; echo "rc=$?"
bash -c 'exec ./nosuch 2> /dev/null; echo after rc=$?'; echo "rc=$?"
bash -c 'exec "" 2> /dev/null; echo after rc=$?'; echo "rc=$?"
( exec nosuchcmd-xyz 2> /dev/null; echo "not here" ); echo "rc=$?"
exec nosuchcmd-xyz 2> /dev/null; echo "after failed exec rc=$?"
''')


# ---- October 2026: from the fifth independent check (aimed at files only) and from mending what it found ----
# Two files of the same name copied or moved into one folder (the second must not replace the first); a slash behind
# a name that is no folder; a file that a command writes by name while an empty > FILE stands on the same command
# (the file keeps what was written); exec with >> onto a large file and onto bytes; gzip keeps the mode of a file;
# >> FILE 2>> FILE in the order written; zgrep with several files; find -exec that removes the folder it stands
# in front of; names behind nosuch/..; sed -i on many files in one call; a file keeps its mode when it is added to.
more('copies-and-moves-of-the-same-name', r'''
mkdir all; mv d1/x.txt d2/x.txt all/; echo "rc=$?"; ls d1 d2; cat all/x.txt
mkdir all; cp d1/x.txt d2/x.txt all/; echo "rc=$?"; cat all/x.txt
mkdir all; cp -f d1/x.txt d2/x.txt all/; echo "rc=$?"; cat all/x.txt; mv -f d1/y.txt d2/y.txt all/; echo "rc=$?"; ls d2
mkdir all; cp -t all d1/x.txt d2/x.txt; echo "rc=$?"; cat all/x.txt; mv -t all d1/y.txt d2/y.txt; echo "rc=$?"; ls d2 all
mkdir all; cp -v d1/x.txt d2/x.txt d1/y.txt all/; echo "rc=$?"; ls all
mkdir all; mv -v d1/x.txt d2/x.txt d2/only2.txt all/; echo "rc=$?"; ls all d2
mkdir all; cp d1/*.txt d2/*.txt all/ 2> /dev/null; echo "rc=$?"; ls all; cat all/x.txt
mkdir all; echo old > all/x.txt; cp d1/x.txt all/; echo "rc=$?"; cat all/x.txt; cp d2/x.txt all/; echo "rc=$?"; cat all/x.txt
mkdir all; echo old > all/x.txt; cp d1/x.txt d2/x.txt all/; echo "rc=$?"; cat all/x.txt
mkdir all; cp -r d1 d2 all/; echo "rc=$?"; find all | sort | tr '\n' ' '
mkdir all; cp -r d1/. d2/. all/; echo "rc=$?"; find all | sort | tr '\n' ' '; cat all/x.txt
mkdir -p all p; cp -r d1 p/; cp -r d1 p/d1 all/; echo "rc=$?"; find all | sort | tr '\n' ' '
mkdir -p all p; cp -r d1 p/; mv d1 p/d1 all/; echo "rc=$?"; ls all p
mkdir all; cp a.txt a.txt all/; echo "rc=$?"; ls all
mkdir all; cp a.txt ./a.txt all/; echo "rc=$?"; ls all
mkdir all; mv a.txt b.txt all/; mv all/a.txt all/b.txt .; echo "rc=$?"; ls a.txt b.txt
mkdir run1 run2 merged; echo 1 > run1/s.txt; echo 2 > run2/s.txt; echo 3 > run2/t.txt; mv run1/*.txt run2/*.txt merged/; echo "rc=$?"; ls run1 run2 merged; cat merged/s.txt
mkdir all; find d1 d2 -name 'x.txt' | sort | xargs cp -t all; echo "rc=$?"; cat all/x.txt
mkdir all; find d1 d2 -name 'x.txt' -exec cp {} all/ \; ; echo "rc=$?"; ls all
mkdir all; for f in d1/x.txt d2/x.txt; do cp "$f" all/; done; echo "rc=$?"; cat all/x.txt
cp d1/x.txt d2/x.txt nums.txt; echo "rc=$?"
cp a.txt b.txt; cp in.txt b.txt; echo "rc=$?"; head -n 1 b.txt
''')

more('a-slash-behind-the-destination', r'''
echo b > ts2; cp -r d1 ts2/; echo "rc=$?"; cat ts2; ls | sort | tr '\n' ' '
echo b > ts2; cp a.txt ts2/; echo "rc=$?"; cat ts2
echo b > ts2; mv a.txt ts2/; echo "rc=$?"; cat ts2; ls a.txt
echo b > ts2; mv d1 ts2/; echo "rc=$?"; cat ts2; ls -d d1
cp -r d1 newdir/; echo "rc=$?"; ls newdir
cp a.txt newfile/; echo "rc=$?"; ls newfile 2>&1 | sed 's/^ls: //'
mv a.txt newname/; echo "rc=$?"; ls | sort | tr '\n' ' '
mv d1 newdir2/; echo "rc=$?"; ls newdir2; ls -d d1 2>&1 | sed 's/^ls: //'
cp -r d1/ d2/; echo "rc=$?"; find d2 | sort | tr '\n' ' '
cp -r d1/. d2/; echo "rc=$?"; find d2 | sort | tr '\n' ' '
cp a.txt d1/; echo "rc=$?"; ls d1
mkdir -p x/y; cp -r x/y/ z; ls z | wc -l; cp -r x/ x2/; find x2 | sort | tr '\n' ' '
touch f; mkdir f/; echo "rc=$?"; mkdir newd/; ls -d newd; mkdir -p deep/er/; ls -d deep/er
rmdir d1/sub/; echo "rc=$?"; rm -r d2/; echo "rc=$?"; ls -d d2 2>&1 | sed 's/^ls: //'
echo b > ts2; cp -r d1 d2 ts2/; echo "rc=$?"; cat ts2
echo b > ts2; cp -t ts2/ a.txt; echo "rc=$?"; cat ts2
echo b > ts2; cp -rT d1 ts2/; echo "rc=$?"; cat ts2
echo b > ts2; mkdir -p ts2/sub; echo "rc=$?"; cat ts2
echo b > ts2; touch ts2/new; echo "rc=$?"; echo x > ts2/new2; echo "rc=$?"; cat ts2
echo b > ts2; cp a.txt ts2/copy.txt; echo "rc=$?"; mv b.txt ts2/moved.txt; echo "rc=$?"; ls b.txt; cat ts2
echo b > ts2; sort a.txt -o ts2/s.txt; echo "rc=$?"; sed 's/a/b/' a.txt > ts2/out; echo "rc=$?"; cat ts2
echo b > ts2; find ts2/ -type f | wc -l; ls ts2/ 2>&1 | sed 's/^ls: //'; [ -e ts2/ ]; echo "e=$?"; [ -f ts2 ]; echo "f=$?"
cp -r d1 d1/; echo "rc=$?"; find d1 | sort | tr '\n' ' '
mv d1 d1/; echo "rc=$?"; mv d1/ d1x; echo "rc=$?"; ls -d d1x; mv d1x/ d2/; echo "rc=$?"; ls d2
mv a.txt d1/sub/; echo "rc=$?"; ls d1/sub; mv d1/sub/ .; echo "rc=$?"; ls -d sub
''')

more('files-written-by-name-under-an-empty-redirection', r'''
f() { echo inner >> log.txt; }; f > log.txt; cat log.txt
log() { echo "[log] $*" >> run.log; }; main() { log start; log end; }; main > run.log 2>&1; cat run.log
{ ls nosuch 2>> err.log; echo done >> err.log; } 2> err.log; wc -l < err.log
cp a.txt F.txt > F.txt; cat F.txt; mv a.txt G.txt > G.txt; cat G.txt
sort -o S.txt a.txt > S.txt; cat S.txt; sort a.txt -o T.txt > T.txt 2>&1; cat T.txt
awk '{ print > "A.txt" }' a.txt > A.txt; cat A.txt; sed -n 'w W.txt' a.txt > W.txt; cat W.txt
truncate -s 5 a.txt > U.txt; wc -c < U.txt; truncate -s 3 V.txt > V.txt; wc -c < V.txt
head -n 4 b.txt | split -l 2 - part. > part.aa; cat part.aa
for i in 1 2; do echo "it $i" >> L.txt; done > L.txt; cat L.txt
while read -r l; do echo "$l" >> W2.txt; done < names.txt > W2.txt; wc -l < W2.txt
if true; then echo yes >> I.txt; fi > I.txt; cat I.txt; case x in x) echo c >> C.txt ;; esac > C.txt; cat C.txt
( echo sub >> P.txt ) > P.txt; cat P.txt; bash -c 'echo child >> Q.txt' > Q.txt; cat Q.txt
eval 'echo ev >> E.txt' > E.txt; cat E.txt; echo "echo src >> R.txt" > lib.sh; source lib.sh > R.txt; cat R.txt
echo a.txt | xargs -I{} cp {} X.txt > X.txt; cat X.txt; find . -name 'b.txt' -exec cp {} Y.txt \; > Y.txt; cat Y.txt
f() { echo first; echo inner >> log3.txt; echo last; }; f >> log3.txt; cat log3.txt
echo keep > K.txt; f() { echo inner >> K.txt; }; f >> K.txt; cat K.txt
cat a.txt | while read -r l; do echo "$l" >> pipe.txt; done > pipe.txt; cat pipe.txt
{ echo o1; } > both.txt 2>&1; { echo b1 >> both.txt; } > both.txt 2>&1; cat both.txt
echo data > D.txt; : > D.txt; wc -c < D.txt; echo data > D2.txt; true > D2.txt; wc -c < D2.txt; echo data > D3.txt; { :; } > D3.txt; wc -c < D3.txt
echo data > D4.txt; sort /dev/null > D4.txt; wc -c < D4.txt; echo data > D5.txt; grep nomatch a.txt > D5.txt; wc -c < D5.txt; echo data > D6.txt; f() { :; }; f > D6.txt; wc -c < D6.txt
echo data > D7.txt; sort /dev/null >> D7.txt; cat D7.txt; grep nomatch a.txt >> D7.txt; cat D7.txt
seq 60000 > big.txt; exec 3>> big.txt; echo "via fd 3" >&3; exec 3>&-; wc -l < big.txt; tail -n 1 big.txt
printf 'caf\351\n' > lat.log; exec 3>> lat.log; echo one >&3; echo two >&3; exec 3>&-; od -An -c lat.log
echo start > mix.log; exec 3>> mix.log; echo one >&3; seq 60000 >> mix.log; echo two >&3; exec 3>&-; wc -l < mix.log; tail -n 1 mix.log; sed -n '2p' mix.log
seq 60000 > big2.txt; exec 3>> big2.txt; echo a >&3; wc -l < big2.txt; echo b >&3; cp big2.txt copy.txt; echo c >&3; exec 3>&-; wc -l < big2.txt; wc -l < copy.txt
### exec_tee_append_big_log
seq 60000 > big.log
exec > >(tee -a big.log) 2>&1
echo "new line"
echo "second"
### end
### exec_err_append
seq 60000 > errs.log
exec 2>> errs.log
ls nosuch
echo "to out"
ls nosuch2
wc -l < errs.log
### end
''')

more('gzip-attributes-shared-files-messages-zgrep', r'''
printf '#!/bin/bash\necho run\n' > t.sh; chmod +x t.sh; gzip t.sh; gunzip t.sh.gz; ./t.sh; echo "rc=$?"
chmod 600 b.txt; gzip b.txt; stat -c %a b.txt.gz; gunzip b.txt.gz; stat -c %a b.txt
chmod 750 in.txt; gzip -r d1 in.txt; stat -c %a in.txt.gz; gunzip -r d1 in.txt.gz; stat -c %a in.txt; cp in.txt x.tgz; chmod 700 x.tgz; gzip -c in.txt > x.tgz; gunzip x.tgz; stat -c %a x.tar
{ echo out1; echo err1 >&2; echo out2; } >> log.txt 2>> log.txt; cat log.txt
f() { echo o1; echo e1 >&2; echo o2; }; f >> l2.txt 2>> l2.txt; cat l2.txt
{ echo o1; ls nosuch; echo o2; } >> l3.txt 2>> l3.txt; sed 's/^ls: .*/ls-message/' l3.txt
for i in 1 2; do echo "o$i"; echo "e$i" >&2; done >> l5.txt 2>> l5.txt; cat l5.txt
bash -c 'echo o1; echo e1 >&2; echo o2' >> l4.txt 2>> l4.txt; cat l4.txt
sort > out.txt 2>&1 < nosuch; sed 's/^.*line [0-9]*: //; s/^bash: //' out.txt
x=$(sort 2>&1 < nosuch); echo "[${x##*: }]"
sort 2>&1 < nosuch | wc -l; ls 2>&1 > nodir/x | wc -l
sort &> both.txt < nosuch; wc -l < both.txt; sort >> app.txt 2>&1 < nosuch; sort >> app.txt 2>&1 < nosuch2; wc -l < app.txt
sort 2>&1 > o2.txt < nosuch | wc -l; ls o2.txt; sort > o3.txt < nosuch 2>&1; wc -c < o3.txt
gzip -k a.txt b.txt; zgrep -l BETA a.txt.gz b.txt.gz; zgrep -c alpha a.txt.gz b.txt.gz; zgrep -H gamma a.txt.gz; zgrep alpha a.txt; echo "rc=$?"
gzip -k a.txt b.txt; zgrep -h alpha a.txt.gz b.txt.gz; zgrep -n delta a.txt.gz b.txt.gz; echo "rc=$?"; zgrep nomatch a.txt.gz b.txt.gz; echo "rc=$?"
gzip -k a.txt; zgrep alpha nosuch.gz a.txt.gz 2> /dev/null; echo "rc=$?"; zgrep -q beta a.txt.gz; echo "rc=$?"; zgrep -c beta a.txt.gz a.txt
gzip -c a.txt | zgrep -c alpha; zgrep -c alpha < a.txt; zgrep -i BETA a.txt b.txt; zgrep -e alpha -e delta b.txt
''')

more('find-exec-on-folders-and-globs-behind-dots', r'''
find . -name sub -exec rm -r {} \; ; echo "rc=$?"; find . | sort | tr '\n' ' '
find . -name sub -exec rm -r {} \; 2>&1 | sed 's/^find: .*: /find: /'; echo "rc=${PIPESTATUS[0]}"
find . -type d -name 'd*' -exec rm -rf {} \; 2> /dev/null; echo "rc=$?"; ls
find . -type d -name sub -exec mv {} moved \; 2> /dev/null; echo "rc=$?"; ls moved
find . -depth -name sub -exec rm -r {} \; ; echo "rc=$?"; find . -name d2 -prune -exec rm -r {} \; ; echo "rc=$?"; ls
find . -name sub -exec rm -r {} + ; echo "rc=$?"; ls d1
find d1 -type d -empty -exec rmdir {} \; 2> /dev/null; echo "rc=$?"; mkdir -p e1/e2; find e1 -type d -exec rmdir {} \; 2> /dev/null; echo "rc=$?"; ls -d e1 e1/e2 2>&1 | sed 's/^ls: //'
find . -maxdepth 1 -name 'd1' -exec rm -r {} \; ; echo "rc=$?"; find . -name 'x.txt' -exec rm {} \; ; echo "rc=$?"
find d1 -name '*.txt' -delete; echo "rc=$?"; find d1 | sort | tr '\n' ' '
echo nosuch/../*.txt | wc -w; echo a.txt/../*.txt | wc -w; echo d1/../*.txt | wc -w; echo ./*.txt | wc -w; echo ../w/*.txt | wc -w
shopt -s nullglob; for f in nosuch/../*; do echo "it $f"; done; echo end; for f in d1/sub/../*.txt; do echo "$f"; done
ls nosuch/../*.txt 2>&1 | sed 's/^ls: //'; echo d1/./x.t* d1/sub/../y.t*; echo */../a.txt
rm nosuch/../*.txt 2> /dev/null; echo "rc=$?"; ls *.txt | wc -l
mkdir gone; cd gone; rmdir ../gone; echo ../*.tsv; echo ./* ; echo *
''')

more('sed-i-on-many-files-modes-kept-by-append-exec-descriptors', r'''
for i in $(seq 40); do echo "v$i alpha" > f$i.txt; done; sed -i 's/alpha/beta/' f*.txt; echo "rc=$?"; grep -l alpha f*.txt | wc -l; grep -c beta f*.txt | grep -c ':1$'; ls | grep -c '^sed'
for i in $(seq 25); do printf 'a\nb\n' > g$i.tsv; done; sed -i '1d' g*.tsv; echo "rc=$?"; cat g*.tsv | sort | uniq -c | tr -s ' '
for i in 1 2 3; do cp a.txt c$i.txt; done; sed -i -e 's/alpha/A/' -e '$d' c1.txt c2.txt c3.txt a.txt; echo "rc=$?"; cat c1.txt c3.txt a.txt | tr '\n' ' '
mkdir many; for i in $(seq 30); do echo "x $i" > many/s$i.txt; done; find many -name '*.txt' | xargs sed -i 's/x/y/'; echo "rc=$?"; grep -c '^y' many/*.txt | grep -vc ':1$'; ls many | wc -l
for i in $(seq 12); do echo "line" > h$i.txt; done; sed -i.bak 's/line/LINE/' h*.txt; echo "rc=$?"; ls h*.bak | wc -l; cat h1.txt h12.txt h1.txt.bak
for i in $(seq 20); do echo "k=$i" > cfg$i.ini; done; sed -i 's/k=/key=/' cfg*.ini nosuch.ini 2> /dev/null; echo "rc=$?"; grep -c '^key=' cfg*.ini | grep -c ':1$'
for i in $(seq 40); do echo "v$i" > n$i.txt; done; for r in 1 2 3; do sed -i "s/^/$r/" n*.txt || echo "failed in round $r"; done; cat n7.txt n40.txt; ls | grep -c '^n'
chmod 600 a.txt; echo more >> a.txt; stat -c %a a.txt; chmod 640 b.txt; { echo x; echo y; } >> b.txt; stat -c %a b.txt; tail -n 2 b.txt
seq 60000 > big.txt; chmod 600 big.txt; echo more >> big.txt; stat -c %a big.txt; tail -n 1 big.txt; seq 3 >> big.txt; stat -c %a big.txt; wc -l < big.txt
printf 'caf\351\n' > lat.txt; chmod 640 lat.txt; echo more >> lat.txt; stat -c %a lat.txt; od -An -c lat.txt | tr -s ' '
chmod 755 in.txt; cat a.txt >> in.txt; stat -c %a in.txt; chmod 700 nums.txt; exec 3>> nums.txt; echo 7 >&3; exec 3>&-; stat -c %a nums.txt; tail -n 1 nums.txt
chmod 750 a.txt; sort b.txt >> a.txt; stat -c %a a.txt; chmod 600 nums.txt; printf 'x\377\n' >> nums.txt; stat -c %a nums.txt; wc -c < nums.txt; chmod 711 b.txt; echo t | tee -a b.txt > /dev/null; stat -c %a b.txt
exec 3> b.bin; printf '\377\376' >&3; printf 'x\n' >&3; exec 3>&-; od -An -c b.bin | tr -s ' '
exec 3> t.txt; echo one >&3; cat t.txt; echo two >&3; exec 3>&-; cat t.txt
exec 3> b2.bin; printf 'a\200b\n' >&3; wc -c < b2.bin; printf 'c\n' >&3; exec 3>&-; wc -c < b2.bin
TIMEFORMAT='%R'; t=$( { time sleep 0.3; } 2>&1 ); t=${t/./}; (( 10#$t >= 300 )) && echo "0.3 at least"; t=$( { time sleep 0.05; } 2>&1 ); t=${t/./}; (( 10#$t >= 50 )) && echo "0.05 at least"
### exec_append_big_log_seen
seq 60000 > big.log
exec 3>&1 >> big.log 2>&1
echo "new line"
ls nosuch
echo "last"
wc -l < big.log >&3
tail -n 3 big.log | sed 's/^ls: .*/ls-message/' >&3
### end
### exec_tee_append_then_read_when_written
printf 'x\377y\n' > bin.log
exec > >(tee -a bin.log)
echo "one"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do [ "$(wc -c < bin.log)" -ge 8 ] && break; sleep 0.1; done
wc -c < bin.log
echo "two"
### end
### exec_append_keeps_mode
seq 60000 > big.log
chmod 600 big.log
exec 3>&1 >> big.log
echo "new line"
stat -c %a big.log >&3
tail -n 1 big.log >&3
### end
''')


# ---- October 2026: from the sixth independent check (whole analyses on the real data) and from mending what it found ----
# grep -P: what grep -o shows after \K (also behind a greedy .*, in alternatives, in matches that follow on each other),
# possessive counts, Python's names for groups, comments, lines of context; "was something piped in?" – [ -p /dev/stdin ]
# and its kin; the time of a folder moves on when a name appears in it or goes (ls -td run_* | head -n 1, find -newer);
# seq 1 60000 | paste -sd+ | bc.
more('grep-P-what-is-shown-after-K-and-other-perl-patterns', r'''
echo "results/vcf/calls.vcf.gz" | grep -oP '.*/\K.*'; echo "human_CYP2C19:11616:G" | grep -oP '.*:\K.*'
echo "DP=12;MQ=60;DP=7" | grep -oP '.*DP=\K\d+'; echo "DP=12;MQ=60;DP=7" | grep -oP 'DP=\K\d+'
printf 'gene=CYP2C19;id=7\n' | grep -oP 'gene=\K[^;]+|id=\K\d+'; echo 1234 | grep -oP '\d\K\d'
printf 'one two  three\n' | grep -oP '\S+\s+\K\S+'; echo "a=1 b=22 c=333" | grep -oP '\w=\K\d+(?= |$)'
echo "x=1,y=22" | grep -oP '(?P<name>[a-z])=\d+'; echo "abab cdcd abcd" | grep -oP '(?P<p>\w\w)(?P=p)'
echo "Name=CYP2C19;Type=gene" | grep -oP 'Name=\K\w++'; echo "aaa" | grep -cP 'a++a'; echo "aaab" | grep -oP 'a++b'
echo "ab" | grep -oP 'a(?#comment)b'; echo "foobar" | grep -oP '(?>foo)bar'; echo "foobar" | grep -cP '(?>fo+)o'
printf 'a\nb\nc\nd\n' | grep -P -A1 'b'; printf 'a\nb\nc\nd\na\nx\n' | grep -nP -A1 'a'; printf 'a\nb\nc\nd\na\nx\n' | grep -oP -A1 'a'
printf 'a\nb\nc\nd\na\nx\n' | grep -P -B1 'd'; printf 'a\nb\nc\nd\na\nx\n' | grep -P -C1 'c'; printf 'a\nb\nc\nd\na\nx\n' | grep -P -1 'c'; printf 'a\nb\nc\nd\na\nx\n' | grep -P -m1 -A2 'a'
grep -P -A1 'l2' in.txt a.txt; grep -HnP -B1 'gamma' a.txt b.txt; grep -P --context=1 -n 'beta|BETA' a.txt b.txt; grep -cP -A1 'a' a.txt
grep -P -A1 'nomatch' a.txt; echo "rc=$?"; grep -P -A 1 -B 1 'beta' a.txt; grep -P --after-context=1 --before-context=0 'alpha' b.txt
grep -oP '(?<=chr)\d+' tab.tsv | sort -u; grep -oP '^\S+\t\K\d+' tab.tsv; grep -P '\t(?:A|C)\t' tab.tsv | cut -f 2; grep -cP '^chr1\t\d{3}\t' tab.tsv
grep -oP 'NA\d+(?=,\d+$)' csv.csv; grep -oP '^[^,]+,\K[^,]+' csv.csv; grep -P -o ',\K\d+$' csv.csv | paste -sd+ | bc
grep -oP '>\K\S+' small.fa; grep -oP '^>\S+\s+\K.*' small.fa; grep -vP '^>' small.fa | grep -oP '[GC]' | wc -l; grep -oP '(?i)acgt' small.fa | wc -l
echo "a.b*c" | grep -oP '\Qa.b*\E\w'; echo "a+b" | grep -cP 'a\+b'; echo "tab	here" | grep -cP '\t'; echo "x-y_z" | grep -oP '[\w\-]+'; echo "a/b" | grep -oP 'a\/b'; echo "50%" | grep -oP '\d+\%'
echo "1 22 333" | grep -oP '\d{2,}'; echo "1 22 333" | grep -oP '\d{2}'; echo "a{b}" | grep -oP 'a\{b\}'; echo "a{b}" | grep -oP 'a{b}'; echo "x{2}" | grep -oP 'x{2'
echo "foo123bar" | grep -oP '\d+\K\w+'; echo "foo123bar" | grep -oP 'foo\K'; echo "rc=$?"; echo "key: value" | grep -oP '^\w+:\s*\K.*$'; echo "a1b2" | grep -oP '[a-z]\K\d' | paste -sd,
printf 'l1\nl2\nl3\nl4\nl5\nl6\nl7\n' | grep -P -A1 -B1 'l2|l6'; printf 'l1\nl2\nl3\nl4\nl5\n' | grep -vP -A1 'l[1245]'; printf 'l1\nl2\nl3\n' | grep -P -A5 'l1' | wc -l
grep -oP 'DP=\K\d+' /dev/null; echo "rc=$?"; echo "DP=5" | grep -qP 'DP=\K\d+'; echo "rc=$?"
echo "aaa bbb" | grep -oP 'a*+'; echo "aab" | grep -oP 'a?+a'; echo "rc=$?"; echo "aab" | grep -oP 'a{1,2}+b'; echo "xyz" | grep -oP '[xy]++z'; echo "(a)" | grep -oP '\(\K[^)]+'
echo "GT:AD:DP 0/1:10,12:22" | grep -oP '\s\K[^:]+'; echo "chr10:96541616" | grep -oP ':\K\d+$'; echo "SM:NA12878 ID:x" | grep -oP 'SM:\K\S+'; echo "@RG	ID:a	SM:b" | grep -oP 'ID:\K[^\t]+'
''')

more('grep-P-classes-escapes-lookarounds-options', r'''
echo "ab x" | grep -oP 'a\Kb|x'
echo "a.b*c a.b*d" | grep -oP '\Qa.b*\E\w'; echo "a++" | grep -oP '\Qa+\E+'; echo "aXXb" | grep -oP 'a\QX\E{2}b'; echo "a.b" | grep -cP '\Q.\E'
echo "abc123_x" | grep -oP '[[:alpha:]]+'; echo "abc 123" | grep -oP '[[:digit:][:space:]]+' | wc -c; echo "a-b]c" | grep -oP '[\]\-]' | paste -sd,; echo "a^b" | grep -oP '[\^]'
echo "ABC" | grep -oP '\x41\x42'; echo "tab	x" | grep -oP '\x09x' | od -An -c | tr -s ' '; echo "é" | grep -cP '\x{e9}'; echo "aé" | grep -oP '\p{L}+'; echo "a1" | grep -oP '\P{L}'
echo "a,b;c" | grep -oP '[^,;]+' | paste -sd' '; echo "[x]" | grep -oP '\[\K[^\]]+'; echo "{x}" | grep -oP '\{\K[^}]+'; echo "a|b" | grep -oP 'a\|b'; echo 'a"b' | grep -oP 'a\"b'
echo "2026-10-05" | grep -oP '^\d{4}(?=-)'; echo "2026-10-05" | grep -oP '(?<=-)\d{2}$'; echo "foo.bar" | grep -oP '(?<!\.)\b\w+'; echo "price: 10 USD, 20 EUR" | grep -oP '\d+(?! USD)' | paste -sd,
echo "aaa" | grep -oP 'a*?'; echo "rc=$?"; echo "aaa" | grep -oP 'a+?'; echo "<a><b>" | grep -oP '<.+?>'; echo "<a><b>" | grep -oP '<.+>'; echo "ab12" | grep -oP '(\w)(\w)\d\d' | grep -cP '(.)\1'
echo "foo=bar; baz=qux" | grep -oP '(\w+)=(\w+)' | sed -n '2p'; echo "aa bb ab" | grep -oP '(\w)\1'; echo "aa bb ab" | grep -oP '(?<c>\w)\k<c>'; echo "abab" | grep -oP '(ab)\g1'; echo "abab" | grep -oP '(ab)\g{1}'
echo "line with trailing space " | grep -cP '\h$'; printf 'a\r\nb\n' | grep -cP 'a\R'; echo "x" | grep -cP '\Ax\z'; echo "a b" | grep -oP '\S\K\s\S'; echo "abc" | grep -oP '\Bb\B'
printf 'NA12878\t31\nNA12891\t27\n' | grep -P '^NA\d+\t3\d$' | cut -f 1; printf 'A\tB\n' | grep -oP '\t\K.'; printf '1\n22\n333\n' | grep -xP '\d{2,3}' | paste -sd,; printf 'foo\nfoobar\n' | grep -wP 'foo'
printf 'a\nb\n' | grep -nP 'b'; printf 'a\nb\n' | grep -vcP 'b'; printf 'a\nb\n' | grep -oP 'c'; echo "rc=$?"; grep -lP 'alpha' a.txt b.txt in.txt; grep -LP 'alpha' a.txt b.txt in.txt; grep -hP 'gamma' a.txt b.txt; grep -P 'x' nosuch.txt 2> /dev/null; echo "rc=$?"
grep -sP 'x' nosuch.txt a.txt; echo "rc=$?"; grep -P -m 2 'a' b.txt; grep -P -m1 -c 'a' b.txt; grep -onP 'l\d' in.txt | head -n 2; grep -P --max-count=1 --line-number 'l' in.txt
echo "DP=10;AF=0.5" | grep -oP 'AF=\K[\d.]+'; echo "0/1:22:10,12" | grep -oP '^[^:]+:\K\d+'; echo "ID=gene1;Name=CYP2C19;x" | grep -oP 'Name=\K[^;]+'; echo "reads: 7038 (100%)" | grep -oP '\d+(?= \()'
echo "aXbXc" | grep -oP 'X\K.' | paste -sd,; echo "k1=v1,k2=v2" | grep -oP '(?:^|,)\K\w+(?==)' | paste -sd,; echo "a  b" | grep -oP 'a\s*\Kb'; echo "mm" | grep -oP 'm\Km'; echo "abc" | grep -oP '(?=b)\K.'
''')

more('is-the-input-a-pipe-a-file-or-the-terminal', r'''
echo hello | { if [ -p /dev/stdin ]; then cat; else echo "no piped input: usage"; fi; }
echo x | [ -p /dev/stdin ]; echo "rc=$?"; [ -p /dev/stdin ] < a.txt; echo "rc=$?"; [ -f /dev/stdin ] < a.txt; echo "rc=$?"; [ -s /dev/stdin ] < a.txt; echo "rc=$?"; [ -s /dev/stdin ] < empty.txt; echo "rc=$?"
f() { if [[ -p /dev/stdin ]]; then wc -l; else echo "nothing piped"; fi; }; cat a.txt | f; f < a.txt
echo x | [[ -p /dev/stdin ]]; echo "rc=$?"; [[ -f /dev/stdin ]] < a.txt; echo "rc=$?"; echo x | [[ -f /dev/stdin ]]; echo "rc=$?"
echo x | { [ -p /dev/fd/0 ]; echo "rc=$?"; [ -p /proc/self/fd/0 ]; echo "rc=$?"; [ -e /dev/stdin ]; echo "rc=$?"; [ -r /dev/stdin ]; echo "rc=$?"; }
[ -p /dev/stdout ] | cat; echo "rc=${PIPESTATUS[0]}"; [ -c /dev/stdout ] | cat; echo "rc=${PIPESTATUS[0]}"
[ -p /dev/stdin ] <<< "here"; echo "rc=$?"; while read -r l; do [ -p /dev/stdin ] && echo "pipe $l"; done < <(echo a; echo b)
cat a.txt | while read -r l; do [ -p /dev/stdin ] && echo "piped: $l"; done; while read -r l; do [ -f /dev/stdin ] && echo "file: $l"; done < a.txt
read_input() { if [ -p /dev/stdin ] || [ -f /dev/stdin ]; then cat; else cat "$1"; fi; }; echo "from pipe" | read_input a.txt; read_input a.txt < b.txt | head -n 2 | tail -n 1
test -p /dev/stdin < /dev/null; echo "rc=$?"; test -c /dev/stdin < /dev/null; echo "rc=$?"; test -e /dev/null && test -c /dev/null && echo "null is a device"
### usage_or_stdin
#!/bin/bash
set -- names.txt
# reads names from a pipe, or from the file given as the first argument
if [ -p /dev/stdin ]; then
  input=$(cat)
elif [ -n "${1:-}" ] && [ -f "$1" ]; then
  input=$(cat "$1")
else
  echo "usage: $0 FILE   or   … | $0" >&2
  exit 2
fi
echo "$input" | sort | head -n 2
### end
''')

more('the-time-of-a-folder', r'''
mkdir run_1; sleep 0.05; mkdir run_2; sleep 0.05; mkdir run_3; sleep 0.05; echo result > run_1/result.txt; ls -td run_* | sed -n '1p'; [ run_1 -nt run_3 ] && echo newer || echo "NOT newer"
mkdir o; touch ref; sleep 0.05; echo x > o/a; [ o -nt ref ] && echo "new name: newer"; touch ref; sleep 0.05; echo y >> o/a; [ o -nt ref ] || echo "contents changed: not newer"; touch ref; sleep 0.05; rm o/a; [ o -nt ref ] && echo "removed: newer"
mkdir o; echo x > o/a; touch ref; sleep 0.05; mv o/a o/b; [ o -nt ref ] && echo "renamed inside: newer"; touch ref; sleep 0.05; mv o/b .; [ o -nt ref ] && echo "moved out: newer"; [ . -nt ref ] && echo "moved in: newer"
mkdir -p logs out; touch logs/start; sleep 0.05; echo 1 > out/one.txt; mkdir out/sub; find . -newer logs/start | sort | tr '\n' ' '
mkdir d; touch ref; sleep 0.05; sort a.txt -o d/sorted.txt; [ d -nt ref ] && echo "a program wrote into it: newer"; [ d -nt d/sorted.txt ] || echo "not newer than the file"; touch ref; sleep 0.05; sed -i 1d d/sorted.txt; [ d -nt ref ] && echo "sed -i: newer"
mkdir d; touch ref; sleep 0.05; touch d; [ d -nt ref ] && echo "touched"; touch ref; sleep 0.05; cp a.txt d/; [ d -nt ref ] && echo "cp: newer"; touch ref; sleep 0.05; cp b.txt d/a.txt; [ d -nt ref ] || echo "cp over: not newer"
mkdir d; touch ref; sleep 0.05; mkdir d/sub; [ d -nt ref ] && echo "mkdir inside: newer"; touch ref; sleep 0.05; echo z > d/sub/f; [ d -nt ref ] || echo "below sub: d not newer"; [ d/sub -nt ref ] && echo "sub newer"
mkdir d; echo 1 > d/f; touch ref; sleep 0.05; gzip d/f; [ d -nt ref ] && echo "gzip: newer"; touch ref; sleep 0.05; find d -name '*.gz' -delete; [ d -nt ref ] && echo "find -delete: newer"; touch ref; sleep 0.05; rmdir d; [ . -nt ref ] && echo "rmdir: newer"
mkdir r1 r2; sleep 0.05; touch r1/x; latest=$(ls -td r*/ | head -n 1); echo "latest: $latest"; sleep 0.05; touch r2/y; ls -td r1 r2 | tr '\n' ' '
''')

more('bc-long-sums', r'''
seq 1 5000 | paste -sd+ | bc; echo "status $?"
seq 1 60000 | paste -sd+ | bc; seq 1 20000 | sed 's/$/ - 1/' | paste -sd+ | bc
seq 1 3000 | paste -sd'*' | bc | tr -d '\\\n' | wc -c
cut -f 2 tab.tsv | paste -sd+ | bc; cut -d, -f 3 csv.csv | tail -n +2 | paste -sd+ | bc; awk -F, 'NR > 1 { print $3 }' csv.csv | paste -sd+ - | bc -l
seq 1 4000 | awk '{ printf "%s%s", (NR > 1 ? " + " : ""), $1 * 0.5 } END { print "" }' | bc -l
echo "1 && 0 || 1; 2 < 3 && 3 < 4; (1+2)*3-4/2%3" | bc; echo "x=0; for (i=1; i<=1000; i++) x+=i; x" | bc
printf '1+1\nquit\n3+3\n' | bc; echo "scale=3; $(seq 1 2000 | paste -sd+) / 2000" | bc
n=$(seq 1 10000 | paste -sd+ | bc); echo "sum $n mean $(echo "scale=2; $n / 10000" | bc)"
''')

# ---- October 2026: from the seventh and eighth independent checks (the script made from a run; the newest code) ----
# (grep -P is carried out by GNU grep 3.11 with PCRE2: these lines do not depend on the version of PCRE)
more('grep-P-is-a-grep-with-PCRE-and-other-things-from-the-last-checks', r'''
printf 'abc\r\n' | grep -cP '^.+$'; printf 'k=v\r\n' | grep -oP '=\K.+' | od -An -c; printf 'a\tb\r\nc\td\r\n' | grep -cP '^\w\t.+$'
printf 'beta 2\n' > g.txt; grep -P -- 'beta' g.txt; grep -oP -- '-\d' <<< 'a-1'; p='-2'; grep -cP -- "$p" <<< 'x-2'; echo "st $?"
printf 'x\tDP=35;AF=0.5\nx\tDP=7;AF=1\n' > v.txt; grep -oPm1 'DP=\K\d+' v.txt; grep -Pom1 'AF=\K[^;]+' v.txt; grep -Pc 'DP' v.txt; grep -PA1 'DP=35' v.txt | wc -l
printf 'c1 a\nc1 b\nc1 c\nc1 d\nc2 e\n' > g.txt; grep -P -m1 -A2 'c1' g.txt; grep -nP -m2 -A1 'c1' g.txt
echo 'x=1;y=22;z=333' | grep -oP '=\K(\d)\1'; grep -oP 'a++(b)\1' <<< 'aabb'; grep -oP "q=\K([\"'])\w+\1" <<< "q='abc' q=\"de\" q='x\""
echo abcabc | grep -oP '(?>a|b)+c'; echo abcabc | grep -cP '^(?>a|b)+c'; echo abca | grep -oP '(?>[a-c])+a'; echo "st $?"
grep -cP '^(")?\w+\1$' <<< 'abc'; echo "st $?"; grep -oP '(a)|b\1' <<< 'ab'; grep -cP '^("?)\w+\1$' <<< 'abc'
echo abc | grep -P -E b 2> /dev/null; echo "st $?"; echo abc | grep -FP b 2> /dev/null; echo "st $?"; echo aXb | egrep -P 'a\wb' 2> /dev/null; echo "st $?"
printf 'abc\0def\nxyz\n' > b.bin; grep -cP 'xyz' b.bin; grep -aP 'xyz' b.bin; grep -cP 'c\0d' b.bin; echo "st $?"
printf 'gene\tx\n' > t.txt; printf 'ge.e\n' > p.txt; grep -P -f p.txt t.txt; grep -P t.txt -e 'gen' | wc -l; echo "st $?"
mkdir -p d/e; printf 'beta\n' > d/a.txt; printf 'beta\nalpha\n' > d/e/b.txt; grep -rlP 'b\w+a' d | sort; grep -rhcP 'alpha' d | sort; grep -rP --include='b*' -c 'beta' d
printf 'one\ntwo\nthree\n' > z.txt; grep -Pc '(?x) t w o  # the second' z.txt; grep -P '(?i)THREE' z.txt; grep -P '(?i)(?s)^O.E$' z.txt; grep -oP 't(?=wo)|(?<=thr)ee' z.txt
printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab\n' | grep -cP '^(?=a)(a+)+$' 2> /dev/null; echo "st $?"
echo 'ABcd{}' | grep -oP '[\p{Lu}]+'; echo 'aVVb' | grep -oP '\V+'
a=(); echo "[${a-none}] [${a[0]-none}]"; ( set -u; echo "$a" ) 2> /dev/null; echo "st $?"; declare -A m; ( set -u; echo "$m" ) 2> /dev/null; echo "st $?"; b=([1]=x); ( set -u; echo "$b" ) 2> /dev/null; echo "st $?"; ( set -u; echo "${b[1]} ${#a[@]} ${a[@]} ok" ); echo "st $?"
printf 'if [ -p /dev/stdin ]; then echo piped; cat; else echo "arg: $1"; fi\n' > in.sh; bash in.sh x < /dev/null; echo hi | bash in.sh x; bash in.sh y < in.sh | head -n 1; bash -c '[ -p /dev/stdin ] && echo pipe || echo nopipe; [ -c /dev/stdin ] && echo dev' < /dev/null; chmod +x in.sh; ./in.sh z < /dev/null
f() { [ -f /dev/stdout ] && echo file; [ -p /dev/stdout ] && echo pipe; }; f > o.txt; cat o.txt; { [ -f /dev/stdout ] && echo file2; } >> o.txt; cat o.txt; [ -d /dev/fd ] && echo dir; f | cat
echo abc > m.txt; chmod 444 m.txt; touch m.txt; echo "st $?"; touch -d '2020-01-02 03:04:05' m.txt; echo "st $?"; date -r m.txt +%Y; stat -c %a m.txt
printf 'x\n' > o.txt; gzip o.txt; chmod 444 o.txt.gz; printf 'y\n' > o.txt; gzip -f o.txt; echo "st $?"; zcat o.txt.gz; ls o.txt*; printf 'z\n' > o.txt; chmod 444 o.txt; gunzip -f o.txt.gz; echo "st $?"; cat o.txt
echo 'x = 5; (x = 6); x' | bc; echo 'y = (x = 2) + 1; y; x' | bc; echo '2^228' | bc; echo 'scale=5; 22/7' | BC_LINE_LENGTH=5 bc; echo '10^68' | bc | wc -l; echo '10^67' | bc | wc -l
### two_commands_on_the_line_of_a_here_document
cat > a.txt <<EOF; echo second >> b.txt
first $((1 + 1))
EOF
cat a.txt b.txt
wc -l < b.txt
while read -r w; do echo "[$w]"; done <<EOF | tr a-z A-Z; echo after
one
two
EOF
### end
''')
more('what-more-random-sequences-of-file-commands-found', r'''
### sed_backup_keeps_the_permissions
printf 'a\nb\nc\n' > job.sh; chmod 755 job.sh; sed -i.bak 1d job.sh; stat -c '%a %n' job.sh job.sh.bak; wc -l < job.sh.bak
chmod 444 job.sh; sed -i.orig 1d job.sh; stat -c '%a %n' job.sh job.sh.orig; chmod 640 job.sh; sed --in-place=.old 1d job.sh; stat -c '%a %n' job.sh job.sh.old
for i in 1 2 3; do printf 'l1\nl2\n' > h$i.txt; done; chmod 755 h1.txt; chmod 644 h2.txt; chmod 600 h3.txt; sed -i.bak 1d h*.txt; stat -c '%a %n' h*
mkdir bak; printf 'l1\nl2\n' > k1.txt; printf 'l1\nl2\n' > k2.txt; chmod 644 k1.txt; chmod 700 k2.txt; sed -i'bak/*' 1d k1.txt k2.txt; echo "rc=$?"; stat -c '%a %n' k* bak/*
### end
### gunzip_looks_into_the_file_first
: > e.gz; echo old > e; gunzip e.gz 2> /dev/null; echo "rc=$?"; cat e; ls e.gz
echo plain > p.gz; echo old > p; gunzip p.gz 2> /dev/null; echo "rc=$?"; cat p; ls p.gz
printf 'x\n' > t.txt; gzip -c t.txt > v.gz; echo old > v; gunzip v.gz 2> /dev/null; echo "rc=$?"; cat v; ls v.gz
rm -f v; : > e2.gz; gunzip e2.gz v.gz 2> /dev/null; echo "rc=$?"; ls e2* v*
echo plain > p2.gz; gunzip p2.gz v.gz 2> /dev/null; echo "rc=$?"; ls p2* v*
### end
''')


def run_bash(text, args, files=False):
    # A folder of its own with the layout of the page's terminal: TOP/home/student is the home folder (HOME – "~" in
    # a script is this folder, never the home folder of whoever runs the test), and the script runs in
    # TOP/home/student/w. In what bash prints, TOP is taken away: the names read as in the page (/home/student/w).
    top = os.path.realpath(tempfile.mkdtemp(prefix='lang'))
    home = os.path.join(top, 'home', 'student')
    d = os.path.join(home, 'w')
    os.makedirs(d)
    if files:
        for name, content in FIX.items():
            os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
            open(os.path.join(d, name), 'w', encoding='utf-8').write(content)
    open(os.path.join(d, 's.sh'), 'w', encoding='utf-8').write(text)
    try:
        env = {**os.environ, 'LC_ALL': 'C.UTF-8', 'HOME': home, 'PWD': d}
        env.pop('OLDPWD', None)
        # (bash gets no input of its own: what [ -p /dev/stdin ] or read finds must not depend on how the test was started)
        r = subprocess.run(f'bash s.sh {args}', shell=True, cwd=d, capture_output=True, text=True, env=env, timeout=60, stdin=subprocess.DEVNULL)
        return r.stdout.replace(top, ''), r.returncode, r.stderr.replace(top, '')
    except subprocess.TimeoutExpired:
        return '', -1, 'the bash of this computer did not end within 60 s'
    finally:
        shutil.rmtree(top, ignore_errors=True)


ONLY = [n for a in sys.argv[1:] for n in GROUPS.get(a, [a])]
with sync_playwright() as pw:
    srv = server(port=PORT)
    bad = 0
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        for name, (text, args) in CASES.items():
            if ONLY and name not in ONLY:
                continue
            want_out, want_code, want_err = run_bash(text, args, name in WITH_FILES)
            got = page.evaluate("""async ([text, args, files]) => {
                const T = MG.app.term, fs = MG.app.fs;
                T.shell.freshState();
                await T.exec('cd ~ && rm -rf w && mkdir w && cd w');
                for (const [n, t] of Object.entries(files || {})) {
                    const p = '/home/student/w/' + n;
                    fs.mkdirp(MG.path.dirname(p));
                    fs.writeText(p, t);
                }
                fs.writeText('/home/student/w/s.sh', text);
                const before = T.outEl.children.length;
                const code = await T.exec('bash s.sh ' + args);
                const els = Array.from(T.outEl.children).slice(before + 1);
                const pick = (c) => els.filter((e) => e.dataset.cls === c).map((e) => e.textContent).join('');
                return { code, out: pick('out'), err: pick('err'), note: pick('note') };
            }""", [text, args, FIX if name in WITH_FILES else None])
            ok = got['out'] == want_out and got['code'] == want_code
            print(('ok   ' if ok else 'FAIL ') + name, flush=True)
            if not ok:
                bad += 1
                if got['code'] != want_code:
                    print(f'   exit: bash {want_code}, page {got["code"]}')
                w, g = want_out.split('\n'), got['out'].split('\n')
                for i in range(max(len(w), len(g))):
                    a = w[i] if i < len(w) else '<none>'
                    c = g[i] if i < len(g) else '<none>'
                    if a != c:
                        print(f'   line {i+1}:\n      bash: {a!r}\n      page: {c!r}')
                print('   page stderr:', got['err'][-600:].replace('\n', '\n      '))
                print('   bash stderr:', want_err[-400:].replace('\n', '\n      '))
        print('\n'.join(l for l in logs if 'PAGEERROR' in l)[:3000])
        b.close()
    finally:
        srv.terminate()
    print(f'{len(CASES) if not ONLY else len([n for n in CASES if n in ONLY])} scripts')
    print('FAILED' if bad else 'ALL OK', bad)
