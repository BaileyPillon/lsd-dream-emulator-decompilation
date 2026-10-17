#include "menu/sprite_atlas.h"

#include <psx/libgpu.h>

#include "base/base.h"
#include "file/file_buf.h"

void func_80044F90(sprite_atlas_t *This, s32 Unk);
void func_8004500C(sprite_atlas_t *This);
void func_80045060(sprite_atlas_t *This);
void func_800450B4(sprite_atlas_t *This);
s32 file_buf_destroy(void *);
void file_buf_release(void *);
void nullsub13(void *);

sprite_atlas_vtable_t D_8006F514 = {
    0x303,
    (base_class_t * (*) (base_class_t *) ) file_buf_destroy,
    func_80044F90,
    func_8004500C,
    base_class_attach,
    base_class_detach,
    base_class_detach_all,
    base_class_iter_children,
    base_class_add_parent,
    base_class_remove_parent,
    base_class_clear_parents,
    base_class_iter_parents,
    base_class_notify,
    base_class_nop,
    base_class_on_notify,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    file_buf_release,
    nullsub13,
    func_80045060,
    NULL,
    NULL,
    NULL,
    NULL,
    func_800450B4,
};

sprite_atlas_t *func_80044F30(u32 Unk1) {
    sprite_atlas_t *allocated = ALLOCATE_STRUCT(sprite_atlas_t);

    if (allocated) {
        func_800451A8()->Construct(allocated, Unk1);
        return allocated;
    }

    return NULL;
}

/* These consumed lookup/call inputs retain the original compiler frame.
 * See docs/ATLAS_TILE_STORAGE.md for the observed allocation. */
typedef void (*atlas_base_method_t)(sprite_atlas_t *);

static inline atlas_base_method_t atlas_base_read_method(void *input) {
    struct {
        void *value;
    } driver = { input };
    typedef char checked_driver[(sizeof(driver) == 4) ? 1 : -1];

    return *(atlas_base_method_t *)(driver.value + 8);
}

static inline void atlas_base_invoke(sprite_atlas_t *object, atlas_base_method_t callback) {
    struct {
        sprite_atlas_t *value;
    } receiver = { object };
    typedef char checked_receiver[(sizeof(receiver) == 4) ? 1 : -1];
    struct {
        atlas_base_method_t value;
    } method = { callback };
    typedef char checked_method[(sizeof(method) == 4) ? 1 : -1];

    method.value(receiver.value);
}

static inline s32 atlas_base_default_mode(s32 input) {
    struct {
        s32 value;
    } mode = { input };
    typedef char checked_mode[(sizeof(mode) == 4) ? 1 : -1];

    return mode.value == 0;
}

void func_80044F90(sprite_atlas_t *This, s32 Unk) {
    atlas_base_invoke(This, atlas_base_read_method(get_file_driver()));
    This->vtable = func_800451A8();
    This->m_Unk12 = 0;
    This->m_Unk11_2 = 0;
    if (atlas_base_default_mode(Unk)) {
        This->m_Unk11_1 = 1;
        This->m_Unk9_2 = 0;
        This->vtable->Unk24(This);
    }
}

void func_8004500C(sprite_atlas_t *This) {
    memory_free_mem(This->m_Unk12);
    memory_free_mem(This->m_Unk10);
    (*(void (**)(sprite_atlas_t *))((s32) get_file_driver() + 12))(This);
}

/* These consumed lookup/call inputs retain the original compiler frame.
 * See docs/ATLAS_TILE_STORAGE.md for the observed allocation. */
typedef void (*atlas_update_method_t)(void *);

static inline u16 atlas_read_update_gate(const u16 *input) {
    struct {
        const u16 *value;
    } gate = { input };
    typedef char checked_gate[(sizeof(gate) == 4) ? 1 : -1];

    return *gate.value;
}

static inline atlas_update_method_t atlas_read_update_method(sprite_atlas_vtable_t *input) {
    struct {
        sprite_atlas_vtable_t *value;
    } table = { input };
    typedef char checked_table[(sizeof(table) == 4) ? 1 : -1];

    return table.value->Unk29;
}

static inline void atlas_invoke_update(sprite_atlas_t *object, atlas_update_method_t callback) {
    struct {
        sprite_atlas_t *value;
    } receiver = { object };
    typedef char checked_receiver[(sizeof(receiver) == 4) ? 1 : -1];
    struct {
        atlas_update_method_t value;
    } method = { callback };
    typedef char checked_method[(sizeof(method) == 4) ? 1 : -1];

    method.value(receiver.value);
}

void func_80045060(sprite_atlas_t *This) {
    if (!atlas_read_update_gate(&This->m_Unk9_2)) {
        atlas_invoke_update(This, atlas_read_update_method(This->vtable));
        This->m_Unk11_2 = 1;
    }
}

typedef struct {
    /* 0x0 */ u8 u;
    /* 0x1 */ u8 v;
    /* 0x2 */ u16 clut;
    /* 0x4 */ u16 pad;
    /* 0x6 */ u16 tpage;
} atlas_cell_t;

void func_800450B4(sprite_atlas_t *This) {
    atlas_cell_t *cell;
    void *mem;
    s32 x;
    s32 u;
    s32 v;
    s32 tpage;
    s32 limit;
    s32 i;

    if (This->m_Unk11_1 == 0) {
        return;
    }
    x = 0x280;
    v = 0;
    u = 0;
    tpage = GetTPage(2, 0, 0x280, 0) & 0xFFFF;
    mem = memory_allocate_mem(0x960);
    This->m_Unk10 = (s32) mem;
    if (mem == NULL) {
        return;
    }
    i = 0;
    cell = (atlas_cell_t *) mem;
    limit = 0x12C;
    do {
        cell->u = u;
        u += 0x10;
        x += 0x10;
        cell->tpage = tpage;
        cell->v = v;
        cell->clut = 0;
        cell->pad = 0;
        if (x >= 0x3C0) {
            u = 0;
            x = 0x280;
            v += 0x10;
        }
        if ((x & 0x3F) == 0) {
            tpage = x >> 6;
            if (v >= 0x100) {
                tpage += 0x10;
            }
            u = 0;
        }
        i++;
        cell++;
    } while (i < limit);
}

sprite_atlas_vtable_t *func_800451A8(void) {
    return &D_8006F514;
}
