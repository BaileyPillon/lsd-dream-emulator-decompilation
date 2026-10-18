#include "graphics/display.h"

extern s32 cd_file_driver_tick(void);

void install_cd_word_callback(display_t *display) {
    display->vtable->display_set_vsync_callback(display, cd_file_driver_tick);
}

s32 invoke_display_word_callback(display_t *display) {
    return display->m_VsyncCallback();
}

void clear_display_word_callback(display_t *display) {
    display->vtable->display_set_vsync_callback(display, NULL);
}
