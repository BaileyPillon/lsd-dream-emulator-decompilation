/* Analysis-only assertions against independently checked original word accesses. */
#include "graphics/display.h"
#define CALLBACK_ABI(name, condition) typedef char callback_abi_##name[(condition) ? 1 : -1]
CALLBACK_ABI(pointer_width, sizeof(void *) == 4);
CALLBACK_ABI(callback_width, sizeof(display_vsync_callback_t) == 4);
CALLBACK_ABI(display_size, sizeof(display_t) == 0x34);
CALLBACK_ABI(table_size, sizeof(display_vtable_t) == 0x88);
CALLBACK_ABI(callback_offset, (u32)&((display_t *)0)->m_VsyncCallback == 0x30);
CALLBACK_ABI(setter_slot, (u32)&((display_vtable_t *)0)->display_set_vsync_callback == 0x84);
CALLBACK_ABI(status_word, sizeof(((display_t *)0)->m_VsyncCallback()) == 4);
#undef CALLBACK_ABI
