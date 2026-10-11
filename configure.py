import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys

from tools import ninja_syntax

PROJECT_ROOT = Path(__file__).resolve().parent

# To build a matching executable or not
NON_MATCHING = False

# Extension constants
ELF_EXT = ".elf"
LD_EXT = ".ld"
MAP_EXT = ".map"
O_EXT = ".o"
YAML_EXT = ".yaml"
SHA_EXT = ".sha"

# Config
GAME_ID = "SLPS01556"
GAME_BIN = GAME_ID[:7] + "." + GAME_ID[7:]

# Paths
CONFIG_DIR = "config"
TOOLS_DIR = "tools"
BUILD_DIR = "build"

LD_SCRIPT = BUILD_DIR + "/" + GAME_ID + LD_EXT
MAP_FILE = BUILD_DIR + "/" + GAME_ID + MAP_EXT
ELF = BUILD_DIR + "/" + GAME_ID + ELF_EXT
EXE = BUILD_DIR + "/" + GAME_BIN
UNDEF_SYMS = BUILD_DIR + "/undefined_syms_auto.txt"
UNDEF_FUNCS = BUILD_DIR + "/undefined_funcs_auto.txt"
SPLAT_CONFIG = CONFIG_DIR + "/" + GAME_ID + YAML_EXT
EXE_HASH = CONFIG_DIR + "/" + GAME_ID + SHA_EXT
ROM = "rom/SLPS_015.56"
SYMBOLS = CONFIG_DIR + "/symbols.txt"

GCC_DIR = TOOLS_DIR + "/gcc263"

# Tools
CROSS = "mipsel-linux-gnu-"
AS = CROSS + "as -EL"
LD = CROSS + "ld -EL"
CPP = CROSS + "cpp"
OBJCOPY = CROSS + "objcopy"
CC = str(PROJECT_ROOT / GCC_DIR / "cc1")
CPP263 = str(PROJECT_ROOT / GCC_DIR / "cpp")
CPLUS = str(PROJECT_ROOT / GCC_DIR / "cc1plus")

PYTHON = sys.executable
MASPSX = TOOLS_DIR + "/maspsx/maspsx.py"
MASPSX_REVISION = "e85ecb373828aabea96d7e6400974d4f91ce8c74"
SPLAT = "-m splat split"

# Tool Flags
INCLUDE_FLAGS = ["-Iinclude/asm", "-Iinclude", "-Isrc"]
ASM_INCLUDES = ["include/asm/macro.inc", "include/asm/gte.inc"]
AS_FLAGS = INCLUDE_FLAGS + ["-march=r3000", "-mtune=r3000", "-no-pad-sections"]
CPP_FLAGS = INCLUDE_FLAGS + ["-undef", "-Wall", "-lang-c", "-fno-builtin"]
CPPPLUS_FLAGS = INCLUDE_FLAGS + ["-lang-c++"]
C_FLAGS = [
    "-quiet",
    "-Wall",
    "-fno-builtin",
    "-mno-abicalls",
    "-funsigned-char",
    "-G0",
    "-O2",
]
C_FLAGS_G8 = [flag for flag in C_FLAGS if not flag.startswith("-G")] + ["-G8"]
CPLUS_FLAGS = C_FLAGS + []
MASPSX_FLAGS = ["--dont-force-G0", "--expand-div", "--aspsx-version=2.21", "-G8"]
LD_FLAGS = ["--no-check-sections", "-nostdlib", "-s"]

CLANG_FORMAT = "clang-format"
CLANG_TIDY = "clang-tidy"
TIDY_FLAGS = INCLUDE_FLAGS + ["-std=c99"]

if NON_MATCHING:
    CPP_FLAGS.append("-DNON_MATCHING=1")

# Sources
asm_game_targets = [

]

asm_psyq_targets = [
    "asm/psyq_unk2.s",
    "asm/psyq_unk3.s",
    "asm/21180.s",
    "asm/22244.s",
    "asm/40FF8.s",
]

