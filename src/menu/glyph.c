#include "menu/glyph.h"

#include "menu/sprite_node.h"

#include "base/base.h"

void func_8001CBA4(base_class_t *);
void func_8001CC48(base_class_t *, base_class_t *);
void func_8001CCB4(base_class_t *, base_class_t *);
void func_8001CD20(base_class_t *);
void func_8001CD60(base_class_t *, base_class_t *, s32);
void func_80042170(void *);
void func_8001D008(void *);
void sprite_node_run(void *, void *, void *);
void func_8001D1A4(void *);
void func_8001D204(void *);
void func_8001D280(void *);
void func_8001D33C(void *);
void func_8004220C(void *);
void func_8004223C(void *);
void func_80042268(void *);
void func_8001D3CC(void *);
void func_8001D3F8(void *);
void func_8001D424(void *);
void func_8001D450(void *);
void func_8001D480(void *);
void func_8001D4AC(void *);
void func_8001D4DC(void *);
void func_8001D568(void *);
void func_8001D600(void *);
void func_8001D624(void *);
void func_8001D6A4(void *);
void func_80042294(void *);
void func_8001D6B4(void *);
void func_8001D714(void *);
void func_8001D950(void *);
void func_8001DA28(void *);
void func_8001DDF4(void *);
void func_8001E49C(void *);
void func_8001E4A4(void *);
void func_8004229C(void *);
void sprite_node_set_offset(void *);
void sprite_node_set_anchor(void *);

/* Twelve-byte source region copied into common sprite setup. The glyph
 * setter writes the low byte of each halfword coordinate into the GPU command. */
typedef struct glyph_region {
    u16 u;
    u16 v;
    u32 width;
    u32 height;
} glyph_region_t;

void func_80041C4C(glyph_region_t *, s32);

void glyph_construct(class_glyph_t *This, s32 Unk1, u8 Unk2);
void glyph_set_mode(class_glyph_t *This, u8 Unk);
void glyph_set_char(class_glyph_t *This, u8 Unk);
u8 glyph_get_char(class_glyph_t *);

class_glyph_vtable_t g_GLYPH_VTABLE = {
    0x1144,
    base_class_destructor,
    glyph_construct,
    func_8001CBA4,
    func_8001CC48,
    func_8001CCB4,
    func_8001CD20,
    base_class_iter_children,
    base_class_add_parent,
    base_class_remove_parent,
    base_class_clear_parents,
    base_class_iter_parents,
    base_class_notify,
    base_class_nop,
    func_8001CD60,
    NULL,
    glyph_set_mode,
    func_80042170,
    func_8001D008,
    sprite_node_run,
    func_8001D1A4,
    func_8001D204,
    func_8001D280,
    func_8001D33C,
    func_8004220C,
    func_8004223C,
    func_80042268,
    func_8001D3CC,
    func_8001D3F8,
    func_8001D424,
    func_8001D450,
    func_8001D480,
    func_8001D4AC,
    func_8001D4DC,
    func_8001D568,
    func_8001D600,
    func_8001D624,
    func_8001D6A4,
    func_80042294,
    func_8001D6B4,
    func_8001D714,
    func_8001D950,
    func_8001DA28,
    func_8001DDF4,
    func_8001E49C,
    func_8001E4A4,
    func_8004229C,
    sprite_node_set_offset,
    sprite_node_set_anchor,
    glyph_set_char,
    (void (*)(void *)) glyph_get_char,
};

class_glyph_t *glyph_create(s32 Unk1, u8 Unk2) {
    class_glyph_t *allocated = ALLOCATE_STRUCT(class_glyph_t);

    if (allocated) {
        glyph_get_vtable()->Construct(allocated, Unk1, Unk2);
        return allocated;
    }

    return NULL;
}

void glyph_construct(class_glyph_t *This, s32 Unk1, u8 Unk2) {
    glyph_region_t region;

    func_80041C4C(&region, 0x20);
    sprite_node_get_vtable()->Construct(This, Unk1, (s32) &region, 0);
    This->vtable = glyph_get_vtable();
    This->vtable->Unk15(This, Unk2);
}

void glyph_set_mode(class_glyph_t *This, u8 Unk) {
    This->vtable->Unk48(This, Unk);
}

void glyph_set_char(class_glyph_t *This, u8 Unk) {
    glyph_region_t region;

    This->m_Char = Unk;
    func_80041C4C(&region, Unk);
    This->m_Unk27[2] = (s8) region.u;
    This->m_Unk27[3] = (s8) region.v;
}

u8 glyph_get_char(class_glyph_t *This) {
    s8 pad[0x10];

    return This->m_Char;
}

class_glyph_vtable_t *glyph_get_vtable(void) {
    return &g_GLYPH_VTABLE;
}

extern s32 D_8006ED40[3];

void func_80041C4C(glyph_region_t *region, s32 code) {
    __builtin_memcpy(region, D_8006ED40, sizeof(*region));
    code &= 0xFF;
    region->u += (code & 0x1F) * 8;
    region->v += ((u32) code >> 5) * 8;
}
