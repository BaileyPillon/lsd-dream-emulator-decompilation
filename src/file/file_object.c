#include "common.h"

#include "file/file_object.h"

extern file_object_vtable_t g_CLASS_1C92C_VTABLE;

file_object_t *class_1C92C_create(u32 Unk1) {
    file_object_t *allocated = ALLOCATE_STRUCT(file_object_t);

    if (allocated) {
        class_1C92C_get_vtable()->class_1C92C_construct(allocated, Unk1);
        return allocated;
    }

    return NULL;
}

void class_1C92C_construct(file_object_t *This, s32 Unk) {
    void *base;

    base = get_file_driver();
    (*(void (**)(void *))((s32) base + 8))(This);

    This->vtable = class_1C92C_get_vtable();
    This->m_Unk10 = 0;
    This->m_Unk11 = 0;

    if (Unk) {
        This->vtable->Unk26(This, Unk);
    }
}

void class_1C92C_cleanup(void *This) {
    void *base;

    base = get_file_driver();
    (*(void (**)(void *))((s32) base + 0xC))(This);
}

void class_1C92C_unk24(file_object_t *This) {
    void (**base)(void *);

    This->m_Unk11 = 1;
    base = (void (**)(void *)) get_file_driver();
    base[25](This);
}

static inline u8 *file_object_record(s32 base, s32 offset) {
    return (u8 *)(base + offset);
}

s32 class_1C92C_unk29(file_object_t *This, u8 *arg1, s32 arg2) {
    s32 temp;
    u8 *var;
    s32 height;
    void *obj;

    if (arg2 < 0x190) {
        temp = *(s32 *)(arg1 + 0x34);
        if (temp != 0) {
            var = file_object_record(This->m_Unk3, temp);
            *(s32 *)(arg1 + 0x30) = 1;
        } else {
            var = (u8 *)This->m_Unk3 + (arg2 * 0xC + 8);
            *(s32 *)(arg1 + 0x30) = 0;
        }
        *(s32 *)(arg1 + 0x34) = *(s32 *)(var + 8);
        if (*(u8 *)var != 0) {
            *(s32 *)(arg1 + 0xC) = ((arg2 % 20) << 11) + 0x400;
            height = *(s16 *)(var + 6);
            *(s32 *)(arg1 + 0x14) = ((arg2 / 20) << 11) + 0x400;
            *(s32 *)(arg1 + 0x10) = height << 11;
            *(s16 *)(arg1 + 0x1A) = *(u8 *)(var + 5) << 10;
            *(s16 *)(arg1 + 0x2C) = *(u8 *)(var + 1);
            *(s16 *)(arg1 + 0x2E) = *(u8 *)(var + 4);
            temp = *(u16 *)(var + 2);
            *(s32 *)(arg1 + 0x38) = temp;

            obj = (void *)This->m_Unk10;
            return (*(s32 (**)(void *, s32, s32, u8 *))((u8 *)*(void **)obj + 0x80))(
                obj, temp, arg2, arg1);
        }
        return -1;
    }
    return 0;
}

file_object_vtable_t *class_1C92C_get_vtable(void) {
    return &g_CLASS_1C92C_VTABLE;
}
