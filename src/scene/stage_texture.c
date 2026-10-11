#include "scene/stage_texture.h"

extern class_stage_texture_vtable_t D_8006F0B8;
extern s16 D_8008A92C;

void file_driver_lock(void);
void file_driver_unlock(void);
void func_80043648(class_stage_texture_slot_t *slot, s32 arg1);

class_stage_texture_t *func_80043008(s32 Unk1, s32 Unk2) {
    class_stage_texture_t *allocated = ALLOCATE_STRUCT(class_stage_texture_t);

    if (allocated) {
        func_80043830()->Construct(allocated, Unk1);
        return allocated;
    }

    return NULL;
}

void func_80043068(class_stage_texture_t *This, s32 path) {
    u16 row;
    s32 index;
    s32 offset;
    s16 width;
    s16 height;
    u16 step;
    u16 shift;
    s16 *slot;
    void *header;

    (*(void (**)(void *))((s32)get_file_driver() + 8))(This);
    This->vtable = func_80043830();
    row = 0;
    index = 0;
    width = 0x100;
    height = 1;
    offset = 0x40;
    This->m_Unk10 = 0;
    This->m_Unk11 = 0;
    This->m_Unk14 = 0;
    This->m_Unk12 = 0;
    This->m_Unk13 = 0;
    step = 1 << D_8008A92C;
    shift = D_8008A92C;
    do {
        u16 y = row + 0x1E0;
        row += step;
        slot = (s16 *)((u8 *)This + offset);
        offset += 0x10;
        slot[0] = shift;
        slot[1] = step;
        slot[2] = 0;
        slot[3] = y;
        slot[4] = width;
        slot[5] = height;
        index++;
    } while (index < 4);
    header = memory_allocate_mem(0x24);
    if (header != NULL) {
        This->m_Unk12 = (s32)memory_allocate_mem(0x800);
        if (This->m_Unk12 != 0) {
            This->m_Unk4 = 0x24;
            This->m_Unk3 = (s32)header;
            *(u16 *)((u8 *)This + 0x2A) = 9;
            This->m_Unk31 = 0;
            ((void (*)(void *, s32, s32, s32))This->vtable->Unk16)(This, path, 1, 0);
            ((void (*)(void *, s32, s32))This->vtable->Unk20)(This, This->m_Unk12, 0x800);
        }
    }
}

void func_800431A8(class_stage_texture_t *This) {
    destroy_list(This->m_Unk11, This->m_Unk10);
    memory_free_mem(This->m_Unk11);
    (*(void (**)(class_stage_texture_t *))((s32) get_file_driver() + 12))(This);
}

u32 func_800434DC(class_stage_texture_t *);
void *func_80043B88(s32);

void func_80043200(class_stage_texture_t *This) {
    s32 size;
    u32 index;
    s32 *slot;

    file_driver_lock();
    switch (*(u16 *)((u8 *)This + 0x2A)) {
    case 9:
        if (!(This->m_Unk8 & 0x80)) {
            break;
        }
        __builtin_memcpy((void *)This->m_Unk3, (void *)This->m_Unk12, 0x24);
        memory_free_mem(This->m_Unk12);
        size = func_800434DC(This);
        This->m_Unk11 = (s32)memory_allocate_mem(*(u32 *)This->m_Unk3 * 4);
        if (This->m_Unk11 == 0) {
            goto failed;
        }
        This->m_Unk12 = (s32)memory_allocate_mem(size);
        if (This->m_Unk12 == 0) {
            goto failed;
        }
        This->m_Unk13 = size;
        ((void (*)(void *, s32, s32))This->vtable->Unk18)(This, *(s32 *)(This->m_Unk3 + 4), 0);
        ((void (*)(void *, s32, s32))This->vtable->Unk20)(This, This->m_Unk12, size);
        *(u16 *)((u8 *)This + 0x2A) = 10;
        break;
    case 10:
        if (!(This->m_Unk8 & 0x80)) {
            break;
        }
        index = This->m_Unk10;
        slot = (s32 *)This->m_Unk11 + index;
        *slot = (s32)func_80043B88(0);
        *(s32 *)(*slot + 0x10) = This->m_Unk12;
        *(s32 *)(*slot + 0x14) = 0;
        *(void **)(*slot + 0x34) = This->m_Slots;
        (*(void (**)(void *))(*(s32 *)*slot + 0x64))((void *)*slot);
        index++;
        (*(void (**)(void *))(*(s32 *)*slot + 0x78))((void *)*slot);
        This->m_Unk10 = index;
        if (index < *(u32 *)This->m_Unk3) {
            ((void (*)(void *, s32, s32))This->vtable->Unk18)(This, *((u32 *)This->m_Unk3 + index + 1), 0);
            ((void (*)(void *, s32, s32))This->vtable->Unk20)(This, This->m_Unk12, This->m_Unk13);
            *(u16 *)((u8 *)This + 0x2A) = 10;
        } else {
            memory_free_mem(This->m_Unk12);
            This->m_Unk12 = 0;
            This->m_Unk13 = 0;
            *(u16 *)((u8 *)This + 0x2A) = 0;
            This->m_Unk14 = 1;
            (*(void (**)(void *))((s32)get_file_driver() + 0x64))(This);
        }
        break;
    }
    goto done;
failed:
    This->m_Unk31 = 1;
done:
    file_driver_unlock();
}


