# Attribution and licensing notices

## Upstream decompilation

LSD Recovered continues [cawfee/lsd_decompiled](https://github.com/cawfee/lsd_decompiled).
The initial publication retains upstream Git history through commit
`16a3914b9bcb75bd94a6b983ed3a952234461625` and adds the matching C recovery,
build fixes, verification tools and documentation developed in this project.

The inspected upstream checkout and repository metadata contain no
repository-wide license. No MIT, GPL or other blanket license is assigned to
the inherited game decompilation, SDK reconstruction or headers here.
Repository visibility is not a substitute for a license grant.

## Third-party tools

| Component | Provenance and notices |
| --- | --- |
| `tools/gcc263/` | Legacy GCC 2.6.3 binaries inherited unchanged from the upstream repository. GCC is a separate GNU project; these binaries are not a project-authored compiler. [GNU GCC source archives](https://ftp.gnu.org/gnu/gcc/) contain the original release sources and notices. |
| `tools/ninja_syntax.py` | Carries its original Google copyright and Apache License 2.0 notice in the file. |
| Python dependencies | Pinned in `requirements.txt` and `requirements-analysis.txt`; each package retains its own license. |
| MASPSX | Downloaded during setup from [mkst/maspsx](https://github.com/mkst/maspsx) at the pinned revision; its checkout and license remain separate. |
| Optional analysis/emulator tools | Referenced in the documentation and supplied by their respective authors. They are not bundled with this repository. |

The repository does not distribute original game discs, executable files,
extracted game assets, PlayStation BIOS files, save states or emulator captures.