asm_data_targets = [
    "asm/data/1764.rodata.s",
    "asm/data/1818.rodata.s",
    "asm/data/1908.rodata.s",
    "asm/data/19DC.rodata.s",
    "asm/data/1AA4.rodata.s",
    "asm/data/1D0C.rodata.s",
    "asm/data/1DD0.rodata.s",
    "asm/data/1EA4.rodata.s",
    "asm/data/206C.rodata.s",
    "asm/data/57040.data.s",
    "asm/data/5BDCC.data.s",
    "asm/data/5C6F0.data.s",
    "asm/data/5C8F8.data.s",
    "asm/data/5DCE8.data.s",
    "asm/data/5E234.data.s",
    "asm/data/5ED58.data.s",
    "asm/data/5EF30.data.s",
    "asm/data/5F0E4.data.s",
    "asm/data/5F468.data.s",
    "asm/data/5F540.data.s",
    "asm/data/5F610.data.s",
    "asm/data/5F8B8.data.s",
    "asm/data/5FA40.data.s",
    "asm/data/5FE14.data.s",
    "asm/data/76EE8.data.s",
    "asm/data/775C4.data.s",
    "asm/data/77EFC.data.s",
    "asm/data/783DC.data.s",
    "asm/data/79528.data.s",
    "asm/data/7B00C.sdata.s",
    "asm/data/7B024.sdata.s",
    "asm/data/7B040.sdata.s",
    "asm/data/7B058.sdata.s",
    "asm/data/7B0B8.sdata.s",
    "asm/data/7B0D4.sdata.s",
    "asm/data/7B0E8.sdata.s",
    "asm/data/7B138.sdata.s",
    "asm/data/7B16C.sdata.s",
    "asm/data/7B180.sdata.s",
    "asm/data/7B234.sdata.s",
    "asm/data/7B394.sdata.s",
    "asm/data/7B3C0.sdata.s",
    "asm/data/7B40C.sdata.s",
    "asm/data/7B424.sbss.s",
    "asm/data/7B468.sbss.s",
    "asm/data/7B46C.sbss.s",
    "asm/data/7B4B4.sbss.s",
    "asm/data/7B4CC.sbss.s",
    "asm/data/800.rodata.s",
    "asm/data/ABC.rodata.s",
    "asm/data/BD4.rodata.s",
    "asm/data/F28.rodata.s",
    "asm/data/FD8.rodata.s",
    "asm/data/1040.rodata.s",
]

asm_header_targets = [
    "asm/header.s",
]

# Hand written assembly
hasm_targets = [
    "src/psyq/write.s",
    "src/psyq/SetMem.s",
    "src/start.s",
]

asm_auto_targets = (
    asm_game_targets
    + asm_psyq_targets
    + asm_data_targets
    + asm_header_targets
    + hasm_targets
)
asm_targets = []