/* Return the largest value in the texture table's records. */
u32 func_800434DC(class_stage_texture_t *This) {
    u32 *table;
    u32 counter;
    u32 count;
    u32 max;
    u32 limit;
    u32 *walk;
    u32 value;

    table = (u32 *)This->m_Unk3;
    count = *(u32 *)This->m_Unk3;
    max = 0;
    counter = 0;
    if (counter < count) {
        limit = count;
        walk = table;
        do {
            value = *(u32 *)((u8 *)walk + 0x14);
            walk = (u32 *)((u8 *)walk + 4);
            if (max < value) {
                max = value;
            }
            counter += 1;
        } while (counter < limit);
    }
    return max;
}

void func_80043538(class_stage_texture_t *This, s32 a2, s16 a3) {
    class_stage_texture_slot_t *slot;

    slot = &This->m_Slots[a2];
    slot->unk0 = a3;
    slot->unk1 = 1 << slot->unk0;
}

void func_8004355C(class_stage_texture_t *This, s32 arg1) {
    s32 i;

    file_driver_lock();
    i = 0;
    do {
        ((void (*)(void *, s32, s32)) This->vtable->Unk31)(This, i, arg1);
        i += 1;
    } while (i < 4);
    file_driver_unlock();
}

void func_800435D0(class_stage_texture_t *This, s32 arg1, s8 *arg2) {
    class_stage_texture_slot_t *slot;

    file_driver_lock();
    slot = &This->m_Slots[arg1];
    __builtin_memcpy(slot->rgb, arg2, 3);
    func_80043648(slot, arg1);
    file_driver_unlock();
}

typedef struct {
    s16 x;
    u16 y;
    s16 w;
    u16 h;
} stage_texture_rect_t;
void StoreImage(stage_texture_rect_t *, u16 *);
void LoadImage(stage_texture_rect_t *, u16 *);
void DrawSync(s32);

void func_80043648(class_stage_texture_slot_t *slot, s32 arg1) {
    stage_texture_rect_t dst;
    stage_texture_rect_t src;
    u16 buf[0x100];
    u16 pixels[0x100];
    u8 r, g, b;
    s32 shift, row, i, weight, roff, goff, boff;

    src.x = 0;
    src.w = 0x100;
    src.h = 1;
    src.y = (arg1 << D_8008A92C) + 0x1E0;
    StoreImage(&src, pixels);
    DrawSync(0);
    dst.h = 1;
    row = 0;
    dst.x = 0;
    dst.y = 0;
    dst.w = 0x100;
    r = (u8)slot->rgb[0];
    g = (u8)slot->rgb[1];
    b = (u8)slot->rgb[2];
    slot->unkA = slot->unk1;
    shift = 0xC - slot->unk0;
    for (row = 0; row < slot->unk1 - 1; row++) {
        weight = (row + 1) << shift;
        roff = r * weight;
        goff = g * weight;
        boff = b * weight;
        weight = 0x1000 - weight;
        i = 0;
        for (i = 0; i < src.w; i++) {
            if (pixels[i] == 0) {
                buf[i] = pixels[i];
            } else {
                s32 red, green, blue;
                red = (pixels[i] & 0x1F) << 3;
                red = ((red * weight) + roff) >> 0xF;
                green = (pixels[i] >> 2) & 0xF8;
                green = ((green * weight) + goff) >> 0xF;
                blue = (pixels[i] >> 7) & 0xF8;
                blue = ((blue * weight) + boff) >> 0xF;
                buf[i] = (pixels[i] & 0x8000) | red | (green << 5) | (blue << 0xA);
            }
        }
        dst.y = src.y + row + src.h;
        DrawSync(0);
        LoadImage(&dst, buf);
    }
}

class_stage_texture_vtable_t *func_80043830(void) {
    return &D_8006F0B8;
}
