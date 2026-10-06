"""Do a student's files survive? Random sequences of file commands, in the page and in real bash: the same output,
the same exit status – and afterwards the same files with the same contents.

   python3 t_files.py             150 sequences (seed 2026), about 4 minutes
   python3 t_files.py SEED N      N sequences from another seed (any whole number)
   python3 t_files.py SEED N K    … and show sequence K of them (the script, and what both sides print)

The page keeps files in two places: its own list of files, and the memory of the WebAssembly programs (where every
file lives that is no text, or is larger than 256 KiB). cp and mv do not copy such a file's bytes until a program
needs them. A fault in that bookkeeping loses or changes a file without a word – so each sequence mixes the page's
own commands (cp, mv, rm, >, >>, truncate, tee, split, find -delete …) with programs (sed -i, sort -o, awk, gzip,
gunzip, cut, paste, uniq …) on the same few names: small text files, a file of bytes that are no text (bin.dat), a
text file of 349 KB (big.txt), folders, a name with a blank in it. After every step (or at the end) the script
prints the checksum and the permissions of every file as the programs see them; the test then compares, file by
file, what the page itself holds with what real bash left behind.

The sequences are run by the bash of this computer in a new folder of the system's temporary files (their home
folder, too; it is removed afterwards) with the GNU tools of this computer, LC_ALL=C.UTF-8 and umask 022 (the
terminal's own settings). They use only names inside that folder, never read a file while appending to it, and
need: bash, coreutils, sed, awk, grep, gzip, findutils, diffutils."""
import sys, time, subprocess, tempfile, os, shutil, hashlib, random, resource
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import *
PORT = 8833
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
N = int(sys.argv[2]) if len(sys.argv) > 2 else 150
SHOW = int(sys.argv[3]) if len(sys.argv) > 3 else None
os.umask(0o022)   # (the files of the sequences get the permissions that the terminal gives them: 644, folders 755)

FIX = {
    'in.txt': 'l1 a\nl2 b\nl3 c\nl4 d\nl5 e\n',
    'nums.txt': '3\n1\n2\n10\n2\n',
    'names.txt': 'sampleB\nsampleA\nsampleC\n',
    'tab.tsv': 'chr1\t100\tA\tG\nchr1\t250\tC\tT\nchr2\t30\tG\tA\n',
    'a.txt': 'alpha\nbeta\ngamma\n',
    'b.txt': 'alpha\nBETA\ngamma\ndelta\n',
    'small.fa': '>seq1 first\nACGTACGTAC\nGGGTTT\n>seq2 second\nTTTTAAAA\n',
    'd1/x.txt': 'one\ntwo\n',
    'd1/y.txt': 'same\n',
    'd1/sub/z.txt': 'deep\n',
    'd2/x.txt': 'one\nTWO\n',
}

# ------------------------------------------------------------------------------------------------------------------
# the sequences
# ------------------------------------------------------------------------------------------------------------------
rnd = random.Random(SEED)
FILES = ['a.txt', 'b.txt', 'in.txt', 'nums.txt', 'names.txt', 'tab.tsv', 'bin.dat', 'big.txt', 'n1.txt', 'n2.txt', 'my file.txt',
         'd1/x.txt', 'd1/y.txt', 'd1/sub/z.txt', 'd2/x.txt', 'dn/f.txt', 'small.fa']
WEIGHT = [4, 3, 3, 2, 3, 2, 5, 5, 3, 2, 3, 2, 1, 2, 1, 2, 1]   # (the two special files are picked more often)
DIRS = ['d1', 'd2', 'dn', 'd1/sub']


def q(n):
    return "'" + n + "'" if ' ' in n else n


class Model:
    """what is believed to be there – roughly: enough to make most steps work on files that exist"""
    def __init__(self):
        self.have = {'a.txt', 'b.txt', 'in.txt', 'nums.txt', 'names.txt', 'tab.tsv', 'bin.dat', 'big.txt', 'n1.txt', 'my file.txt', 'd1/x.txt', 'd1/y.txt',
                     'd1/sub/z.txt', 'd2/x.txt', 'small.fa', 'nums.txt.gz'}
        self.dirs = {'d1', 'd2', 'd1/sub'}

    def add(self, n):
        if ('/' not in n or n.rsplit('/', 1)[0] in self.dirs) and n not in self.dirs:
            self.have.add(n)

    def rm(self, n):
        self.have.discard(n)

    def rmdir(self, d):
        self.dirs = {x for x in self.dirs if x != d and not x.startswith(d + '/')}
        self.have = {x for x in self.have if not x.startswith(d + '/')}


