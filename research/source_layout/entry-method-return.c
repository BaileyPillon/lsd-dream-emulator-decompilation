/* Unaccepted source hypothesis for dream_generation_find_entry.
 * The consumed method return reproduces the original 80-byte frame without
 * enlarging the ten-byte packet. The complete image still differs in six
 * bytes: a retained method store and argument scheduling need explanation.
 * Insert at the scanner's INCLUDE_ASM in dream_generation_post.c; the
 * complete executable must match before this can enter the game build. */
typedef struct {
    u8 position[4];
    generation_style_t style;
} generation_find_input_t;

typedef void (*generation_entry_method_fn_t)(s32, s32 *, generation_find_input_t *);

typedef struct {
    generation_entry_method_fn_t method;
} generation_entry_method_t;

static inline generation_entry_method_t get_entry_method(s32 owner) {
    generation_entry_method_t value;

    value.method = *(generation_entry_method_fn_t *)(*(u32 *)owner + 0xE8);
    return value;
}

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
                    dream_generation_copy_style((generation_style_t *)((u8 *)&out + 4), (generation_style_t *)effect);
                    {
                        generation_entry_method_t selected = get_entry_method(g_GenerationOwner);
                        selected.method(g_GenerationOwner, arg0, &out);
                    }
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
