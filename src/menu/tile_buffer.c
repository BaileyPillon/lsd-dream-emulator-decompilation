#include "menu/tile_buffer.h"

void func_80044D40(tile_buffer_t *arg0, s32 arg1, s32 arg2);
void func_80044DC8(tile_buffer_t *This);
void func_80044E10(tile_buffer_t *This);
void func_80044E64(tile_buffer_t *This);
s32 file_buf_destroy(void *);
void file_buf_release(void *);
void nullsub13(void *);

tile_buffer_vtable_t D_8006F498 = {
    0x203,
    (base_class_t * (*) (base_class_t *) ) file_buf_destroy,
    func_80044D40,
    func_80044DC8,
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
    func_80044E10,
    NULL,
    NULL,
    NULL,
    NULL,
    func_80044E64,
};

tile_buffer_t *func_80044CD4(s32 Unk1, void *Unk2) {
    tile_buffer_t *allocated = ALLOCATE_STRUCT(tile_buffer_t);

    if (allocated) {
        func_80044F20()->Construct(allocated, Unk1, Unk2);
        return allocated;
    }

    return NULL;
}

/* These consumed lookup/call inputs retain the original compiler frame.
 * See docs/ATLAS_TILE_STORAGE.md for the observed allocation. */
typedef void (*tile_base_method_t)(tile_buffer_t *);

static inline tile_base_method_t tile_base_read_method(void *input) {
    struct {
        void *value;
    } driver = { input };
    typedef char checked_driver[(sizeof(driver) == 4) ? 1 : -1];

    return *(tile_base_method_t *)(driver.value + 8);
}

static inline void tile_base_invoke(tile_buffer_t *object, tile_base_method_t callback) {
    struct {
        tile_buffer_t *value;
    } receiver = { object };
    typedef char checked_receiver[(sizeof(receiver) == 4) ? 1 : -1];
    struct {
        tile_base_method_t value;
    } method = { callback };
    typedef char checked_method[(sizeof(method) == 4) ? 1 : -1];

    method.value(receiver.value);
}

static inline s32 tile_base_default_mode(s32 input) {
    struct {
        s32 value;
    } mode = { input };
    typedef char checked_mode[(sizeof(mode) == 4) ? 1 : -1];

    return mode.value == 0;
}

void func_80044D40(tile_buffer_t *arg0, s32 arg1, s32 arg2) {
    tile_base_invoke(arg0, tile_base_read_method(get_file_driver()));
    arg0->vtable = func_80044F20();
    arg0->m_Unk14 = arg2;
    arg0->m_Unk15_2 = 0;
    if (tile_base_default_mode(arg1)) {
        arg0->m_Unk15_1 = 1;
        arg0->m_Unk9_2 = 0;
        arg0->vtable->Unk24(arg0);
    }
}

void func_80044DC8(tile_buffer_t *This) {
    memory_free_mem(This->m_Unk13);
    (*(void (**)(tile_buffer_t *))((s32) get_file_driver() + 12))(This);
}

void func_80044E10(tile_buffer_t *This) {
    if (!This->m_Unk9_2) {
        This->vtable->Unk29(This);
        This->m_Unk15_2 = 1;
    }
}

/* These consumed lookup/call inputs retain the original compiler frame.
 * See docs/ATLAS_TILE_STORAGE.md for the observed allocation. */
static inline void *tile_allocate_indices(s32 input) {
    struct {
        s32 value;
    } view = { input };
    typedef char checked_input_view[(sizeof(view) == 4) ? 1 : -1];

    return memory_allocate_mem(view.value);
}

void func_80044E64(tile_buffer_t *This) {
    s16 *mem;
    s32 count;
    s32 i;
    s32 fifteen;

    This->m_Unk12 = *(s32 *) (This->m_Unk14 + 0x2C);

    if (This->m_Unk15_1) {
        This->m_Unk10_2 = 0x14;
        fifteen = 0xF;
        count = *(volatile u16 *) &This->m_Unk10_2 * fifteen;
        This->m_Unk10_0 = 0x10;
        This->m_Unk10_1 = 0x10;
        This->m_Unk11_0 = 0xF;
        if ((This->m_Unk13 = (s32) tile_allocate_indices(count << 1)) != 0) {
            mem = This->m_Unk13;
            i = 0;
            if (count != 0) {
                do {
                    *mem++ = i++;
                } while (i < count);
            }
            return;
        }
    }
    This->vtable->file_buf_release(This);
}

tile_buffer_vtable_t *func_80044F20(void) {
    return &D_8006F498;
}