M = Model()


def anyfile(not_in=()):
    while True:
        f = rnd.choices(FILES, WEIGHT)[0]
        if f not in not_in:
            return f


def S(not_in=()):
    """a file to read: mostly one that is there"""
    there = sorted(x for x in M.have if not x.endswith('.gz') and x not in not_in)
    return rnd.choice(there) if there and rnd.random() < 0.88 else anyfile(not_in)


def G():
    """a .gz file: mostly one that is there"""
    there = sorted(x for x in M.have if x.endswith('.gz'))
    return rnd.choice(there) if there and rnd.random() < 0.85 else anyfile() + '.gz'


def W(not_in=()):
    """a file to write: one that is there, or a new name"""
    there = sorted(x for x in M.have if not x.endswith('.gz') and x not in not_in)
    return rnd.choice(there) if there and rnd.random() < 0.5 else anyfile(not_in)


def D(not_in=()):
    while True:
        d = rnd.choice(DIRS)
        if d not in not_in:
            return d


def step(n):
    """one step: a command line. (No step reads a file while it appends to the same file, and wc and grep never write
    to one of their own input files: GNU wc then counts its own output, GNU grep refuses – known differences.)"""
    k = rnd.randrange(98)
    a, x = S(), S()
    b, c = W(), W()
    y = W(not_in=(x,))
    d = D()
    base = lambda p: p.rsplit('/', 1)[-1]
    had = lambda p: p in M.have
    # ---- the page's own commands ----
    if k == 0:
        if had(a): M.add(b)
        return f'cp {q(a)} {q(b)}'
    if k == 1:
        if had(a) and d in M.dirs: M.add(d + '/' + base(a))
        return f'cp {q(a)} {q(d)}'
    if k == 2:
        e = D(not_in=(d,))
        if e.startswith(d + '/'): d, e = e, d
        return f'cp -r {q(d)} {q(e)}'
    if k == 3:
        if had(a) and a != b: M.rm(a); M.add(b)
        return f'mv {q(a)} {q(b)}'
    if k == 4:
        if had(a) and d in M.dirs and a != d + '/' + base(a): M.rm(a); M.add(d + '/' + base(a))
        return f'mv {q(a)} {q(d)}'
    if k == 5:
        e = D()
        if d in M.dirs and d != e and not e.startswith(d + '/'): M.rmdir(d)
        return f'mv {q(d)} {q(e)}'
    if k == 6:
        M.rm(a)
        return f'rm {q(a)}'
    if k == 7:
        M.rm(a); M.rm(b)
        return f'rm -f {q(a)} {q(b)}'
    if k == 8:
        M.rmdir(d)
        return f'rm -r {q(d)}'
    if k == 9:
        for i in range(1, d.count('/') + 2): M.dirs.add('/'.join(d.split('/')[:i]))
        return f'mkdir -p {q(d)}'
    if k == 10: return f'rmdir {q(d)}'
    if k == 11:
        M.add(b)
        return f'echo "line {n}" > {q(b)}'
    if k == 12:
        M.add(b)
        return f'echo "more {n}" >> {q(b)}'
    if k == 13:
        M.add(b)
        return f': > {q(b)}'
    if k == 14:
        M.add(b)
        return f'truncate -s {rnd.choice([0, 3, 7, 40])} {q(b)}'
    if k == 15:
        M.add(b)
        return f'touch {q(b)}'
    if k == 16: return f'head -n 7 {q(a)} | split -l 2 - part.'
    if k == 17:
        M.have = {v for v in M.have if not base(v).startswith('n')}
        return "find . -name 'n*' -delete"
    # ---- programs ----
    if k == 18:
        M.add(c)
        return f'cat {q(a)} {q(S())} > {q(c)}'
    if k == 19:
        M.add(y)
        return f'tee {q(y)} < {q(x)} > /dev/null'
    if k == 20:
        z = W(not_in=(x,)); M.add(y); M.add(z)
        return f'tee -a {q(y)} {q(z)} < {q(x)} > /dev/null'
    if k == 21:
        M.add(b)
        return f'head -c {rnd.choice([5, 50, 300000])} {q(a)} > {q(b)}'
    if k == 22:
        M.add(y)
        return f'tail -n 2 {q(x)} >> {q(y)}'
    if k == 23: return f"sed -i 's/[aeiou1]/_/' {q(a)}"
    if k == 24:
        if had(a): M.add(a + '.bak')
        return f"sed -i.bak '1d' {q(a)}"
    if k == 25: return f"sed -i '$d' {q(a)} {q(S())}"
    if k == 26:
        if had(a): M.add(b)
        return f'sort {q(a)} -o {q(b)}'
    if k == 27: return f'sort -r -o {q(a)} {q(a)}'
    if k == 28: return f'sort {q(a)} > {q(a)}'
    if k == 29:
        M.add(b)
        return f"awk 'NR % 2' {q(a)} > {q(b)}"
    if k == 30: return f"awk '{{ print > (\"aw\" NR % 2 \".txt\") }}' {q(a)}"
    if k == 31: return f"awk '{{ print $1 }}' {q(a)} > tmp.x && mv tmp.x {q(a)}"
    if k == 32:
        if had(a) and a + '.gz' not in M.have: M.rm(a); M.add(a + '.gz')
        return f'gzip {q(a)}'
    if k == 33:
        if had(a): M.add(a + '.gz')
        return f'gzip -k {q(a)}'
    if k == 34:
        if had(a): M.rm(a); M.add(a + '.gz')
        return f'gzip -f {q(a)}'
    if k == 35:
        g = G()
        if had(g) and g[:-3] not in M.have: M.rm(g); M.add(g[:-3])
        return f'gunzip {q(g)}'
    if k == 36:
        g = G()
        if had(g): M.rm(g); M.add(g[:-3])
        return f'gunzip -f {q(g)}'
    if k == 37:
        M.add(b)
        return f'gzip -dc {q(G())} > {q(b)}'
    if k == 38:
        M.add(b + '.gz')
        return f'gzip -c {q(a)} > {q(b + ".gz")}'
    if k == 39: return 'gzip *.txt *.gz'
    if k == 40: return 'gunzip *.gz'
    if k == 41: return f'gzip -r {q(d)}'
    if k == 42: return f'gunzip -r {q(d)}'
    if k == 43:
        M.add(b)
        return f'tr a-z A-Z < {q(a)} > {q(b)}'
    if k == 44:
        M.add(b)
        return f'cut -c 1-3 {q(a)} > {q(b)}'
    if k == 45:
        M.add(c)
        return f'paste {q(a)} {q(S())} > {q(c)}'
    if k == 46:
        if had(a): M.add(b)
        return f'uniq {q(a)} {q(b)}'
    if k == 47:
        b = W(not_in=(a,)); M.add(b)
        return f'grep -v a {q(a)} > {q(b)}'
    if k == 48:
        M.add(c)
        return f'diff {q(a)} {q(S())} > {q(c)}'
    if k == 49: return f'cmp {q(a)} {q(S())}'
    if k == 50:
        a2 = S(); c = W(not_in=(a, a2)); M.add(c)
        return f'wc -c {q(a)} {q(a2)} > {q(c)}'
    if k == 51:
        M.add(b)
        return f'fold -w 7 {q(a)} > {q(b)}'
    if k == 52: return 'for f in *.txt; do sed -i \'s/e/E/\' "$f"; done'
    # ---- a copy or a move, then the original or the copy is changed: each must keep its own contents ----
    if k == 53:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; echo "added {n}" >> {q(y)}; tail -c 20 {q(x)} | md5sum'
    if k == 54:
        if had(x): M.add(y)
        M.add(x)
        return f'mv {q(x)} {q(y)}; echo "new {n}" > {q(x)}; cat {q(x)} {q(y)} | wc -c'
    if k == 55:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; sed -i \'1s/^/#/\' {q(y)}; head -c 12 {q(x)} | od -An -c | head -n 1'
    if k in (56, 57):
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; truncate -s 4 {q(x)}; wc -c < {q(y)}'
    if k == 58:
        if had(x): M.rm(x); M.add(y); M.add(x + '.gz')
        return f'mv {q(x)} {q(y)}; gzip -c {q(y)} > {q(x)}.gz; gzip -dc {q(x)}.gz | cmp - {q(y)}'
    if k == 59:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; rm {q(x)}; sort {q(y)} | head -n 2 > {q(x)}'
    if k == 60: return f'cp {q(a)} tmp.x; : > {q(a)}; cat tmp.x >> {q(a)}; rm -f tmp.x'
    if k == 61:
        if had(a) and a != b: M.rm(a); M.add(b)
        return f'sed -i \'s/$/ !/\' {q(a)}; mv {q(a)} {q(b)}; sed -n \'1p\' {q(b)}'
    if k == 62:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; echo "over {n}" > {q(x)}; head -c 30 {q(y)} | md5sum'
    if k == 63:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; gzip -f {q(x)}; wc -c < {q(y)}; gunzip -f {q(x)}.gz; cmp {q(x)} {q(y)}'
    if k in (64, 65):
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; printf "\\377\\376 {n}\\n" > {q(x)}; head -c 16 {q(y)} | md5sum; wc -c < {q(x)}'
    if k == 66:
        if had(x): M.rm(x); M.add(y); M.add(x)
        return f'mv {q(x)} {q(y)}; head -n 3 nums.txt | split -l 1 - {q(x)}. ; ls {q(x)}.* 2> /dev/null | wc -l; rm -f {q(x)}.a?; truncate -s 9 {q(x)}; wc -c < {q(y)}'
    if k == 67:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; cp {q(y)} third.tmp; rm -f {q(x)}; mv third.tmp {q(x)}; cmp {q(x)} {q(y)}'
    if k == 68:
        M.add(b)
        return f'head -c 300000 big.txt > {q(b)}; cp {q(b)} second.big; echo "tail {n}" >> second.big; tail -c 12 {q(b)} | md5sum; tail -n 1 second.big; rm -f second.big'
    if k == 69:
        if had(x): M.add(y)
        return f'cp {q(x)} {q(y)}; echo "replaced {n}" > {q(x)}; cp {q(y)} {q(x)}.2; cmp {q(y)} {q(x)}.2; rm -f {q(x)}.2'
    if k == 70:
        if had(x): M.rm(x); M.add(y)
        return f'mv {q(x)} hold.tmp && head -c 20 hold.tmp | md5sum; mv hold.tmp {q(y)}'
    # ---- temporary names, folders that are moved, removed and made again, a file where a folder was ----
    if k == 71:
        if had(a): M.add(b)
        return f't=$(mktemp -p .) && {{ sort {q(a)} > "$t" && mv "$t" {q(b)}; rm -f "$t"; }}'
    if k == 72:
        if had(a): M.add(b)
        return f't=$(mktemp -d -p .) && {{ cp {q(a)} "$t/f" && sed -i 1d "$t/f" && mv "$t/f" {q(b)}; rm -rf "$t"; }}'
    if k == 73:
        e = D(not_in=(d,))
        if d in M.dirs and not e.startswith(d + '/') and not d.startswith(e + '/'): M.rmdir(d)
        return f'mv {q(d)} {q(e)}; ls {q(e)} 2> /dev/null | head -n 3; for f in {q(e)}/*.txt; do [ -f "$f" ] && sort -r "$f" -o "$f"; done'
    if k == 74:
        M.rmdir(d)
        for i in range(1, d.count('/') + 2): M.dirs.add('/'.join(d.split('/')[:i]))
        M.add(d + '/new.txt')
        return f'rm -rf {q(d)}; mkdir -p {q(d)}; sort {q(a)} -o {q(d)}/new.txt; ls {q(d)}'
    if k == 75:
        M.rm(a)
        return f'rm -f {q(a)}; mkdir {q(a)} && cp {q(x)} {q(a)}/inside.txt; md5sum {q(a)}/inside.txt 2> /dev/null | cut -c 1-8; rm -r {q(a)}; echo "again {n}" > {q(a)}; wc -c {q(a)}'
    if k == 76:
        M.rmdir('dn')
        return f'rm -rf dn; cp {q(a)} dn; tr a-z A-Z < dn | head -c 30 | md5sum; rm -f dn; mkdir dn; cp {q(x)} dn/; ls dn'
    if k == 77: return f'cp -r {q(d)} keep.d; rm -rf {q(d)}; mv keep.d {q(d)}; find {q(d)} -type f ! -name "*.gz" | sort | xargs -r md5sum | cut -c 1-8 | tr "\\n" " "; echo'
    if k == 78: return f'for f in {q(d)}/*; do [ -f "$f" ] && [[ $f != *.gz ]] && gzip -f "$f"; done; ls {q(d)} 2> /dev/null; for f in {q(d)}/*.gz; do [ -f "$f" ] && gunzip -f "$f"; done; ls {q(d)} 2> /dev/null'
    if k == 79:
        if had(a): M.add(a + '.bak')
        return f'cp {q(a)}{{,.bak}}; sed -i \'$d\' {q(a)}; diff {q(a)} {q(a)}.bak | head -n 3'
    if k == 80: return 'for f in *.txt; do mv "$f" "${f%.txt}.tsv2"; done; ls | head -n 4; for f in *.tsv2; do mv "$f" "${f%.tsv2}.txt"; done'
    if k == 81:
        # (never a block that reads the file it writes to: tr would read what it has itself written, without end)
        b = W(not_in=(a, x)); M.add(b)
        return f'{{ cat {q(a)}; tr a-z A-Z < {q(x)}; }} > {q(b)}'
    if k == 82:
        M.add(b + '.gz')
        return f'for f in {q(a)} {q(x)}; do gzip -c "$f"; done > {q(b + ".gz")}; gzip -dc {q(b + ".gz")} | wc -c'
    if k == 83:
        M.add(b)
        return f'f() {{ sort -u "$1"; }}; f {q(a)} > {q(b)}; f {q(b)} | wc -l'
    if k == 84: return 'find . -name "*.bak" -delete; find . -type f -name "x*.txt" -exec sed -i "s/^/>/" {} +; find . -type f -empty -delete'
    if k == 85: return f'mkdir -p copies; find {q(d)} -type f ! -name "*.gz" -exec cp {{}} copies/ \\; 2> /dev/null; ls copies | head -n 3; rm -r copies'
    if k == 86:
        if had(x): M.add(y)
        return f'cat {q(x)} | tee {q(y)} | wc -c; cmp {q(x)} {q(y)}'
    if k == 87: return f'cd {q(d)} 2> /dev/null && {{ rm -rf "$PWD"; mkdir -p "$PWD"; cd "$PWD"; echo "made again {n}" > here.txt; sort here.txt -o here2.txt; ls; cd ~/w; }}'
    if k == 88:
        if had(a): M.add(b)
        return f'cp {q(a)} {q(b)}; chmod +x {q(b)}; sed -i 1d {q(b)}; [ -x {q(b)} ] && echo "still x"; sort {q(b)} -o {q(b)}; [ -x {q(b)} ] && echo "still x"'
    if k == 89: return f'mkdir -p deep/a/b; cp {q(a)} deep/a/b/f; mv deep deep2; sed -i 1d deep2/a/b/f; mv deep2/a deep2/c; wc -l < deep2/c/b/f; rm -r deep2'
    if k == 90:
        if had(x): M.add(y)
        return f'cp -p {q(x)} {q(y)}; [ {q(x)} -nt {q(y)} ] || [ {q(y)} -nt {q(x)} ] || echo "same time"; sed -i 1d {q(y)}; wc -l < {q(y)}'
    # ---- two files of one name into one folder; a file written by name under an empty > ; many files in one call; modes ----
    if k == 91: return 'mkdir -p all; cp d1/x.txt d2/x.txt all/; cat all/x.txt 2> /dev/null | md5sum | cut -c 1-8; rm -r all'
    if k == 92:
        if 'd1' in M.dirs and (had('d1/x.txt') or had('d2/x.txt')):
            if not had('d1/x.txt'): M.rm('d2/x.txt')
            M.add('d1/x.txt')
        return 'mkdir -p all; mv d1/x.txt d2/x.txt all/; ls all; mv all/x.txt d1/ 2> /dev/null; rm -rf all'
    if k == 93:
        M.add(y)
        return f'sort {q(x)} -o {q(y)} > {q(y)}'
    if k == 94:
        M.add(b)
        return f'f() {{ echo "inner {n}" >> {q(b)}; }}; f > {q(b)}; wc -c < {q(b)}'
    if k == 95: return "sed -i 's/^/+/' *.txt d1/*.txt"
    if k == 96:
        if rnd.random() < 0.5:
            return f'chmod 640 {q(a)} && {{ echo "more {n}" >> {q(a)}; stat -c %a {q(a)}; }}'
        if had(a): M.rm(a + '.gz')
        return f'chmod 750 {q(a)} && gzip -f {q(a)} && gunzip -f {q(a)}.gz && stat -c %a {q(a)}'
    inner = rnd.choice(["sed -i 's/o/0/' x.txt", 'sort -r x.txt -o ../n1.txt', 'cp ../a.txt .', 'mv x.txt ../n2.txt', 'gzip -f x.txt', 'echo "in dir" > ../b.txt', 'rm -f ../a.txt y.txt',
                        'awk 1 ../in.txt > y.txt', 'cp ../big.txt .', 'mv ../bin.dat .', 'cat ../big.txt ../bin.dat > both.dat', 'gunzip -f x.txt.gz',
                        'cp ../bin.dat copy.dat; echo tail >> copy.dat; cmp ../bin.dat copy.dat', 'mv ../big.txt .; sed -i 1d big.txt; mv big.txt ..'])
    return f'cd {q(rnd.choice(["d1", "d2"]))} && {{ {inner}; echo "inner=$?"; cd "$OLDPWD"; }}'