# Psy-Q SDK units, compiled with -G0.
c_psyq_targets = [
    "src/psyq/libc/memory.c",
    "src/psyq/libc/printf.c",
    "src/psyq/libc/prnt.c",
    "src/psyq/libc/memchr.c",
    "src/psyq/libc/strlen.c",
    "src/psyq/libc/ctype.c",
    "src/psyq/libc/putchar.c",
    "src/psyq/libc/strcat.c",
    "src/psyq/malloc.c",
    "src/psyq/gs/matrix.c",
    "src/psyq/gs/134.c",
    "src/psyq/gs/127.c",
    "src/psyq/gs/13.c",
    "src/psyq/gs/2d_sp0.c",
    "src/psyq/gs/2d_com1.c",
    "src/psyq/gs/2d_bg0.c",
    "src/psyq/gs/119.c",
    "src/psyq/gs/120.c",
    "src/psyq/gs/135.c",
    "src/psyq/gs/box0.c",
    "src/psyq/gs/com0.c",
    "src/psyq/gs/objt.c",
    "src/psyq/gs/GsMapModelingData.c",
    "src/psyq/gte/mtx003.c",
    "src/psyq/gte/mtx0.c",
    "src/psyq/gte/mtx2.c",
    "src/psyq/gte/mtx1.c",
    "src/psyq/gte/mtxb.c",
    "src/psyq/gte/mtx4.c",
    "src/psyq/gte/mtx5.c",
    "src/psyq/gte/mtxa.c",
    "src/psyq/gte/mtx6.c",
    "src/psyq/gte/mtx9.c",
    "src/psyq/gte/mtx7.c",
    "src/psyq/gte/mtx8.c",
    "src/psyq/gte/mtx03.c",
    "src/psyq/gte/mtx04.c",
    "src/psyq/gte/mtx05.c",
    "src/psyq/gte/mtx06.c",
    "src/psyq/gte/mtx07.c",
    "src/psyq/gte/mtx08.c",
    "src/psyq/gte/mtx09.c",
    "src/psyq/gte/mtx10.c",
    "src/psyq/gte/mtx11.c",
    "src/psyq/gte/mtx12.c",
    "src/psyq/gte/cmb0.c",
    "src/psyq/gte/reg04.c",
    "src/psyq/gte/reg05.c",
    "src/psyq/gte/reg06.c",
    "src/psyq/gte/reg07.c",
    "src/psyq/gte/reg08.c",
    "src/psyq/gte/reg09.c",
    "src/psyq/gte/fgo01.c",
    "src/psyq/gte/geo.c",
    "src/psyq/gte/geo00.c",
    "src/psyq/gte/geo02.c",
    "src/psyq/gte/geo03.c",
    "src/psyq/gte/msc02.c",
    "src/psyq/gte/divf3a.c",
    "src/psyq/gte/divf4a.c",
    "src/psyq/gte/divg3a.c",
    "src/psyq/gte/divg4a.c",
    "src/psyq/gte/divft3a.c",
    "src/psyq/gte/divft4a.c",
    "src/psyq/gte/divgt3a.c",
    "src/psyq/gte/divgt4a.c",
    "src/psyq/gte/ratan.c",
    "src/psyq/gte/SquareRoot0.c",
    "src/psyq/gpu/sys.c",
    "src/psyq/gs/001.c",
    "src/psyq/gpu/prim.c",
    "src/psyq/gs/003.c",
    "src/psyq/gs/103.c",
    "src/psyq/gs/121.c",
    "src/psyq/gs/002.c",
    "src/psyq/gs/010.c",
    "src/psyq/gte/reg03.c",
    "src/psyq/etc/intr.c",
    "src/psyq/etc/vmode.c",
    "src/psyq/etc/intr_dma.c",
    "src/psyq/etc/intr_vb.c",
    "src/psyq/etc/vsync.c",
    "src/psyq/etc/pad.c",
    "src/psyq/gte/smp00.c",
    "src/psyq/libc/strcpy.c",
    "src/psyq/libc/strstr.c",
    "src/psyq/cd/lib.c",
    "src/psyq/spu/SpuVmSetProgVol.c",
    "src/psyq/snd/SsUtPitchBend.c",
    "src/psyq/spu/SpuVmVSetUp.c",
    "src/psyq/snd/SsSetTableSize.c",
    "src/psyq/snd/SsVabOpenHead.c",
    "src/psyq/snd/SsUtGetVabHdr.c",
    "src/psyq/snd/SsUtGetVagAtr.c",
    "src/psyq/snd/SsSetMVol.c",
    "src/psyq/snd/SsUtGetProgAtr.c",
    "src/psyq/snd/SsVabTransBody.c",
    "src/psyq/snd/SsSetMute.c",
    "src/psyq/snd/SsVabTransCompleted.c",
    "src/psyq/snd/SsSeqCalledTbyT.c",
    "src/psyq/snd/Snd_pause.c",
    "src/psyq/snd/Snd_tempo.c",
    "src/psyq/snd/Snd_replay.c",
    "src/psyq/snd/SsVabClose.c",
    "src/psyq/snd/_SsUtResolveADSR.c",
    "src/psyq/snd/SsUtReverbOn.c",
    "src/psyq/snd/SsUtSetVagAtr.c",
    "src/psyq/snd/_SsSndNextSep.c",
    "src/psyq/snd/_SsReadDeltaValue.c",
    "src/psyq/snd/Snd_stop.c",
    "src/psyq/spu/SpuSetMute.c",
    "src/psyq/spu/SpuVmDamperOn.c",
    "src/psyq/spu/SpuVmDamperOff.c",
    "src/psyq/snd/SsSeqSetVol.c",
    "src/psyq/snd/Snd_SetReplayMode.c",
    "src/psyq/snd/Snd_setvol_data.c",
    "src/psyq/snd/SsSeqOpen.c",
    "src/psyq/snd/Snd_SetPlayMode.c",
    "src/psyq/snd/seq_close.c",
    "src/psyq/snd/Snd_SetPauseMode.c",
    "src/psyq/gs/GsInit3D.c",
    "src/psyq/cd/CdInit.c",
    "src/psyq/gs/GsGetTimInfo.c",
    "src/psyq/libc/memset.c",
    "src/psyq/gs/110.c",
    "src/psyq/gs/GsSetFlatLight.c",
    "src/psyq/gs/Gssub_make_matrix.c",
    "src/psyq/libc/rand.c",
    "src/psyq/gs/GsSetRefView2.c",
    "src/psyq/gs/GsGetLw.c",
    "src/psyq/gs/GsDrawOt.c",
    "src/psyq/gs/GsClearOt.c",
    "src/psyq/gs/GsSetLightMode.c",
    "src/psyq/gs/TransposeMatrix.c",
    "src/psyq/gs/SetFogNear.c",
    "src/psyq/libpress/libpress.c",
    "src/psyq/libc/exit.c",
    "src/psyq/libpress/vlc.c",
    "src/psyq/libpress/vlc2.c",
    "src/psyq/cd/c002.c",
    "src/psyq/cd/c003.c",
    "src/psyq/cd/read2.c",
    "src/psyq/cd/c005.c",
    "src/psyq/cd/c008.c",
    "src/psyq/cd/c011.c",
    "src/psyq/cd/c010.c",
    "src/psyq/cd/cdrom.c",
    "src/psyq/cd/c009.c",
    "src/psyq/cd/c007.c",
    "src/psyq/libc/atoi.c",
    "src/psyq/libc/todigit.c",
    "src/psyq/card/c172.c",
    "src/psyq/card/c171.c",
    "src/psyq/card/card.c",
    "src/psyq/card/a78.c",
    "src/psyq/card/a74.c",
    "src/psyq/card/a75.c",
    "src/psyq/card/c112.c",
    "src/psyq/card/a80.c",
]

