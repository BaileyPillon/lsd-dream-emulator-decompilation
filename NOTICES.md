# Attribution and licensing notices

## Upstream decompilation

LSD: Dream Emulator Decompilation continues [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled).
The initial publication retains upstream Git history through commit
`16a3914b9bcb75bd94a6b983ed3a952234461625` and adds the matching C recovery,
build fixes, verification tools and documentation developed in this project.

The inspected upstream checkout and repository metadata contain no
repository-wide license. No MIT, GPL or other blanket license is assigned to
the inherited game decompilation, SDK reconstruction or headers here.
Repository visibility is not a substitute for a license grant.

## Matching C contributions

Two matching collision reconstructions are adapted from
[brian-oblivion/lsddecomp](https://github.com/brian-oblivion/lsddecomp), commit
`90a398e4f429b4371be05648605fc198b9efb395`:

- `src/graphics/scene_node.c`, `SceneNode__RaycastHullAgainstFaces`, adapted as
  `func_8001DDF4` in this project's `src/base/transform.c`.
- `src/graphics/tmd_model.c`, `TmdModel__RaycastFaces`, adapted as
  `func_8001F8B8` in this project's `src/file/tmd_prim_geom.c`.

That upstream project dedicates its own work under CC0-1.0. Its complete
[license text](LICENSES/CC0-1.0.txt) is retained here. Adaptations use this
project's existing types, symbols and interfaces; documented compiler-layout
storage preserves the original executable. This attribution does not assign a
blanket license to the inherited decompilation, SDK material or game assets.

## Third-party tools

| Component | Provenance and notices |
| --- | --- |
| `tools/gcc263/` | Legacy GCC 2.6.3 binaries inherited unchanged from the upstream repository. GCC is a separate GNU project; these binaries are not a project-authored compiler. [GNU GCC source archives](https://ftp.gnu.org/gnu/gcc/) contain the original release sources and notices. |
| `tools/ninja_syntax.py` | Carries its original Google copyright and Apache License 2.0 notice in the file. |
| Python dependencies | Pinned in `requirements.txt` and `requirements-analysis.txt`; each package retains its own license. |
| MASPSX | Downloaded during setup from [mkst/maspsx](https://github.com/mkst/maspsx) at the pinned revision; its checkout and license remain separate. |
| Optional analysis/emulator tools | Referenced in the documentation and supplied by their respective authors. They are not bundled with this repository. |
| Optional NPC observer | Project analysis source for the existing CPU hook in [BizHawk 2.11.1](https://github.com/TASEmulators/BizHawk/tree/2.11.1) and its pinned Mednafen submodule. Build inputs and their upstream notices remain in a separate checkout; no emulator binary is bundled. |

The repository does not distribute original game discs, executable files,
extracted game assets, PlayStation BIOS files, save states or emulator captures.
