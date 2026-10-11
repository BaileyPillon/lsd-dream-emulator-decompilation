#include "menu/main_menu.h"
#include "base/base.h"
#include "menu/ui_screen.h"

void func_8004D578(main_menu_t *This, dream_sys_t *DreamSys);
void func_8004D704(main_menu_t *This);
void func_8004D788(main_menu_t *This, void **Unk2, s32 Unk3);
void show_title(main_menu_t *This);
void func_8003C1DC(void);
void func_8003E280(void);
void func_8003C238(void);
void func_8004D898(main_menu_t *This);
void func_8003E418(void);
void func_8003C48C(void);
void func_8003C51C(void);
void func_8004D90C(main_menu_t *This, s32 Unk);
void timer_begin_frame(void);
void timer_end_frame(void);
void func_8003C794(void);
void func_8003C7B4(void);
void func_8003C7F4(void);
void func_8003C858(void);
void func_8003C8D0(void);
void func_8003C944(void);
void func_8003C9B0(void);
void func_8004D9D4(main_menu_t *This);
void func_8004DABC(main_menu_t *This);
void func_8003CAEC(void);
void func_8003CAF8(void);
void func_8003CB30(void);
void func_8003CB68(void);
void func_8003CBB8(void);
void func_8003CBC0(void);
void func_8003CC2C(void);
void func_8003CCDC(void);
void func_8003CD48(void);
void func_8003CDE0(void);
void func_8004DB18(main_menu_t *This, void *Unk);
void func_8004DC08(main_menu_t *This);
void func_8004DC64(void);
void func_8004DCD0(main_menu_t *This, char *Unk_arg_s0);
void func_8003D3B0(void);
void func_8003D444(void);
void func_8003D4DC(void);
void func_8003D5C0(void);
void func_8003D5CC(void);
void func_8003D6D4(void);
void func_8003D73C(void);
void func_8003D980(void);
void func_8003DA10(void);
void func_8003DAD4(void);
void func_8003DCAC(void);
void func_8003DDC8(void);
void func_8003DE30(void);
void func_8003DE9C(void);
void func_8003DFA0(void);
void func_8004DE08(main_menu_t *This);
void attach_memory_card(main_menu_t *This, s32 Unk);
void func_8004E054(main_menu_t *This);
void write_save(main_menu_t *This);
void read_save(main_menu_t *This);
void func_8004E230(main_menu_t *This, void *Unk2, s32 Unk3);

extern main_menu_vtable_t g_MAIN_MENU_VTABLE;
extern char *D_80011454;
extern char *D_80086D6C[16];
extern char *D_8008AA10;
extern char *g_DAY_STR;
extern u8 D_8008AA28;
extern s32 D_8008AA2C;
extern const char g_MENU_FILE_ICON_PATH[];

void func_8004DCD0(main_menu_t *This, char *Unk_arg_s0) {
    u8 local_buf[3];
    u8 *s1_buf_ptr = local_buf;

    u32 v1_idx_for_D8AA28;
    s32 v0_val_to_modify;
    u8 *v1_target_addr_in_buf;

    func_8003DFBC()->Unk56(This, Unk_arg_s0);

    if (This->m_Unk14 != 0) {
        v1_idx_for_D8AA28 = D_8008AA28;
        v0_val_to_modify = 0x80;
        local_buf[0] = 0;
        local_buf[1] = 0;
        local_buf[2] = 0;

        v1_target_addr_in_buf = v1_idx_for_D8AA28 + s1_buf_ptr;
    } else {
        __builtin_memcpy(local_buf, Unk_arg_s0, 3);

        if (D_8008AA2C < 0x80) {
            v0_val_to_modify = local_buf[0];
            v0_val_to_modify = v0_val_to_modify + 0x80;
            local_buf[0] = v0_val_to_modify;
            goto UPDATES_ONLY;
        }

        v1_idx_for_D8AA28 = D_8008AA28;
        v1_target_addr_in_buf = s1_buf_ptr + v1_idx_for_D8AA28;

        v0_val_to_modify = *v1_target_addr_in_buf;
        v0_val_to_modify = v0_val_to_modify + 0x80;
    }
STORE_AND_PROCEED:
    *v1_target_addr_in_buf = v0_val_to_modify;

UPDATES_ONLY:
    if ((++D_8008AA28 & 0xFFU) >= 3) {
        D_8008AA28 = 0;
    }

    if (++D_8008AA2C >= 0x101) {
        D_8008AA2C = 0;
    }

    This->m_Unk43->vtable->Unk45(This->m_Unk43, local_buf);
}

