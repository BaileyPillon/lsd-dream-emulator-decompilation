/* Unaccepted, padding-free source-layout candidate. Insert at this function's
 * INCLUDE_ASM in src/dream/dream_generation_post.c. Complete executable equality is required. */
void *dream_generation_find_entry(s32 *arg0, s32 *arg1, s32 *arg2) {
    generation_entry_out_t out;
    s32 remaining;
    s32 i;
    s32 dx;
    s32 dz;
    s32 distance;
    u8 *entry;
    s8 *flag;
    u8 *effect;
    s32 effect_base;

    if (arg2 != NULL) {
        i = 0;
        remaining = g_GenerationStageEntryCounts[g_GenerationLocation] - g_GenerationEntryIndex;
        entry = (u8 *)g_GenerationStageEntries[g_GenerationLocation] + g_GenerationEntryIndex * 8;
        if (remaining > 0) {
            effect_base = (s32)g_GenerationEntityEffects + 0x3C;
            flag = (s8 *)(entry + 6);
            do {
                g_GenerationEntryIndex++;
                if (*flag > 0) {
                    __builtin_memcpy(&out.position, entry, 4);
                    effect = (u8 *)(*(u8 *)(flag - 2) * 6 + effect_base);
                    dream_generation_copy_style((generation_style_t *)((u8 *)&out + 4), (generation_style_t *)effect);
                    (*(void (**)(s32, s32 *, generation_entry_out_t *))(*(u32 *)g_GenerationOwner + 0xE8))(g_GenerationOwner, arg0, &out);
                    dx = arg0[0] - arg2[0];
                    if (dx < 0) {
                        dx = ~dx + 1;
                    }
                    dz = arg0[2] - arg2[2];
                    if (dz < 0) {
                        distance = dx - dz;
                    } else {
                        distance = dx + dz;
                    }
                    *arg1 = distance;
                    i++;
                    if (distance < *(s32 *)((s32)g_GenerationEntityRange + ((s32)*flag << 2))) {
                        return entry;
                    }
                } else {
                    i++;
                }
                flag += 8;
                entry += 8;
            } while (i < remaining);
        }
    }
    return NULL;
}
