#include "graphics/effect.h"
#include "graphics/effect_base.h"

extern effect_vtable_t g_EFFECT_VTABLE;

extern s32 D_8006EAA8[];
extern s32 D_8006EA90[];

effect_t *effect_create(s32 Unk1, s32 Unk2, s32 Unk3) {
    effect_t *allocated = ALLOCATE_STRUCT(effect_t);

    if (allocated) {
        effect_get_vtable()->effect_construct(allocated, Unk1, Unk2, Unk3);
        return allocated;
    }

    return NULL;
}

void effect_construct(effect_t *This, s32 Unk1, s32 Unk2, s32 Unk3) {
    effect_base_vtable_t *parent;
    void *color;

    parent = func_800408BC();
    if (Unk2 != 0) {
        color = (u8 *) &D_8006EA90 + (Unk2 * 3);
    } else {
        color = &D_8006EAA8;
    }
    parent->Construct(This, Unk1, (u32) color, Unk3);
    This->vtable = effect_get_vtable();
    This->vtable->Unk15(This, Unk2);
}

void effect_reset(effect_t *This, s32 Unk2) {
    This->m_Variant = Unk2;
    This->m_State = 0;
    This->m_ColorStep = 10;
    This->m_ColorChannels = 0;
    This->m_Mode = 0;
    This->vtable->Unk23(This, 0);
    This->vtable->Unk24(This, 0);
    This->m_Unk37 = 0;
}

void effect_tick(effect_t *This, int Unk2, int Unk3) {
    if (Unk3 == 2) {
        s32 value = This->m_Life;

        This->m_Life = value - 1;

        if (value > 0) {
            if (This->m_Mode != 9) {
                if ((This->m_ColorChannels & 4) != 0) {
                    ((u8 *) &This->m_Color)[0] += (u8) This->m_ColorStep;
                }

                if ((This->m_ColorChannels & 2) != 0) {
                    ((u8 *) &This->m_Color)[1] += (u8) This->m_ColorStep;
                }

                if ((This->m_ColorChannels & 1) != 0) {
                    ((u8 *) &This->m_Color)[2] += (u8) This->m_ColorStep;
                }
            }
        } else {
            This->vtable->Unk55(This, Unk2);
        }
    }
}

void effect_set_color_step(effect_t *This, s32 Value) {
    This->m_ColorStep = Value;
}

/* Both start modes forward the attachment target, color variant and mode. */
void effect_start(effect_t *This, base_class_t *Target, s32 Variant, s32 Mode) {
    s32 color_index;

    if (This->m_State == 0) {
        color_index = This->vtable->effect_activate(This, Target, Variant, Mode);
        This->vtable->Unk45(This, 1, (s32 *)((u8 *)D_8006EA90 + color_index * 3));
        This->m_State = 1;
        This->m_ColorStep = -This->m_ColorStep;
    }
}

void effect_start_attached(effect_t *This, base_class_t *Target, s32 Variant, s32 Mode) {
    s32 color_index = Variant;

    if (This->m_State == 0) {
        color_index = This->vtable->effect_activate(This, Target, color_index, Mode);
        if (This->m_Unk37 != 0) {
            This->m_Life -= 1;
        } else {
            This->vtable->Unk45(This, 1, (s32 *)((u8 *)D_8006EAA8 + color_index * 3));
        }
        This->m_State = 2;
    }
}

s32 effect_activate(effect_t *This, base_class_t *Target, s32 Variant, s32 Mode) {
    effect_vtable_t *vtable;
    s32 state;
    s32 life;
    s32 variant;

    vtable = This->vtable;
    variant = Variant;
    if (variant < 0) {
        variant = This->m_Variant;
    } else {
        This->m_Variant = variant;
    }
    state = 1;
    if (variant != 0) {
        This->m_ColorChannels = variant;
    } else {
        state = 2;
        This->m_ColorChannels = 0xF;
    }
    This->m_ColorChannels = variant;
    if (variant == 0) {
        This->m_ColorChannels = 0xF;
    }
    life = 0x100 / This->m_ColorStep;
    This->m_Mode = Mode;
    This->m_Life = life;
    if (This->m_Unk37 != 0) {
        This->m_Life = life - life / This->m_Unk38;
    }
    This->m_Unk32 = This->m_ColorMask / This->m_Life;
    vtable->Attach((base_class_t *) This, Target);
    vtable->Unk24((void *) This, 1);
    vtable->Unk25((void *) This, state);
    vtable->Unk23((void *) This, 1);
    return variant;
}

void effect_deactivate(effect_t *This, s32 arg1) {
    effect_vtable_t *vt;
    s32 state;
    s32 which;

    state = This->m_State;
    vt = This->vtable;
    if (state != 0) {
        if (state == 1) {
            which = 5;
            if (This->m_Unk37 == 0) {
                vt->Unk23(This, 0);
                vt->Unk24(This, 0);
            }
        } else {
            which = 6;
            if (This->m_Unk37 != 0) {
                if (This->m_ColorChannels == 0xF) {
                    vt->Unk45(This, 1, D_8006EAA8);
                }
                vt->Unk24(This, 0);
            }
        }
        vt->Detach(This, arg1);
        if (This->m_ColorStep < 0) {
            This->m_ColorStep = -This->m_ColorStep;
        }
        This->m_State = 0;
        vt->Notify(This, which);
    }
}

s32 effect_get_color_impl(effect_t *This) {
    if (This->m_ColorChannels == 15) {
        return D_8006EAA8;
    }

    return (s32 *) ((s8 *) D_8006EA90 + 3 * This->m_ColorChannels);
}

void effect_save_render_state(effect_t *This, u16 *a, s32 *b) {
    if (This->m_Unk2 != 0) {
        This->m_Unk33 = (u16) This->m_Unk23_1;
        This->m_Unk34 = (u16) This->m_Unk23_2;
        __builtin_memcpy(&This->m_Unk35, &This->m_Unk19, 8);
        This->m_Unk23_1 = a[0];
        This->m_Unk23_2 = a[2];
        __builtin_memcpy(&This->m_Unk19, b, 8);
    }
}

void effect_restore_render_state(effect_t *This) {
    __builtin_memcpy(&This->m_Unk19, &This->m_Unk35, 8);
    This->m_Unk23_1 = This->m_Unk33;
    This->m_Unk23_2 = This->m_Unk34;
}

void effect_set_linked(effect_t *This, s32 Unk2, s32 Unk3) {
    This->m_Unk37 = Unk2;
    This->m_Unk38 = Unk3;
}

effect_vtable_t *effect_get_vtable() {
    return &g_EFFECT_VTABLE;
}