# what the programs see: the checksum of every file (of a .gz file: of what is in it), the folders, and the
# permissions of every file and folder (chmod; and a file keeps them when it is added to, changed in place, compressed)
DUMP = r'''dump() { find . -type f ! -name '*.gz' ! -name s.sh -print0 | sort -z | xargs -0 -r md5sum | cut -c 1-8,33-; find . -type f -name '*.gz' | sort | while IFS= read -r f; do printf '%s  %s\n' "$(gzip -dc "$f" 2> /dev/null | md5sum | cut -c 1-8)" "$f"; done; find . -type d | sort | tr '\n' ' '; echo; find . ! -name s.sh ! -name . -print0 | sort -z | xargs -0 -r stat -c '%a %n' | tr '\n' ' '; echo; }'''
# a file of bytes that are no text, a text file that is too large to be kept as text, a name with a blank, a .gz file
PRE = "tr 'a-m' '\\200-\\214' < in.txt > bin.dat; seq 60000 > big.txt; cp names.txt n1.txt; cp a.txt 'my file.txt'; gzip -k nums.txt"


def sequence():
    global M
    M = Model()
    nsteps = rnd.randrange(6, 15)
    every = rnd.random() < 0.5   # the checksums after every step, or only at the end (looking can hide a fault)
    lines = [DUMP, PRE]
    for n in range(1, nsteps + 1):
        lines.append(step(n) + '; echo "rc=$?"')
        if every and n < nsteps:
            lines.append('dump')
    lines.append('dump')
    return '\n'.join(lines) + '\n'