# Game units, compiled with -G8.
c_game_targets = [
    "src/file/tim_list.c",
    "src/main.c",
    "src/base/base.c",
    "src/utils/cd_paths.c",
    "src/menu/main_menu.c",
    "src/menu/main_menu_entry.c",
    "src/menu/main_menu_post.c",
    "src/menu/card/memory_card.c",
    "src/file/file_buf.c",
    "src/sound/bgm.c",
    "src/sound/sound.c",
    "src/sys/system.c",
    "src/sys/screen.c",
    "src/dream/dream_sys.c",
    "src/dream/dream_session_path.c",
    "src/file/debug_file_driver.c",
    "src/menu/mdec_movie.c",
    "src/scene/render_context.c",
    "src/file/str_stream.c",
    "src/sys/pad.c",
    "src/sys/display_ref.c",
    "src/file/cd_file_driver.c",
    "src/file/tmd_prim_geom.c",
    "src/base/object_math.c",
    "src/dream/dream_generation.c",
    "src/dream/dream_generation_palette.c",
    "src/dream/dream_generation_post.c",
    "src/dream/dream_generation_sdata.c",
    "src/dream/generation_structure.c",
    "src/menu/card/comment_input.c",
    "src/menu/card/comment_input_cursor.c",
    "src/scene/map_scene.c",
    "src/scene/link.c",
    "src/dream/generation_apply.c",
    "src/graphics/renderer.c",
    "src/base/timer.c",
    "src/game/game_flow.c",
    "src/menu/movie_screen.c",
    "src/scene/stage_grid.c",
    "src/file/tmd_prim.c",
    "src/graphics/display.c",
    "src/file/file_object.c",
    "src/graphics/effect.c",
    "src/graphics/effect_base.c",
    "src/menu/text_line.c",
    "src/menu/glyph.c",
    "src/menu/sprite.c",
    "src/sound/seq_file.c",
    "src/base/frame_phase.c",
    "src/graphics/light.c",
    "src/graphics/flat_light.c",
    "src/file/tmd_model.c",
    "src/file/model_part.c",
    "src/menu/ui_sprite.c",
    "src/file/object_model.c",
    "src/file/object_model_list.c",
    "src/menu/tile_buffer.c",
    "src/menu/sprite_atlas.c",
    "src/file/model_part_list.c",
    "src/file/cd_stream.c",
    "src/dream/dream_session.c",
    "src/scene/scene.c",
    "src/graphics/scene_renderer.c",
    "src/scene/notify_node.c",
    "src/scene/scene_node.c",
    "src/dream/generation_sprite.c",
    "src/scene/actor.c",
    "src/base/render_sort.c",
    "src/psyq/spu/S_I.c",
    "src/psyq/snd/24490.c",
    "src/psyq/snd/272A8.c",
    "src/sys/display_border.c",
    "src/base/transform.c",
    "src/scene/stage_texture.c",
    "src/file/tim_image.c",
    "src/menu/ui_screen.c",
    "src/menu/sprite_node.c",
    "src/menu/graph_screen.c",
    "src/menu/card/select_menu.c",
    "src/scene/map_scene_post.c",
    "src/scene/entity.c",
    "src/psyq/snd/22D88.c",
]

