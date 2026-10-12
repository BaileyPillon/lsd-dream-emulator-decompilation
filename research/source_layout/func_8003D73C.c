/* Unaccepted, padding-free source-layout candidate. Insert at this function's
 * INCLUDE_ASM in src/menu/ui_screen.c. Complete executable equality is required. */
void func_8003D73C(ui_screen_t *This, s32 Unk2, s32 Unk3) {
    s32 idx;
    s32 count;
    s32 v9;
    s32 i;
    text_line_t **row;
    text_line_t *obj;
    s32 *entry;
    s32 pos[2];
    s32 tmp[2];
    effect_base_t *sound;

    idx = This->m_Unk21;
    row = (text_line_t **) This->m_Unk24[idx];
    v9 = ((s32 *) ((func_8003CE98_arg_t *) This->m_Unk18)->table[idx])[1];
    count = This->m_Unk22[idx];

    i = 0;
    if (count > 0) {
        do {
            obj = *row++;
            obj->vtable->Unk19(obj);
            i++;
        } while (i < count);
    }

    entry = (s32 *) ((func_8003CE98_arg_t *) This->m_Unk18)->table[idx];
    __builtin_memcpy(pos, entry + 4, sizeof(pos));
    pos[1] -= v9 * 10;

    if (Unk3) {
        sound = (effect_base_t *) This->m_Unk25;
        sound->vtable->attach_to(sound, This->m_Unk4, pos);
        i = 0;
        tmp[0] = 0x28;
        tmp[1] = count * 12;
        sound = (effect_base_t *) This->m_Unk25;
        sound->vtable->Unk47(sound, tmp);
    } else {
        sound = (effect_base_t *) This->m_Unk25;
        sound->vtable->Unk19(sound);
        i = 0;
    }

    row = (text_line_t **) This->m_Unk24[idx];
    if (count > 0) {
        do {
            (*row)->vtable->Unk18(*row, Unk2, pos);
            i++;
            (*row)->vtable->Unk23(*row, Unk3);
            pos[1] += 10;
            row++;
        } while (i < count);
    }

    row = (text_line_t **) This->m_Unk24[idx];
    obj = row[v9];
    obj->vtable->Unk23(obj, 1);
}
