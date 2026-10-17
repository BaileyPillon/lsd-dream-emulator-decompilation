# Emulator media-metadata initialization

The Nymashock adapter constructs media labels whose unused short-string storage
can retain prior stack bytes. Waterbox snapshots preserve those object
representations. Equal game outputs can therefore accompany different complete
state payloads in the
[distributed-core comparison](COLD_DREAM_CYCLE.md).

The [source patch](../research/runtime_state/bizhawk-2.11.1-label-initialization.patch)
constructs persistent drives, states, media types, defaults and actual disc-count
media records in their final vectors, then assigns the original labels and
fields. It avoids copying temporary record representations into persistent
storage. The tested libc++ default constructor initializes the whole 24-byte
string object.

The earlier CD-only patch initialized that label's twenty unused bytes, but a
30,000-frame replay still differed in eight unused bytes of `Disc 1 of 1`.
The current revision covers all six labels in the one-disc descriptor graph.
Six actual cold boots preserve every checked name, state flag, media type,
delay, default and vector element count. All 64 unused string bytes and 23
existing record-padding bytes are zero; all five complete-state repeat pairs
agree. The same descriptor checks pass in all 122 saved states from the
completed original/rebuilt first-dream replay.

This changes the emulator host. Matching C remains **196,504 / 199,912 bytes
(98.30%)**, with four assembly functions and two inherited storage explanations.
The normal play profile and separate Bevy port retain their existing inputs.

## Evidence and limits

| Profile | Completed observation |
| --- | --- |
| Distributed BizHawk 2.11.1 | Earlier 30,000-frame game outputs agree; strict state differences remain recorded. |
| Unmodified source rebuild | Two one-frame repeats and a 6,000-frame original/rebuilt controller history agree, including all 16 checkpoint state payloads. The native label still contains eight nonzero unused bytes. |
| CD-only initialization rebuild | Game outputs and audio agree over 30,000 frames per disc. Strict state comparisons retain eight differing unused disc-name bytes at each of 61 checkpoints. |
| Complete-record initialization rebuild | Six one-frame boots agree across five complete-state repeat pairs; all six native descriptor labels and original named values are checked. |
| Complete-record full-day replay | All 61 complete-state checkpoint pairs, recorded controls, native fields, RAM, GPU, PNG and complete PCM agree over 30,000 frames per disc. The native day advances at relative frame 23,706 in both runs. |

The unmodified source rebuild already passes its recorded repeats. Equality in
those runs is not attributed solely to the patch. A separate hosted construction
test uses five known storage patterns, three construction modes and debug/release
builds. Its thirty observations show direct construction retaining all twenty
prefilled tail bytes, default construction plus assignment clearing them, and
the move preserving the complete representation. Guards and the logical label
agree in every case.

The initialized-record core also preserves the recorded game outputs from the
earlier distributed-core original-disc history. Those manifests differ in the
core binary and owned save/screenshot path roots. The ordinary strict input
comparator rejects those differences; this separate output-preservation check
does not accept cross-core state parity.

The [validation metadata](emulator-label-initialization-checks.json) records
before/after counts, source and core identities, and private report hashes.

No saved-state bytes are masked or rewritten. These are separately identified
rebuilt emulator profiles; they do not turn the distributed-core failures into
passes. Complete game content, NPC encounters, original hardware timing and
whole-feature acceptance remain separate requirements.

## Reproduce the construction check

Use Clang 18, libc++ 18 and lld 18 in Linux/WSL. From the matching-game checkout:

```sh
set -eu
mkdir .decomp-lab/label-construction-new
clang++-18 -std=c++17 -stdlib=libc++ -Wall -Wextra -Werror -O0 \
  research/runtime_state/label_construction.cpp \
  -o .decomp-lab/label-construction-new/debug
clang++-18 -std=c++17 -stdlib=libc++ -Wall -Wextra -Werror \
  -O3 -flto -fuse-ld=lld-18 research/runtime_state/label_construction.cpp \
  -o .decomp-lab/label-construction-new/release
.decomp-lab/label-construction-new/debug > .decomp-lab/label-construction-new/debug.jsonl
.decomp-lab/label-construction-new/release > .decomp-lab/label-construction-new/release.jsonl
```

Each executable emits fifteen rows. Mode `0` directly constructs the label;
mode `1` default-constructs before assignment; mode `2` also fills the string's
capacity through its public API before assignment. Seeds are `0`, `23`, `90`,
`165` and `255`. Every row must retain length `2`, capacity `22`, equal logical
names, unchanged guards and identical before/after-move bytes. In modes `1` and
`2`, bytes `4..23` must all be zero. The program checks the observed 24-byte ABI
at compile time. No original game inputs or model API are used.

## Build separate emulator profiles