c_game_g0_targets = {
    "src/dream/dream_generation_palette.c",
    "src/menu/main_menu_entry.c",
}


def c_source_uses_g8(filename):
    """Keep isolated comparisons and the standard build on identical flags."""
    return filename in c_game_targets and filename not in c_game_g0_targets


cpp_targets = []


def _find_c_sources(*roots):
    """All .c/.h files under the given roots, used by clang-format."""
    found = []
    for root in roots:
        for dirpath, _dirnames, filenames in os.walk(PROJECT_ROOT / root):
            for name in filenames:
                if name.endswith((".c", ".h")):
                    path = Path(dirpath) / name
                    found.append(path.relative_to(PROJECT_ROOT).as_posix())
    return sorted(found)


format_targets = _find_c_sources("src", "include")
tidy_targets = sorted(set(c_psyq_targets + c_game_targets + cpp_targets))


def assembly_includes(filename):
    """Track assembly included inside C, which CPP's header depfile cannot see."""
    source = (PROJECT_ROOT / filename).read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    return sorted(set(
        f"{folder}/{name}.s" for folder, name in re.findall(
            r'\bINCLUDE_(?:ASM|RODATA)\s*\(\s*"([^"\n]+)"\s*,\s*(\w+)\s*\)', source)
    ))


def generate_build(output_path=None):
    """Write the build graph; importing this module never writes files."""
    output_path = output_path or PROJECT_ROOT / "build.ninja"
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        n = ninja_syntax.Writer(f)

        n.variable("ninja_required_version", "1.3")
        n.newline()

        n.variable("as", AS)
        n.variable("ld", LD)
        n.variable("cc", ninja_syntax.escape(shlex.quote(CC)))
        n.variable("cpp", CPP)
        n.variable("cpp263", ninja_syntax.escape(shlex.quote(CPP263)))
        n.variable("cplus", ninja_syntax.escape(shlex.quote(CPLUS)))
        n.variable("objcopy", OBJCOPY)
        n.variable("python", ninja_syntax.escape(shlex.quote(PYTHON)))
        n.variable("maspsx", MASPSX)
        n.variable("splat", SPLAT)

        n.variable("asflags", " ".join(AS_FLAGS))
        n.variable("ldflags", " ".join(LD_FLAGS))
        n.variable("cppflags", " ".join(CPP_FLAGS))
        n.variable("cflags", " ".join(C_FLAGS))
        n.variable("cflags_g8", " ".join(C_FLAGS_G8))
        n.variable("cppplusflags", " ".join(CPPPLUS_FLAGS))
        n.variable("cplusflags", " ".join(CPLUS_FLAGS))
        n.variable("maspsxflags", " ".join(MASPSX_FLAGS))
        n.variable("clang_format", CLANG_FORMAT)
        n.variable("clang_tidy", CLANG_TIDY)
        n.variable("formatfiles", " ".join(shlex.quote(f) for f in format_targets))
        n.variable("tidyfiles", " ".join(shlex.quote(f) for f in tidy_targets))
        n.variable("tidyflags", " ".join(TIDY_FLAGS))

        # Keep ninja_log out of working dir
        n.variable("builddir", BUILD_DIR)
        n.newline()

        # Rule for .s files
        n.rule("asm", command="$as $asflags -o $out $in", description="AS $out")
        n.newline()

        # Rule for .c files
        n.rule(
            "cc",
            command="$python tools/compile_c.py --cpp $cpp -MMD -MF $out.d -MT $out $cppflags $in --cc $cc $cflags --maspsx $python $maspsx $maspsxflags --as $as $asflags -o $out",
            description="CC $out",
            depfile="$out.d",
            deps="gcc",
        )

        # G8 files
        n.rule(
            "cc_g8",
            command="$python tools/compile_c.py --cpp $cpp -MMD -MF $out.d -MT $out $cppflags -DCCG8 $in --cc $cc $cflags_g8 --maspsx $python $maspsx $maspsxflags --as $as $asflags -o $out",
            description="CC $out",
            depfile="$out.d",
            deps="gcc",
        )
        n.newline()

        # Rule for .cpp files
        n.rule(
            "cplus",
            command="$python tools/compile_c.py --cpp $cpp263 $cppplusflags $in --cc $cplus $cplusflags --maspsx $python $maspsx $maspsxflags --as $as $asflags -o $out",
            description="CXX $out",
            depfile="$out.asmproc.d",
        )

        n.rule(
            "link",
            command=f"$ld -o $out -Map {shlex.quote(MAP_FILE)} -T {shlex.quote(LD_SCRIPT)}"
            f" -T {shlex.quote(UNDEF_SYMS)} -T {shlex.quote(UNDEF_FUNCS)} $ldflags $in",
            description="LINK $out",
        )
        n.newline()

        n.rule("objcopy", command="$objcopy -O binary $in $out", description="OBJCOPY $out")
        n.newline()

        # TQDM_DISABLE=1 drops splat progress bars (token noise for agents / CI logs)
        n.rule(
            "splat",
            command="env TQDM_DISABLE=1 $python $splat $in",
            description="SPLAT $in",
            restat=True,
        )
        n.newline()

        # Ninja cleans generated outputs, never tracked assembly source inputs.
        n.rule("clean_custom", command="ninja -t clean", description="CLEAN")
        n.newline()

        # Full resplit: wipe generated asm/ then splat (use after symbol/map changes)
        n.rule(
            "resplit_custom",
            command="rm -rf asm && env TQDM_DISABLE=1 $python $splat $in",
            description="RESPLIT $in",
        )
        n.newline()

        n.rule("checksha", command="sha1sum --check $in", description="CHECK $in")
        n.newline()

        n.rule("format", command="$clang_format -i $formatfiles", description="FORMAT")
        n.newline()
        n.rule(
            "format_check",
            command="$clang_format --dry-run --Werror $formatfiles",
            description="FORMAT-CHECK",
        )
        n.newline()
        n.rule("tidy", command="$clang_tidy $tidyfiles -- $tidyflags", description="TIDY")
        n.newline()

        included_assembly = {
            filename: assembly_includes(filename)
            for filename in c_psyq_targets + c_game_targets + cpp_targets
        }
        split_outputs = list(dict.fromkeys(
            [LD_SCRIPT, UNDEF_SYMS, UNDEF_FUNCS]
            + asm_game_targets + asm_psyq_targets + asm_data_targets + asm_header_targets
            + [path for paths in included_assembly.values() for path in paths]
        ))
        n.build(split_outputs, "splat", SPLAT_CONFIG, implicit=[ROM, SYMBOLS])
        n.newline()

        obj_files = []

        for filename in asm_auto_targets + asm_targets:
            out_file = BUILD_DIR + "/" + filename + O_EXT
            obj_files.append(out_file)
            n.build(out_file, "asm", filename,
                    implicit=ASM_INCLUDES)

        for filename in c_psyq_targets:
            out_file = BUILD_DIR + "/" + filename + O_EXT
            obj_files.append(out_file)
            n.build(out_file, "cc", filename,
                    implicit=[LD_SCRIPT, "tools/compile_c.py"] + ASM_INCLUDES + included_assembly[filename])

        for filename in c_game_targets:
            out_file = BUILD_DIR + "/" + filename + O_EXT
            obj_files.append(out_file)
            n.build(out_file, "cc_g8" if c_source_uses_g8(filename) else "cc", filename,
                    implicit=[LD_SCRIPT, "tools/compile_c.py"] + ASM_INCLUDES + included_assembly[filename])

        for filename in cpp_targets:
            out_file = BUILD_DIR + "/" + filename + O_EXT
            obj_files.append(out_file)
            n.build(out_file, "cplus", filename,
                    implicit=[LD_SCRIPT, "tools/compile_c.py"] + ASM_INCLUDES + included_assembly[filename])

        n.newline()

        # Link binary to elf
        n.build(
            ELF,
            rule="link",
            inputs=obj_files,
            implicit=[LD_SCRIPT, UNDEF_SYMS, UNDEF_FUNCS],
        )
        n.newline()

        # Build final exe
        n.build(
            EXE,
            rule="objcopy",
            inputs=ELF,
        )
        n.newline()

        # Default rule
        n.build("all", "phony", EXE)
        n.default("all")
        n.newline()

        # Alias to all
        n.build("build", "phony", "all")
        n.newline()

        # Split rom
        n.build("split", "phony", split_outputs)
        n.newline()

        # Wipe asm/ and split from scratch
        n.build("resplit", "resplit_custom", SPLAT_CONFIG)
        n.newline()

        # Clean helper
        n.build("clean", "clean_custom")
        n.newline()

        n.build("format", "format")
        n.newline()

        n.build("format-check", "format_check")
        n.newline()

        n.build("tidy", "tidy")
        n.newline()

        # Check hash
        n.build("check", "checksha", EXE_HASH, implicit=[EXE])
        n.newline()

        # n.build("test", "cplus", "tests/test.cpp")
        # n.newline()