SEQS = [sequence() for _ in range(N)]


# ------------------------------------------------------------------------------------------------------------------
def summary(path, data):
    """a file as it is compared: its checksum – of a .gz file only whether it has contents (gzip and the page's bgzip
    write different bytes for the same contents; what is in it is in the output of the script)"""
    if path.endswith('.gz'):
        return 'gz' if data else 'gz, empty'
    return hashlib.md5(data).hexdigest()


def run_bash(text):
    # A folder of its own with the layout of the page's terminal: TOP/home/student is the home folder (HOME), and the
    # script runs in TOP/home/student/w.
    top = os.path.realpath(tempfile.mkdtemp(prefix='files'))
    home = os.path.join(top, 'home', 'student')
    d = os.path.join(home, 'w')
    os.makedirs(d)
    for name, content in FIX.items():
        os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
        open(os.path.join(d, name), 'w', encoding='utf-8').write(content)
    open(os.path.join(d, 's.sh'), 'w', encoding='utf-8').write(text)
    try:
        env = {**os.environ, 'LC_ALL': 'C.UTF-8', 'HOME': home, 'PWD': d}
        env.pop('OLDPWD', None)
        # (no file can grow beyond 64 MB, whatever a sequence does: a step that read the file it appends to would not end)
        limit = lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))
        r = subprocess.run('bash s.sh', shell=True, cwd=d, capture_output=True, env=env, timeout=60, stdin=subprocess.DEVNULL, preexec_fn=limit)
        files = {}
        for dp, dirs, fl in os.walk(d):
            for x in dirs:
                files[os.path.relpath(os.path.join(dp, x), d)] = 'folder'
            for x in fl:
                p = os.path.join(dp, x)
                rel = os.path.relpath(p, d)
                if rel != 's.sh':
                    files[rel] = summary(rel, open(p, 'rb').read())
        return r.stdout.decode('utf-8', 'replace').replace(top, ''), r.returncode, r.stderr.decode('utf-8', 'replace').replace(top, ''), files
    except subprocess.TimeoutExpired:
        return '', -1, 'the bash of this computer did not end within 60 s', {}
    finally:
        shutil.rmtree(top, ignore_errors=True)


