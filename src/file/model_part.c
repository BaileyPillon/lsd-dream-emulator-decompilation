#include "file/model_part.h"

extern model_part_vtable_t D_8006F240;

model_part_t *func_80043E84(s32 Unk1) {
    model_part_t *allocated = ALLOCATE_STRUCT(model_part_t);

    if (allocated) {
        func_800441A4()->Construct(allocated, Unk1);
        return allocated;
    }

    return NULL;
}

void func_80043EE4(model_part_t *This, s32 *Unk) {
    void *unk_class = get_file_driver();
    (*(void (**)(model_part_t *))(unk_class + 8))(This);

    This->vtable = func_800441A4();

    if (*Unk) {
        This->m_Unk3 = *Unk;
        This->m_Unk4 = 0;
        This->vtable->Unk24(This);
    } else {
        This->vtable->Unk26(This, Unk[1]);
    }
}

void func_80043F78(model_part_t *This) {
    void *unk = get_file_driver();
    (*(void (**)(model_part_t *))(unk + 12))(This);
}

u8 func_80043FB0(model_part_t *This, u8 *types, s32 *index) {
    return This->vtable->Unk30(This, types, index, (u8 *)(This->m_Unk3 + 8));
}

u32 *func_8004416C(model_part_t *, u32 *, u8 *, u8 *, u8 *, u8 *);

u8 func_80043FE4(model_part_t *This, u8 *out, s32 *arg2, u8 *src) {
    u8 type;
    u8 kind;
    u8 flag;
    u8 words;
    u16 count;
    u32 i;
    u8 written;
    s32 found;
    s32 k;

    count = *(u16 *)(src + 2);
    src += 8;
    i = 0;
    written = 0;
    found = 0;
    for (; i < count; i++) {
        func_8004416C(This, (u32 *)src, &type, &kind, &flag, &words);
        if (kind == 8 && flag == 0) {
            written++;
            if (out != NULL) {
                *out++ = type;
            }
        } else if (kind == 2) {
            if (out != NULL) {
                if (arg2 != NULL && *(u16 *)(src + 4) == *arg2) {
                    /* The native count wraps to a byte before both promotions. */
                    out -= (u16)written;
                    for (k = 0; k < (s16)written; k++) {
                        if (*out++ == type) {
                            found = k;
                            break;
                        }
                    }
                }
            } else if (arg2 != NULL) {
                found++;
            }
        }
        src += words * 4;
    }
    if (arg2 != NULL) {
        *arg2 = found;
    }
    return written;
}

u32 *func_8004416C(model_part_t *This, u32 *Src, u8 *dst1, u8 *dst2, u8 *dst3, u8 *dst4) {
    u32 val;

    val = *Src;
    *dst1 = val;
    *dst2 = (val >> 16) & 0xF;
    *dst3 = (val >> 20) & 0xF;
    *dst4 = val >> 24;
    return Src + 1;
}

model_part_vtable_t *func_800441A4(void) {
    return &D_8006F240;
}
