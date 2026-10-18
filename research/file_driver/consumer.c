#include "file/file_buf.h"
#include "file/debug_file_driver.h"

void file_open_common(file_buf_t *file, s32 resource, s32 mode, s32 flags) {
    file->vtable->Open(file, resource, mode, flags);
}

s32 file_read_common(file_buf_t *file, s32 destination, u32 bytes) {
    return file->vtable->Read(file, destination, bytes);
}

void file_open_debug(file_buf_t *file, s32 resource, s32 mode, s32 flags) {
    debug_file_driver_vtable_t *table = (debug_file_driver_vtable_t *) file->vtable;
    table->debug_file_driver_open(file, resource, mode, flags);
}

s32 file_read_debug(file_buf_t *file, s32 destination, u32 bytes) {
    debug_file_driver_vtable_t *table = (debug_file_driver_vtable_t *) file->vtable;
    return table->debug_file_driver_read(file, destination, bytes);
}
