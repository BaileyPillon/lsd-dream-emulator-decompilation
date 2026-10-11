#include "common.h"

/* Original PlayStation BIOS B0 calls, kept separate from game save formatting. */
INCLUDE_ASM("asm/nonmatchings/psyq/card/file_io", lseek);
INCLUDE_ASM("asm/nonmatchings/psyq/card/file_io", close);
INCLUDE_ASM("asm/nonmatchings/psyq/card/file_io", delete);
INCLUDE_ASM("asm/nonmatchings/psyq/card/file_io", format);
INCLUDE_ASM("asm/nonmatchings/psyq/card/file_io", read);
INCLUDE_ASM("asm/nonmatchings/psyq/card/file_io", open);
