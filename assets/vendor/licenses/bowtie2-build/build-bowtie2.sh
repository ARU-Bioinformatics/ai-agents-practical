#!/bin/bash
# Builds Bowtie 2 2.4.2 (bowtie2-build-s and bowtie2-align-s) as WebAssembly modules that the
# practical's Aioli runtime can load. Needs: git, tar, patch, make, python3 and the Emscripten SDK (emsdk).
# Built for the practical with Emscripten 6.0.10 and zlib 1.3.2.
#
#   tar -xf ../sources/bowtie2-2.4.2.tar.xz      # or: git clone --branch v2.4.2 https://github.com/BenLangmead/bowtie2.git bowtie2-2.4.2
#   git clone --branch v1.3.2 https://github.com/madler/zlib.git zlib-1.3.2
#   (cd bowtie2-2.4.2 && patch -p1 < ../bowtie2-v2.4.2-webassembly.patch)
#   source /path/to/emsdk/emsdk_env.sh
#   bash build-bowtie2.sh
# (See README.txt in this folder.)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
Z=$HERE/zlib-1.3.2
OUT=$HERE/out/bowtie2
mkdir -p "$OUT"

# zlib as a static WebAssembly library
if [ ! -f "$Z/libz.a" ]; then
  (cd "$Z" && emconfigure ./configure --static && emmake make -j2 libz.a)
fi

# The patch (bowtie2-v2.4.2-webassembly.patch) makes the Makefile, when the compiler is em++:
#  - compile Bowtie 2's own SSE2 code to WebAssembly SIMD (-msimd128 -msse2) instead of emulating it,
#  - use WebAssembly exceptions (-fwasm-exceptions),
#  - write NAME.js + NAME.wasm into $(WASM_OUT) and add $(WASM_FLAGS) when linking;
# in bt2_search.cpp, runs the search in the calling thread (there are no threads here); and, in pat.cpp, reports a
# read file that could not be opened (this C library's fdopen() does not complain about the descriptor -1).
EM_FLAGS="-I$Z -L$Z -sINVOKE_RUN=0 -sFORCE_FILESYSTEM=1 -sEXPORTED_RUNTIME_METHODS=[\"callMain\",\"FS\",\"PROXYFS\",\"WORKERFS\"] -sMODULARIZE=1 -sENVIRONMENT=web,worker -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=64MB -sSTACK_SIZE=5MB -fwasm-exceptions -lworkerfs.js -lproxyfs.js"
cd "$HERE/bowtie2-2.4.2"
HOSTNAME=webassembly emmake make -B -j2 bowtie2-build-s bowtie2-align-s \
  NO_TBB=1 POPCNT_CAPABILITY=0 WASM_OUT="$OUT" WASM_FLAGS="$EM_FLAGS" \
  COMPILER_NOTE="Emscripten $(emcc -dumpversion) (clang), WebAssembly SIMD"

# The runtime needs each program's exit status: record it where exit() is handled.
python3 - "$OUT" <<'PY'
import sys
for name in ('bowtie2-align-s.js', 'bowtie2-build-s.js'):
    p = sys.argv[1] + '/' + name
    s = open(p).read()
    old = 'var exitJS=(status,implicit)=>{EXITSTATUS=status;'
    assert s.count(old) == 1, name
    s = s.replace(old, 'var exitJS=(status,implicit)=>{Module.__exitStatus=status;EXITSTATUS=status;')
    s = '// Bowtie 2 2.4.2 compiled to WebAssembly for this practical (see THIRD_PARTY.md). exit(status) is recorded as Module.__exitStatus.\n' + s
    open(p, 'w').write(s)
PY
ls -l "$OUT"
