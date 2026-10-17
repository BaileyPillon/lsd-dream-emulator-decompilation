#include "menu/ui_screen.h"
#include "menu/main_menu.h"
#include "menu/graph_screen.h"

s32 screen_run_ui(ui_screen_t *screen, void *graphics, s32 mode) {
    return screen->vtable->Run(screen, graphics, mode);
}
s32 screen_run_main(main_menu_t *screen, void *graphics, s32 mode) {
    return screen->vtable->Run(screen, graphics, mode);
}
s32 screen_run_chart(graph_screen_t *screen, void *graphics, s32 mode) {
    return screen->vtable->Run(screen, graphics, mode);
}
