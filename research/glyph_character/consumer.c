/* Analysis callers for the recovered character methods; excluded from the game. */
#include "menu/glyph.h"

s32 glyph_character_read(class_glyph_t *glyph) {
    return glyph->vtable->Unk49(glyph);
}

s32 glyph_character_write_read(class_glyph_t *glyph, s32 code) {
    glyph->vtable->Unk48(glyph, code);
    return glyph->vtable->Unk49(glyph);
}
