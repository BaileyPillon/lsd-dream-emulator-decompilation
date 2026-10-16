/* Target-compiler assertions; this header emits no game data or instructions. */
#include "menu/glyph.h"

#define GLYPH_ABI_CHECK(name, expression) typedef char glyph_abi_##name[(expression) ? 1 : -1]
GLYPH_ABI_CHECK(byte_width, sizeof(u8) == 1);
GLYPH_ABI_CHECK(byte_unsigned, (u8)-1 == 255);
GLYPH_ABI_CHECK(pointer_width, sizeof(void *) == 4);
GLYPH_ABI_CHECK(object_size, sizeof(class_glyph_t) == 0xAC);
GLYPH_ABI_CHECK(table_size, sizeof(class_glyph_vtable_t) == 0xCC);
GLYPH_ABI_CHECK(character_offset, (u32)&((class_glyph_t *)0)->m_Char == 0xA8);
GLYPH_ABI_CHECK(setter_slot, (u32)&((class_glyph_vtable_t *)0)->Unk48 == 0xC4);
GLYPH_ABI_CHECK(getter_slot, (u32)&((class_glyph_vtable_t *)0)->Unk49 == 0xC8);
#undef GLYPH_ABI_CHECK
