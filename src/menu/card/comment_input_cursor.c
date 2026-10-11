#include "menu/card/comment_input.h"
#include "menu/glyph.h"
#include "menu/text_line.h"

extern s32 D_8008AADC;
extern s32 D_8008AAE0;

void func_800518F4(class_comment_input_t *This, s32 arg1, s32 arg2) {
    class_glyph_t *icon;
    s32 position[2];

    if (This->m_Unk17 != 0) {
        position[1] = D_8008AAE0;
        position[0] = arg1 * 7 + D_8008AADC;
        icon = (class_glyph_t *)This->m_Unk15;
        ((void (*)(void *, void *))icon->vtable->Unk46)(icon, position);
        This->m_Unk5 = arg1;
        if (arg2 != 0) {
            ((void (*)(void *, s32))This->vtable->Unk23)(This, 0);
        }
    }
}


#include "menu/card/comment_input.h"
#include "menu/text_line.h"

extern class_comment_input_vtable_t D_80086ED0;
extern u8 *D_8008AAE4;

void func_80051998(class_comment_input_t *This, s32 arg1, s32 arg2, s32 arg3) {
    text_line_t *label;

    if (This->m_Unk17 != 0) {
        ((u8 *) This->m_Unk9)[arg1] = ((u8 *) D_8008AAE4)[arg2];
        label = (text_line_t *) This->m_Unk16;
        ((void (*)(void *, u8, s32)) label->vtable->Unk48)(label, ((u8 *) D_8008AAE4)[arg2], arg1);
        This->m_Unk5 = arg1;
        This->m_Unk6 = arg2;
        if (arg3 != 0) {
            ((void (*)(void *, s32)) This->vtable->Unk23)(This, 0);
        }
    }
}

class_comment_input_vtable_t *func_80051A4C(void) {
    return &D_80086ED0;
}
