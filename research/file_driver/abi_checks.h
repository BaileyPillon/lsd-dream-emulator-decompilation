/* Analysis-only layout and result assertions for the matching PS1 compiler. */
#include "file/file_buf.h"
#include "file/debug_file_driver.h"

#define FILE_ABI(name, condition) typedef char file_abi_##name[(condition) ? 1 : -1]
FILE_ABI(pointer_width, sizeof(void *) == 4);
FILE_ABI(signed_word_width, sizeof(s32) == 4);
FILE_ABI(unsigned_word_width, sizeof(u32) == 4);
FILE_ABI(file_object_size, sizeof(file_buf_t) == 0x2C);
FILE_ABI(common_open_slot, (u32) &((file_buf_vtable_t *) 0)->Open == 0x44);
FILE_ABI(common_read_slot, (u32) &((file_buf_vtable_t *) 0)->Read == 0x54);
FILE_ABI(debug_open_slot, (u32) &((debug_file_driver_vtable_t *) 0)->debug_file_driver_open == 0x44);
FILE_ABI(debug_read_slot, (u32) &((debug_file_driver_vtable_t *) 0)->debug_file_driver_read == 0x54);
FILE_ABI(common_read_result, sizeof(((file_buf_vtable_t *) 0)->Read((file_buf_t *) 0, 0, 0)) == 4);
FILE_ABI(debug_read_result, sizeof(((debug_file_driver_vtable_t *) 0)->debug_file_driver_read((file_buf_t *) 0, 0, 0)) == 4);
#undef FILE_ABI