def setup():
    """Install any missing dependencies"""
    req_file = PROJECT_ROOT / "requirements.txt"
    print("Installing requirements...", flush=True)
    subprocess.check_call([PYTHON, "-m", "pip", "install", "-r", str(req_file)])

    # Git stores these legacy Linux binaries without executable permissions.
    for name in ("cc1", "cc1plus", "cpp", "gcc", "g++"):
        path = PROJECT_ROOT / GCC_DIR / name
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    maspsx_dir = PROJECT_ROOT / TOOLS_DIR / "maspsx"
    if not os.path.isdir(maspsx_dir):
        print(f"Installing maspsx to {maspsx_dir}...")

        subprocess.check_call(
            [
                "git",
                "clone",
                "--recursive",
                "https://github.com/mkst/maspsx",
                str(maspsx_dir),
            ]
        )
        subprocess.check_call(["git", "-C", str(maspsx_dir), "checkout", "--detach", MASPSX_REVISION])


def check_rom(path=None):
    """Validate the original executable before generating build files."""
    path = Path(path) if path is not None else PROJECT_ROOT / ROM
    if not path.is_file():
        return f"Missing original executable: {path}. Supply rom/SLPS_015.56."
    expected = (PROJECT_ROOT / EXE_HASH).read_text(encoding="utf-8").split()[0]
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        return f"Wrong executable SHA-1: {actual}; expected {expected}."
    return None


