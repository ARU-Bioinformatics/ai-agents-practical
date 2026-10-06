How the Bowtie 2 programs of this practical were built
======================================================
bowtie2-align-s and bowtie2-build-s (assets/vendor/biowasm/bowtie2/2.4.2/) are Bowtie 2 2.4.2,
compiled to WebAssembly with Emscripten 6.0.10 and zlib 1.3.2. Bowtie 2 is licensed under the
GNU General Public License version 3; this folder and ../sources/bowtie2-2.4.2.tar.xz are its
Corresponding Source for these programs.

To build them again (Linux; needs git, tar, patch, make, python3 and the Emscripten SDK):

  tar -xf ../sources/bowtie2-2.4.2.tar.xz                    # or: git clone --branch v2.4.2 https://github.com/BenLangmead/bowtie2.git bowtie2-2.4.2
  git clone --branch v1.3.2 https://github.com/madler/zlib.git zlib-1.3.2
  (cd bowtie2-2.4.2 && patch -p1 < ../bowtie2-v2.4.2-webassembly.patch)
  source /path/to/emsdk/emsdk_env.sh                         # Emscripten 6.0.10 was used
  bash build-bowtie2.sh                                      # writes out/bowtie2/NAME.js and NAME.wasm

(Keep build-bowtie2.sh, the patch and the two source folders in one folder.)

The patch is adapted from the Biowasm recipe for Bowtie 2 (../biowasm-build/tools/bowtie2/, MIT).
The git submodule third_party/simde of Bowtie 2 is not needed: Bowtie 2's SSE2 code is compiled to
WebAssembly SIMD through Emscripten's own emmintrin.h.

A build with another version of Emscripten gives programs that work the same but are not
byte-identical to the ones here.