PAGE = """async ([text, fix]) => {
    const T = MG.app.term, fs = MG.app.fs;
    T.shell.freshState();
    await T.exec('cd ~ && rm -rf w && mkdir w && cd w');
    for (const [n, t] of Object.entries(fix)) {
        const p = '/home/student/w/' + n;
        fs.mkdirp(MG.path.dirname(p));
        fs.writeText(p, t);
    }
    fs.writeText('/home/student/w/s.sh', text);
    const before = T.outEl.children.length;
    const code = await T.exec('bash s.sh');
    const els = Array.from(T.outEl.children).slice(before + 1);
    const pick = (c) => els.filter((e) => e.dataset.cls === c).map((e) => e.textContent).join('');
    // the files as the page itself holds them
    const files = {}, top = '/home/student/w/';
    for (const [k, e] of Array.from(fs.entries)) {
        if (!k.startsWith(top) || k === top + 's.sh') continue;
        const rel = k.slice(top.length);
        if (e.kind === 'dir') { files[rel] = 'folder'; continue; }
        try { const b = await fs.readBytes(k); files[rel] = rel.endsWith('.gz') ? (b.length ? 'gz' : 'gz, empty') : MG.md5(b); } catch (x) { files[rel] = 'cannot be read: ' + x.message; }
    }
    return { code, out: pick('out'), err: pick('err'), files };
}"""

