#include "game/game_flow.h"
#include "menu/main_menu.h"
#include "menu/graph_screen.h"

/* Analysis callers: excluded from the canonical game. A void-returning
 * common view must fail compilation when its result is consumed here. */
base_class_t *screen_destroy_common(game_flow_screen_t *screen) {
    return screen->vtable->Destroy((base_class_t *)screen);
}

base_class_t *screen_destroy_main(main_menu_t *screen) {
    return screen->vtable->Destroy((base_class_t *)screen);
}

base_class_t *screen_destroy_chart(graph_screen_t *screen) {
    return screen->vtable->Destroy((base_class_t *)screen);
}

typedef char check_destroy_pointer_width[(sizeof(void *) == 4) ? 1 : -1];
#define CHECK_DESTROY_SLOT(name, type) \
    typedef char name[((u32)&((type *)0)->Destroy == 4) ? 1 : -1]
CHECK_DESTROY_SLOT(check_common_destroy_slot, game_flow_screen_vtable_t);
CHECK_DESTROY_SLOT(check_main_destroy_slot, main_menu_vtable_t);
CHECK_DESTROY_SLOT(check_chart_destroy_slot, graph_screen_vtable_t);
#undef CHECK_DESTROY_SLOT
