#include "sound/seq_file.h"

#include "base/base.h"
#include "file/file_buf.h"

/* File-driver-backed SEQ storage. m_Flag is raised by the load-completion
 * callback and cleared before the inherited file driver releases its data. */
s32 file_buf_destroy(void *);
void nullsub13(void *);
void file_buf_release(void *);

void seq_file_construct(seq_file_t *This, unsigned char *Path);
void seq_file_cleanup(seq_file_t *This);
void seq_file_set_flag(seq_file_t *This);

seq_file_vtable_t g_SEQ_FILE_VTABLE = {
    0xB03,
    (base_class_t *(*)(base_class_t *)) file_buf_destroy,
    seq_file_construct,
    seq_file_cleanup,
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
    seq_file_set_flag,
    NULL,
    NULL,
    NULL,
    NULL,
};

seq_file_t *seq_file_create(u32 PathAddress) {
    seq_file_t *allocated = ALLOCATE_STRUCT(seq_file_t);

    if (allocated) {
        seq_file_get_vtable()->Construct(allocated, PathAddress);
        return allocated;
    }

    return NULL;
}

void seq_file_construct(seq_file_t *This, unsigned char *Path) {
    void *file_driver;
    unsigned char path_buffer[32];

    file_driver = get_file_driver();

    ((void (*)(seq_file_t *))(*((void (**)(void))((char *) file_driver + 8))))(This);

    This->vtable = (seq_file_vtable_t *) seq_file_get_vtable();
    This->m_Flag = 0;

    if (Path) {
        strcpy((char *) path_buffer, (char *) Path);
        ((void (*)(seq_file_t *, unsigned char *)) This->vtable->pad10)(This, path_buffer);
    }
}

void seq_file_cleanup(seq_file_t *This) {
    void *file_driver;

    This->m_Flag = 0;
    file_driver = get_file_driver();

    ((void (*)(seq_file_t *))(*((void (**)(void))((char *) file_driver + 12))))(This);
}

void seq_file_set_flag(seq_file_t *This) {
    This->m_Flag = 1;
}

seq_file_vtable_t *seq_file_get_vtable(void) {
    return &g_SEQ_FILE_VTABLE;
}
