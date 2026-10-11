#include "menu/main_menu.h"
#include "menu/ui_screen.h"
extern s32 D_8008A9B4;

/* This original text unit uses absolute data addressing (-G0). */
void func_8004DC64(main_menu_t *This, s32 arg) {
    func_8003DFBC()->Unk55(This, arg);
    This->m_Unk43->vtable->Unk18(This->m_Unk43, arg, &D_8008A9B4);
}