void func_8004DE08(main_menu_t *This) {
    s32 saved_unk21;
    void *mem;
    s32 shake[2];
    u8 size;

    size = This->m_Unk43->m_GlyphCount;
    saved_unk21 = This->m_Unk21;
    mem = memory_allocate_mem(size);
    func_80040FC0(mem, g_DAY_STR);
    This->m_Unk43->vtable->Unk50(This->m_Unk43, mem);
    memory_free_mem(mem);
    func_8004D678(This, This->m_Unk18, This->m_DreamSys);
    This->vtable->Unk55(This, (void *) This->m_Unk4);
    This->m_DreamSys->vtable->dream_sys_get_set_screen_shake(This->m_DreamSys, shake);
    This->m_Unk21 = 5;
    This->vtable->Unk23(This, 11);
    This->vtable->Unk70(This, shake[0], 1);
    This->vtable->Unk23(This, 15);
    This->vtable->Unk59(This, saved_unk21, 0);
    This->m_DreamSys->vtable->dream_sys_get_set_screen_shake(This->m_DreamSys, shake);
}

void attach_memory_card(main_menu_t *This, s32 Unk) {
    if (!This->m_MemoryCard) {
        /* Preserve the original caller's unused second argument. */
        This->m_TextureHelper =
            ((tim_image_t *(*)(const char *, s32)) tim_image_create)(g_MENU_FILE_ICON_PATH, Unk);
        This->m_MemoryCard = memory_card_create(1, 0);
    }

    This->m_MemoryCard->vtable->Unk26(This->m_MemoryCard, D_80011454, &D_80086D6C, *(u32 *) (This->m_Unk2 + 4),
                                      This->m_Unk3, This->m_Unk4, This->m_Sound);

    This->vtable->Attach(This, (s32) This->m_MemoryCard);
    This->vtable->Detach(This, *(void **) (This->m_Unk2 + 4));
    This->vtable->Detach(This, (void *) This->m_Unk3);
}

void func_8004E054(main_menu_t *This) {
    This->vtable->Attach(This, *(u32 *) (This->m_Unk2 + 4));
    This->vtable->Attach(This, This->m_Unk3);
    This->vtable->Detach(This, This->m_MemoryCard);
    This->m_MemoryCard->vtable->Unk27(This->m_MemoryCard);
}

void write_save(main_menu_t *This) {
    dream_sys_t *dream_sys_obj;
    u32 title_ptr; // points to ETC\TITLE.TIM
    void (*func_ptr)(dream_sys_t *, s32 *);

    s32 unk_struct[2];

    dream_sys_obj = This->m_DreamSys;
    title_ptr = *(u32 *) ((char *) This->m_Unk23 + 0x14);
    func_ptr = dream_sys_obj->vtable->dream_sys_get_set_screen_shake;
    unk_struct[0] = title_ptr;
    func_ptr(dream_sys_obj, &unk_struct[0]);
    This->vtable->attach_memory_card(This);

    if (This->m_DreamSys->vtable->dream_sys_is_new_game(This->m_DreamSys)) {
        *(u8 *) D_8008AA10 = 0;
    }

    This->m_MemoryCard->vtable->Unk29(This->m_MemoryCard, D_8008AA10, g_DAY_STR, 13, 3, This->m_TextureHelper,
                                      This->m_RegionCode, This->m_RegionCodeParam);
}

void read_save(main_menu_t *This) {
    This->vtable->attach_memory_card(This);

    This->m_MemoryCard->vtable->Unk28(This->m_MemoryCard, D_8008AA10, g_DAY_STR, This->m_RegionCode,
                                      This->m_RegionCodeParam);
}

void func_8004E230(main_menu_t *This, void *Unk2, s32 Unk3) {
    if (Unk3 > 0x17) {
        return;
    }

    if (Unk3 < 0x16) {
        return;
    }

    This->vtable->Unk74(This, Unk2);

    if (Unk3 == 0x16) {
        This->m_DreamSys->vtable->dream_sys_clear_new_game(This->m_DreamSys);
        This->vtable->Unk72(This, 22);
    }
}

main_menu_vtable_t *main_menu_get_vtable(void) {
    return &g_MAIN_MENU_VTABLE;
}
