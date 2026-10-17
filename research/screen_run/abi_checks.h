/* Matching-compiler layout assertions; no game code or data is emitted. */
#include "menu/ui_screen.h"
#include "menu/main_menu.h"
#include "menu/graph_screen.h"
#include "game/game_flow.h"

#define SCREEN_RUN_ABI(name, condition) typedef char screen_run_abi_##name[(condition) ? 1 : -1]
SCREEN_RUN_ABI(pointer_width, sizeof(void *) == 4);
SCREEN_RUN_ABI(ui_slot, (u32) &((ui_screen_vtable_t *) 0)->Run == 0x44);
SCREEN_RUN_ABI(main_slot, (u32) &((main_menu_vtable_t *) 0)->Run == 0x44);
SCREEN_RUN_ABI(chart_slot, (u32) &((graph_screen_vtable_t *) 0)->Run == 0x44);
SCREEN_RUN_ABI(common_slot, (u32) &((game_flow_screen_vtable_t *) 0)->Run == 0x44);
SCREEN_RUN_ABI(ui_result, (u32) &((ui_screen_t *) 0)->m_Unk13 == 0x38);
SCREEN_RUN_ABI(chart_result, (u32) &((graph_screen_t *) 0)->m_Result == 0x38);
SCREEN_RUN_ABI(chart_video_flag, (u32) &((graph_screen_t *) 0)->m_VideoReelReady == 0x238);
#undef SCREEN_RUN_ABI
