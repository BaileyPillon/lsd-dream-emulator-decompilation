#include "menu/ui_sprite.h"
#include "base/transform.h"
#include "menu/ui_sprite.h"

extern ui_sprite_vtable_t D_8006F2C4;
extern s8 D_8008A938[];

ui_sprite_t *func_800441B4(s32 Unk1, s32 Unk2) {
    ui_sprite_t *allocated = ALLOCATE_STRUCT(ui_sprite_t);

    if (allocated) {
        func_8004467C()->Construct(allocated, Unk1, Unk2);
        return allocated;
    }

    return NULL;
}

void func_80044220(ui_sprite_t *This, s32 Unk2, s32 Unk3) {
    func_8001E57C()->Construct(This);
    This->vtable = func_8004467C();
    This->vtable->Unk15(This, Unk2, Unk3);
}

void func_80044294(ui_sprite_t *This, u8 *arg1, s32 arg2) {
    if (arg2 == 0) {
        This->m_Unk16 = 0x01000000;
        This->m_Unk18_0 = arg1[0x2C] * *(u16 *) (arg1 + 0x2E);
        This->m_Unk18_1 = arg1[0x2D] * *(u16 *) (arg1 + 0x30);
    } else if (arg2 == 1) {
        This->m_Unk16 = 0x02000000;
        This->m_Unk18_0 = 320;
        This->m_Unk18_1 = 240;
    }

    This->m_Unk17_0 = 0;
    This->m_Unk17_1 = 0;
    This->m_Unk19_0 = 0;
    This->m_Unk19_1 = 0;

    __builtin_memcpy(&This->m_Unk20, &D_8008A938, 3);

    This->m_Unk21 = arg1 + 0x2C;
    This->m_Unk23_0 = 0x1000;
    This->m_Unk23_1 = 0x1000;
    This->m_Unk24 = 0;

    This->m_Unk22_0 = (s16) This->m_Unk18_0 / 2;
    This->m_Unk22_1 = (s16) This->m_Unk18_1 / 2;
}

void func_80044380(ui_sprite_t *This, s32 arg1, u8 *arg2) {
    s32 num = *(s16 *) (arg2 + 8);
    s32 den = *(s16 *) (arg2 + 10);

    s32 val = ((num / den) << 12) + (((num % den) << 12) / den);

    if (arg1 != 0) {
        This->m_Unk24 = val;
    } else {
        This->m_Unk24 += val;
    }
}

/* Adapted from brian-oblivion/lsddecomp, commit 90a398e4f429b4371be05648605fc198b9efb395,
 * src/graphics/bg_layer.c (BgLayer__UpdateScale), dedicated under CC0.
 * Signed numerator/denominator pairs for the X and Y scale.
 * See docs/UI_SCALE_BOUNDS_MATCHING_C.md for provenance and verification. */
typedef struct ui_sprite_scale_ratio { s16 num; s16 den; } ui_sprite_scale_ratio_t;
void func_8004441C(ui_sprite_t *self, s32 set, ui_sprite_scale_ratio_t *src) {
    s32 negX;
    s32 negY;
    s32 den;
    s16 sx;
    s16 sy;
    s32 v;

    negX = 0;
    negY = 0;
    if (src[0].num < 0 || src[0].den < 0) {
        negX = 1;
    }
    if (src[1].num < 0 || src[1].den < 0) {
        negY = 1;
    }
    den = src[0].den;
    if (den != 0) {
        sx = ((src[0].num / den) << 12) + (((src[0].num % den) << 12) / den);
    }
    if (src[1].den != 0) {
        sy = ((src[1].num / src[1].den) << 12) +
             (((src[1].num % src[1].den) << 12) / src[1].den);
    }
    if (set) {
        if (den == 0) {
            self->m_Unk23_0 = 0x1000;
        } else {
            v = sx;
            if (v > 30000) {
                v = 30000;
            }
            self->m_Unk23_0 = v;
        }
        if (src[1].den == 0) {
            self->m_Unk23_1 = 0x1000;
        } else {
            v = sy;
            if (v > 30000) {
                v = 30000;
            }
            self->m_Unk23_1 = v;
        }
    } else {
        if (self->m_Unk23_0 + sx > 30000) {
            if (negX) {
                self->m_Unk23_0 = 1;
            } else {
                self->m_Unk23_0 = 30000;
            }
        } else {
            self->m_Unk23_0 = sx + self->m_Unk23_0;
        }
        if (self->m_Unk23_1 + sy > 30000) {
            if (negY) {
                self->m_Unk23_1 = 1;
            } else {
                self->m_Unk23_1 = 30000;
            }
        } else {
            self->m_Unk23_1 = sy + self->m_Unk23_1;
        }
    }
}

void func_8004464C(ui_sprite_t *This, s32 Unk1, s8 *Data) {
    if (Unk1) {
        __builtin_memcpy(This->m_Unk20, Data, 3);
    }
}

void func_80044674(void) {
}

ui_sprite_vtable_t *func_8004467C(void) {
    return &D_8006F2C4;
}