def check_dependencies():
    """Return actionable errors without modifying the checkout."""
    errors = []
    if sys.platform != "linux":
        errors.append("Builds require Linux or WSL. Run these commands in a Linux terminal.")
    for name in (SPLAT_CONFIG, SYMBOLS, MASPSX):
        if not (PROJECT_ROOT / name).is_file():
            errors.append(f"Missing {name}; run python3 configure.py setup for tools.")
    for path in (CC, CPP263, CPLUS):
        if not Path(path).is_file():
            errors.append(f"Missing compiler: {path}.")
        elif sys.platform == "linux" and not os.access(path, os.X_OK):
            errors.append(f"Compiler is not executable: {path}; run configure.py setup.")
    for tool in (CROSS + "as", CROSS + "ld", CPP, OBJCOPY, "ninja"):
        if not shutil.which(tool):
            errors.append(f"Missing {tool}; install the MIPS toolchain and Ninja in Linux.")
    if importlib.util.find_spec("splat") is None:
        errors.append("Missing Python package splat; run python3 configure.py setup.")
    rom_error = check_rom()
    if rom_error:
        errors.append(rom_error)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Configure the LSD: Dream Emulator build.")
    parser.add_argument("command", nargs="?", default="configure",
                        choices=("configure", "setup", "doctor"))
    args = parser.parse_args(argv)
    os.chdir(PROJECT_ROOT)
    try:
        if args.command == "setup":
            if sys.platform != "linux":
                parser.exit(1, "Setup requires Linux or WSL. Open a Linux terminal first.\n")
            setup()
            return 0
        errors = check_dependencies()
        if errors:
            for error in errors:
                print(f"[!] {error}", file=sys.stderr)
            return 1
        if args.command == "doctor":
            print("Build prerequisites and original executable are ready.")
        else:
            generate_build()
            print("Generated build.ninja. Run ninja check to build and verify the executable.")
        return 0
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