with sync_playwright() as pw:
    srv = server(port=PORT)
    bad = 0
    try:
        b, page, logs = browser(pw)
        page.goto(f'http://127.0.0.1:{PORT}/index.html')
        page.wait_for_function('window.MG_READY === true', timeout=30000)
        for i, text in enumerate(SEQS, 1):
            if SHOW is not None and i != SHOW:
                continue
            want_out, want_code, want_err, want_files = run_bash(text)
            got = page.evaluate(PAGE, [text, FIX])
            diffs = []
            if got['code'] != want_code:
                diffs.append(f'exit: bash {want_code}, page {got["code"]}')
            if got['out'] != want_out:
                w, g = want_out.split('\n'), got['out'].split('\n')
                n = 0
                for j in range(max(len(w), len(g))):
                    x = w[j] if j < len(w) else '<nothing>'
                    y = g[j] if j < len(g) else '<nothing>'
                    if x != y:
                        diffs.append(f'output line {j + 1}: bash {x[:200]!r}, page {y[:200]!r}')
                        n += 1
                        if n >= 6:
                            break
            for k in sorted(set(want_files) | set(got['files'])):
                if want_files.get(k) != got['files'].get(k):
                    diffs.append(f'file {k}: bash {want_files.get(k, "not there")}, page {got["files"].get(k, "not there")}')
            if bool(want_err.strip()) != bool(got['err'].strip()):
                diffs.append('messages: ' + ('only bash printed some' if want_err.strip() else 'only the page printed some'))
            print(('ok   ' if not diffs else 'FAIL ') + f'sequence {i}', flush=True)
            if diffs or SHOW is not None:
                bad += bool(diffs)
                print('   | ' + text.rstrip('\n').replace('\n', '\n   | '))
                for l in diffs[:25]:
                    print('   ' + l)
                if SHOW is not None:
                    print('--- bash prints:\n' + want_out + '--- bash messages:\n' + want_err + '--- the page prints:\n' + got['out'] + '--- the page\'s messages:\n' + got['err'])
        errs = [l for l in logs if 'PAGEERROR' in l]
        if errs:
            print('\n'.join(errs)[:3000])
            bad += 1
        b.close()
    finally:
        srv.terminate()
    n = 1 if SHOW is not None else len(SEQS)
    print(f'\nseed {SEED}: {n - min(bad, n)} of {n} passed')
    print('ALL OK' if not bad else 'FAILED')
    sys.exit(1 if bad else 0)
