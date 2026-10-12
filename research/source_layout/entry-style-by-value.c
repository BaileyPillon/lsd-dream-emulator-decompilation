/* Unaccepted ten-byte spawn-record hypothesis. Replace the generation-find
 * INCLUDE_ASM in a private complete source unit; exact image equality is required. */
typedef struct { u8 position[4]; generation_style_t style; } generation_find_input_t;
static inline void generation_find_store_style_value(generation_style_t *dst, generation_style_t src) { *dst = src; }
void *dream_generation_find_entry(s32 *arg0, s32 *arg1, s32 *arg2) {
    generation_find_input_t out;
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
                    generation_find_store_style_value((generation_style_t *)((u8 *)&out + 4), *((generation_style_t *)effect));
                    (*(void (**)(s32, s32 *, generation_find_input_t *))(*(u32 *)g_GenerationOwner + 0xE8))(g_GenerationOwner, arg0, &out);
                    dx = (s32)((u32)arg0[0] - (u32)arg2[0]);
                    if (dx < 0) {
                        dx = (s32)(~(u32)dx + 1U);
                    }
                    dz = (s32)((u32)arg0[2] - (u32)arg2[2]);
                    if (dz < 0) {
                        distance = (s32)((u32)dx - (u32)dz);
                    } else {
                        distance = (s32)((u32)dx + (u32)dz);
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
