/* Unaccepted, padding-free source-layout candidate. Insert at this function's
 * INCLUDE_ASM in src/menu/ui_screen.c. Complete executable equality is required. */
void func_8003DAD4(ui_screen_t *This) {
    s32 idx;
    s32 sel;
    s32 count;
    s32 i;
    text_line_t **row;
    s32 pos[2];
    s32 *entry;
    effect_base_t *sound;

    if (This->m_HasIdleTimeout != 2) {
        return;
    }

    idx = This->m_Unk21;
    sel = This->m_Unk23[idx];
    entry = (s32 *) ((func_8003CE98_arg_t *) This->m_Unk18)->table[idx];
    __builtin_memcpy(pos, entry + 4, sizeof(pos));
    pos[1] -= sel * 10;

    row = (text_line_t **) This->m_Unk24[idx];
    count = This->m_Unk22[idx];
    if (count > 0) {
        i = 0;
        do {
            (*row)->vtable->Unk23(*row, 0);
            i++;
            ((void (*)(void *, void *)) (*row)->vtable->Unk46)(*row, pos);
            pos[1] += 10;
            row++;
        } while (i < count);
    }

    {
        text_line_t *obj = ((text_line_t **) This->m_Unk24[idx])[sel];
        obj->vtable->Unk23(obj, 1);
        obj->vtable->Unk45(obj, (char *)This->m_Unk18 + 0x10);
    }
    ((s32 *) ((func_8003CE98_arg_t *) This->m_Unk18)->table[idx])[1] = sel;
    sound = (effect_base_t *)This->m_Unk25;
    sound->vtable->Unk19(sound);
    This->m_HasIdleTimeout = 1;
    This->vtable->Unk23(This, 0x10);
}
