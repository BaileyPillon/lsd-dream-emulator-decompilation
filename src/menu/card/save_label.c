#include "menu/card/save_label.h"

extern s8 *D_8008AAC4;
extern s32 atoi(char *);

/* Apply the selected slot's two-byte label to the save-title template. */
void func_800507F8(s8 *title, const u8 *filename) {
    s32 offset;
    s32 slot;

    if (filename != NULL) {
        offset = 13;
        if ((u32) (filename[14] - '8') < 2) {
            offset = 14;
        }

        __builtin_memcpy(title + 0x18, D_8008AAC4 + 0x1E, 2);
        __builtin_memcpy(title + 6, D_8008AAC4 + 0x1E, 12);
        slot = atoi((char *) filename + offset) - 1;
        __builtin_memcpy(title + 8, D_8008AAC4 + slot * 2, 2);
    } else {
        __builtin_memcpy(title + 6, D_8008AAC4 + 0x1E, 6);
    }
}
