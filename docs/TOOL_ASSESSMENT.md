# Requested reverse-engineering tools

This assessment is specific to the original PS1 R3000 MIPS-I executable, not
to later fan remakes. Pseudocode is evidence for a C attempt; the matching
compiler and the complete executable comparison decide whether it is accepted.

| Repository | Actual role and current evidence |
| --- | --- |
| [morluto/rea](https://github.com/morluto/rea) | Applied its evidence-first investigation skill and independently scoped analysis. Installed and ran REA 6.3.0 with the Ghidra provider against the verified MIPS ELF. It rejected this architecture with `target_unavailable: unsupported ELF architecture`; the error is saved in `.decomp-lab/rea-evidence/original-overview.log`. Current main's documented MIPS32R2 admission does not cover this PS1 R3000 binary. Do not spoof its architecture/ABI. |
| [trevaintdead/ai-game-modding-guides](https://github.com/trevaintdead/ai-game-modding-guides) | Read the system-map/build/asset/runtime workflow from its source checkout. Applied that separation in the feature inventory, isolated candidate builds and emulator evidence. |
| [bethington/ghidra-mcp](https://github.com/bethington/ghidra-mcp) | Ghidra 12.1.4 successfully imported an unstripped ELF whose exported executable exactly matches LSD. Exported pseudocode for 2,109 analyzed function symbols, including SDK and header artifacts, and verified the dedicated local MCP API can decompile original functions. This is not a count of recovered game features. |
| [rehan-remade/universal-modder](https://github.com/rehan-remade/universal-modder) | Applied `mod-any-game` and the retro-decomp playbook: private matching candidates, original assets, and emulator-local scripted inputs. Its actual CLI knowledge-base searches for LSD returned no notes in this checkout. No paid image service or asset replacement is required for parity. |
| [HexRaysSA/ida-mcp](https://github.com/HexRaysSA/ida-mcp) | Its backend requires a licensed IDA installation with idalib. No suitable local IDA installation has been found in the inspected tool paths. Ghidra supplies the native MIPS analysis without this prerequisite. No successful IDA analysis is claimed. |
| [icsharpcode/ILSpy](https://github.com/icsharpcode/ILSpy) | Used CLI 9.1.0.7988 on the shipped BizHawk 2.11.1 managed adapter to inspect its core APIs, media lookup and required game-database initialization while developing the [isolated replay host](HEADLESS_REPLAY.md). This is analysis tooling; LSD's native MIPS executable remains the matching C target, and no game C recovery is attributed to ILSpy. |
| [SamboyCoding/Cpp2IL](https://github.com/SamboyCoding/Cpp2IL) | Targets Unity IL2CPP binaries and metadata. The original PS1 game has neither, so it cannot recover this executable. |
| [matt-kempster/m2c](https://github.com/matt-kempster/m2c) | An additional appropriate MIPS-to-C aid, recommended by the retro-decomp guide. Installed in the private WSL environment and used on original assembly with `--target mipsel-gcc-c`. Generated sketches still require typing, compilation and exact comparison. |
| [simonlindholm/decomp-permuter](https://github.com/simonlindholm/decomp-permuter) | Additional local compiler search for the remaining C candidates, pinned to commit `8556c81d80d1c1af98a858c8f4dc951357f29139`. Uses the actual GCC 2.6.3/MASPSX/R3000 pipeline, with stack and branch-target differences counted. The bounded 20-minute memory-card search returned no improvement over its eight-byte private mismatch; no candidate was promoted. Search scores require genuine source review and complete-executable equality. Evidence: `.decomp-lab/root-work/card-permuter-0152-result.json`. |
| [TASEmulators/BizHawk](https://github.com/TASEmulators/BizHawk) | Official 2.11.1 build in a dedicated runtime directory. Lua drives emulator-local inputs and captures frames, states and PCM audio. Earlier English replay outputs agree, but their manifests omitted the actual Nymashock core identity. Current Japanese 6,000-frame shared-state and 1,800-frame cold pairs agree with Nymashock and its Waterbox host pinned before execution. A further same-original cold boot varies in eight decoded state bytes; no bytes are masked. Full feature scenarios remain pending. Evidence and boundaries: [replay method](RUNTIME_COMPARISON.md), [Japanese verification](JAPANESE_EDITION.md). |

A later ten-minute local search retained the renderer candidate's genuine
inline dimension helpers and counted its four differing bytes, with conditional
dummy-block mutations disabled. It produced no improvement or output candidate.
Evidence: `.decomp-lab/root-work/c6a8-permuter-state-join-01-result.json`.
Neither timed search establishes an exact C match or whole-game parity.

The later [grid edge-lifetime study](GRID_PHASES.md#inclusive-edge-lifetime-study)
calibrates a new eight-byte seed against the original 660-byte function and the
current compiler stages. Its ten-minute local search disables padding and
constant-condition insertion and produces no improved output. Stack and branch
targets remain part of the score; complete-executable equality remains the
independent acceptance gate.

## Linked video

The actual metadata/description of [The AI unlock has begun](https://www.youtube.com/watch?v=h5zkzon0gM4)
was fetched with yt-dlp without downloading its media, and saved as
`.decomp-lab/youtube-h5zkzon0gM4.json`. The description lists the seven requested
repositories plus [AnyPS5](https://github.com/boykopovar/AnyPS5) and
[PortPS5](https://github.com/ymatrix1/PortPS5). Those two address PS5 native
binary portability, not this PS1 MIPS executable. The video's demonstrations
are not independent evidence that a tool supports LSD or achieves parity.

## Local analysis

The isolated Ghidra project is `<AnalysisRoot>/projects/lsd-original.gpr`,
with the program
`/original-symbols.elf`. `tools/start_analysis.ps1` takes explicit installation paths and starts a dedicated local
server on port 8101, preserving existing unrelated services. The native
language is `MIPS:LE:32:default`, with LSD's GP value `0x8008A808`.

The ELF, pseudocode and copyrighted inputs stay outside tracked deliverables.
`tools/decomp_workbench.py context` produces verified original assembly,
native Ghidra evidence, candidate C, headers and a portable AI-analysis prompt.
It verifies the original bytes and hashes every bundled evidence file. The
exporter itself does not invoke an AI model or send files to an external API.
`tools/decomp_workbench.py check` compiles an isolated full translation unit
and compares the entire executable. These developer tools remain separate
from original NPC behavior and optional mod outputs. Binary equality proves executable identity; it does not certify a
source explanation, exhaustive asset coverage or independently observed
gameplay.

The optional `check --function` diagnostic now qualifies actual complete ELF
function extents after checking that retaining symbols changes no candidate
executable bytes. Its [source-interface guide](SOURCE_INTERFACE_DIAGNOSTICS.md)
records actual use on two nonmatching collision units and an unchanged bounds
control, plus the remaining ABI and source gates. These are analysis results;
they add no recovered C bytes or accepted game features.