The patch targets [BizHawk 2.11.1's adapter](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/waterbox/nyma/cdrom.cpp).
The [upstream build instructions](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/waterbox/readme.txt)
describe the toolchain. This recipe records the tested Clang/LLVM 18.1.8 path.
The patch retains upstream CRLF context and is marked `-text` in Git. Its
Windows checkout was applied to fresh pinned source; a repeated application
check rejects it without changing the target.

Required packages include `make`, `cmake`, `clang-18`, `lld-18`, `llvm-18`,
`llvm-18-dev` and `zstd`. The hosted reproducer additionally uses
`libc++-18-dev` and `libc++abi-18-dev`.

Use a fresh native Linux directory without spaces. Generated musl linker
scripts use the compiler's path, so a shim directory under a Windows path
containing spaces can fail linking. The LLVM development package supplies the
CMake configuration needed by compiler-rt.

Run from the matching-game checkout. The separate checkout below contains
emulator sources and build products; it does not replace this game's toolchain.

```sh
set -eu
lsdPatchFile="$PWD/research/runtime_state/bizhawk-2.11.1-label-initialization.patch"
lsdCoreDir="$HOME/lsd-nymashock-media-record-research"
test -f "$lsdPatchFile"
test ! -e "$lsdCoreDir"
git -c core.autocrlf=false clone --depth=1 --branch=2.11.1 \
  --filter=blob:none --sparse https://github.com/TASEmulators/BizHawk.git "$lsdCoreDir"
git -C "$lsdCoreDir" config --local core.autocrlf false
test "$(git -C "$lsdCoreDir" rev-parse HEAD)" = bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5
git -C "$lsdCoreDir" sparse-checkout set --skip-checks \
  waterbox/nyma waterbox/musl waterbox/libcxx waterbox/emulibc waterbox/libco
git -C "$lsdCoreDir" submodule update --init --depth=1 waterbox/musl waterbox/nyma/mednafen
git clone --depth=1 --branch=llvmorg-18.1.8 --filter=blob:none --sparse \
  https://github.com/llvm/llvm-project.git "$lsdCoreDir/waterbox/llvm-project"
git -C "$lsdCoreDir/waterbox/llvm-project" sparse-checkout set \
  cmake compiler-rt libunwind libcxx libcxxabi runtimes
mkdir "$lsdCoreDir/tools"
for lsdTool in clang clang++ ld.lld llvm-config llvm-ar llvm-ranlib llvm-nm llvm-objdump; do
  ln -s "$(command -v "$lsdTool-18")" "$lsdCoreDir/tools/$lsdTool"
done
export PATH="$lsdCoreDir/tools:$PATH"
export CC=clang CXX=clang++
export SYSROOT="$lsdCoreDir/waterbox/sysroot"
export LLVMDIR="$lsdCoreDir/waterbox/llvm-project"
export LLVM_DIR="$(llvm-config --cmakedir)"
export CMAKE_PREFIX_PATH="$(llvm-config --prefix)"
export CMAKE_BUILD_PARALLEL_LEVEL=4
(cd "$lsdCoreDir/waterbox/musl" && ./wbox_configure.sh && make -j4 && make install)
(cd "$lsdCoreDir/waterbox/emulibc" && make -j4)
(cd "$lsdCoreDir/waterbox/libco" && make -j4)
for lsdPhase in - 0 1 2; do
  (cd "$lsdCoreDir/waterbox/libcxx" && \
    "./configure-for-waterbox-phase-$lsdPhase" && \
    cmake --build "build$lsdPhase" --parallel 4 && cmake --install "build$lsdPhase")
done
(cd "$lsdCoreDir/waterbox/nyma/zlib" && \
  ./configure-for-waterbox && make -j4 libz.a && ./install-for-waterbox)
(cd "$lsdCoreDir/waterbox/nyma" && make -f shock.mak -j4)
git -C "$lsdCoreDir" diff --exit-code
cp "$lsdCoreDir/waterbox/nyma/obj/release/shock.wbx" "$lsdCoreDir/shock-pristine.wbx"
git -C "$lsdCoreDir" apply --check "$lsdPatchFile"
git -C "$lsdCoreDir" apply "$lsdPatchFile"
(cd "$lsdCoreDir/waterbox/nyma" && make -f shock.mak -j4)
cp "$lsdCoreDir/waterbox/nyma/obj/release/shock.wbx" "$lsdCoreDir/shock-initialized-records.wbx"
sha256sum "$lsdCoreDir/shock-pristine.wbx" "$lsdCoreDir/shock-initialized-records.wbx"
```

The exact recipe completed successfully in a fresh checkout. Runtime
observations use a separately pinned initial build of the same patched source.
The metadata records distinct hashes for the recipe outputs and the tested core.

The pinned submodules are musl `2063abc4e16c84218757b1db10d3cdf9f36ef3f8`
and Mednafen `382ff1b8d293c9a862497706808cbb79b2cecbfb`; LLVM is
`3b5b5c1ec4a3095ab096dd780e84d7ab81f3d7ff`. Build outputs depend on the
complete compiler environment. Record their hashes; a source rebuild is not
assumed byte-identical to the distributed core.

For runtime checks, use a separate copy of the BizHawk 2.11.1 frontend for each
core and place its Zstandard-compressed core at `dll/shock.wbx.zst`. The
[cold-start recorder](COLD_START.md) accepts that directory through
`--emulator-root` and pins its actual files, BIOS, disc, configuration and
observer. Use `--frames 30000` for the full-day capture and add
`--require-day-advance` to the comparison. Keep each runtime's files fixed while
its recorded manifests are still being verified.

The [normal play instructions](PLAYING.md) continue to use the distributed
emulator profile. [Earlier native string-storage diagnosis](NYMASHOCK_STATE.md)
and [complete replay limits](STATE_REPLAY_BOUNDARY.md) retain their original
evidence and scope. The patch is an emulator-source change; upstream source
and licensing remain linked to the pinned BizHawk project.
