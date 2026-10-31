#include "game/game_flow.h"
#include "menu/main_menu.h"
#include "menu/graph_screen.h"

/* Analysis-only callers; no additional method is installed in the game. */
void screen_prefix_attach(game_flow_screen_t *s, base_class_t *other) {
    s->vtable->Attach((base_class_t *)s, other);
}
void screen_prefix_detach(game_flow_screen_t *s, base_class_t *other) {
    s->vtable->Detach((base_class_t *)s, other);
}
void screen_prefix_detach_all(game_flow_screen_t *s) {
    s->vtable->DetachAll((base_class_t *)s);
}
void screen_prefix_iter_children(game_flow_screen_t *s, void **value, void **cursor) {
    s->vtable->IterChildren((base_class_t *)s, value, cursor);
}
void screen_prefix_add_parent(game_flow_screen_t *s, base_class_t *other) {
    s->vtable->AddParent((base_class_t *)s, other);
}
void screen_prefix_remove_parent(game_flow_screen_t *s, base_class_t *other) {
    s->vtable->RemoveParent((base_class_t *)s, other);
}
void screen_prefix_clear_parents(game_flow_screen_t *s) {
    s->vtable->ClearParents((base_class_t *)s);
}
void screen_prefix_iter_parents(game_flow_screen_t *s, void **value, void **cursor) {
    s->vtable->IterParents((base_class_t *)s, value, cursor);
}
void screen_prefix_notify(game_flow_screen_t *s, s32 code) {
    s->vtable->Notify((base_class_t *)s, code);
}
void screen_prefix_nop(game_flow_screen_t *s) {
    s->vtable->Nop((base_class_t *)s);
}

/* Assignments check real inherited callback types without pointer casts. */
void screen_prefix_typecheck(game_flow_screen_vtable_t *v) {
    v->Attach = base_class_attach;
    v->Detach = base_class_detach;
    v->DetachAll = base_class_detach_all;
    v->IterChildren = base_class_iter_children;
    v->AddParent = base_class_add_parent;
    v->RemoveParent = base_class_remove_parent;
    v->ClearParents = base_class_clear_parents;
    v->IterParents = base_class_iter_parents;
    v->Notify = base_class_notify;
    v->Nop = base_class_nop;
}

typedef char screen_prefix_pointer_width[(sizeof(void *) == 4) ? 1 : -1];
typedef char screen_prefix_extent[(sizeof(game_flow_screen_vtable_t) == 0x48) ? 1 : -1];
#define PREFIX_SLOT(field, offset) \
    typedef char prefix_slot_##field[((u32)&((game_flow_screen_vtable_t *)0)->field == offset) ? 1 : -1]
PREFIX_SLOT(type_id, 0x00);
PREFIX_SLOT(Destroy, 0x04);
PREFIX_SLOT(ConstructAddress, 0x08);
PREFIX_SLOT(CleanupAddress, 0x0C);
PREFIX_SLOT(Attach, 0x10);
PREFIX_SLOT(Detach, 0x14);
PREFIX_SLOT(DetachAll, 0x18);
PREFIX_SLOT(IterChildren, 0x1C);
PREFIX_SLOT(AddParent, 0x20);
PREFIX_SLOT(RemoveParent, 0x24);
PREFIX_SLOT(ClearParents, 0x28);
PREFIX_SLOT(IterParents, 0x2C);
PREFIX_SLOT(Notify, 0x30);
PREFIX_SLOT(Nop, 0x34);
PREFIX_SLOT(OnNotifyAddress, 0x38);
PREFIX_SLOT(Reserved_3C, 0x3C);
PREFIX_SLOT(InitializeAddress, 0x40);
PREFIX_SLOT(Run, 0x44);
#undef PREFIX_SLOT

#define PREFIX_CONCRETE(field) \
    typedef char prefix_main_##field[((u32)&((main_menu_vtable_t *)0)->field == \
                                     (u32)&((game_flow_screen_vtable_t *)0)->field) ? 1 : -1]; \
    typedef char prefix_chart_##field[((u32)&((graph_screen_vtable_t *)0)->field == \
                                      (u32)&((game_flow_screen_vtable_t *)0)->field) ? 1 : -1]
PREFIX_CONCRETE(Destroy);
PREFIX_CONCRETE(Attach);
PREFIX_CONCRETE(Detach);
PREFIX_CONCRETE(DetachAll);
PREFIX_CONCRETE(IterChildren);
PREFIX_CONCRETE(AddParent);
PREFIX_CONCRETE(RemoveParent);
PREFIX_CONCRETE(ClearParents);
PREFIX_CONCRETE(IterParents);
PREFIX_CONCRETE(Notify);
PREFIX_CONCRETE(Nop);
PREFIX_CONCRETE(Run);
#undef PREFIX_CONCRETE
