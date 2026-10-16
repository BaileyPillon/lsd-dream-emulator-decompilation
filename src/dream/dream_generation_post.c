#include "common.h"

extern s32 g_CurrentDay;
extern s32 g_GenerationSampleOffsets[];


extern s32 g_GenerationSpawnParams[];
extern s32 g_GenerationSpawnSample[];
extern s32 g_GenerationSpawnRoll[];
extern s32 g_GenerationSpawnSprite[];
extern u8 g_GenerationSpriteData[];
extern s32 g_GenerationSpawnIndex[];

void dream_generation_seed_palette_daily(void) {
    s32 d;

    rand();
    g_GenerationSpawnSample[0] = g_GenerationSampleOffsets[1];
    g_GenerationSpawnParams[0] = (rand() % 20) << 11;
    g_GenerationSpawnParams[2] = 0xA000;
    d = g_CurrentDay % 3;
    if (d == 1) {
        g_GenerationSpawnRoll[0] = 0xFFFF6000;
    } else if (d == 2) {
        g_GenerationSpawnRoll[0] = 0x800;
    }
    g_GenerationSpawnSprite[0] = ((u32) rand() % 7) * 12 + (s32) g_GenerationSpriteData;
    g_GenerationSpawnIndex[0] = rand() % 5;
}

extern s32 *g_GenerationEntityContext;
extern s32 g_GenerationEntityEffects[];

void *dream_generation_find_entry(s32 *, s32 *, s32 *);
void sound_entity_init(s32, s32 *, s32, s32, s32);

s32 *dream_generation_spawn_entity(s32 *arg0, s32 *arg1, s32 arg2, s32 arg3) {
    s32 *temp_v0;
    u8 *temp_v1;
    s8 temp_a2;
    s8 temp_v2;

    temp_v0 = dream_generation_find_entry(arg0 + 1, arg0 + 4, (s32 *)arg2);
    if (temp_v0 != NULL) {
        arg0[0] = (s32) temp_v0;
        temp_a2 = *(s8 *) ((u8 *) temp_v0 + 6);
        sound_entity_init(*g_GenerationEntityContext, arg0 + 5, temp_a2, (s32) arg0,
                          g_GenerationEntityEffects[temp_a2]);
        temp_v2 = *(s8 *) ((u8 *) temp_v0 + 6);
        if (temp_v2 == *arg1) {
            *arg1 = -temp_v2;
        }
        temp_v1 = (u8 *) temp_v0;
        temp_v1[6] = -temp_v1[6];
        return arg0;
    }
    return NULL;
}

typedef struct {
    s16 words[3];
} generation_style_t;

static inline void dream_generation_copy_style(generation_style_t *dst, generation_style_t *src) {
    *dst = *src;
}

extern s32 *g_GenerationStageEntries[];
extern u8 g_GenerationStageEntryCounts[];
extern s32 g_GenerationEntryIndex;
extern s32 g_GenerationLocation;
extern s32 g_GenerationOwner;
extern s32 g_GenerationEntityRange[];
typedef struct {
    s32 position;
    s32 style;
    s16 z;
} generation_entry_out_t;

typedef struct {
    u8 position[4];
    generation_style_t style;
} generation_find_input_t;
typedef void (*generation_entry_method_fn_t)(s32, s32 *, generation_find_input_t *);
/* A complete four-byte vtable snapshot. The initialized view preserves the
 * original compiler layout; returning a scalar avoids a method store. */
typedef struct {
    u32 table[1];
} generation_entry_table_ref_t;
typedef char checked_generation_entry_table_word[
    (sizeof(generation_entry_table_ref_t) == 4) ? 1 : -1];

static inline generation_entry_method_fn_t read_entry_method(s32 owner) {
    generation_entry_table_ref_t reference = {{ *(u32 *)owner }};
    return *(generation_entry_method_fn_t *)(reference.table[0] + 0xE8);
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
                    (read_entry_method(g_GenerationOwner))(g_GenerationOwner, arg0, &out);
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


extern s32 *g_GenerationEntityContext;

void sound_entity_stop(s32, s32 *);

s32 dream_generation_stop_entity(s32 *arg0) {
    u8 *temp_v1;

    sound_entity_stop(*g_GenerationEntityContext, (s32 *) arg0 + 5);
    temp_v1 = (u8 *) *arg0;
    temp_v1[6] = -temp_v1[6];
    return 0;
}

void sound_entity_update(s32, s32 *);
s32 dream_generation_entity_in_range(s32 *, s32 *);

s32 dream_generation_update_entity(s32 arg0, s32 *arg1, s32 arg2) {
    if (dream_generation_entity_in_range((s32 *)arg0, arg1) != 0) {
        sound_entity_update(*g_GenerationEntityContext, (s32 *) (arg0 + 0x14));
        return 1;
    }

    return 0;
}

extern s32 g_GenerationEntityRange[];

s32 dream_generation_entity_in_range(s32 *arg0, s32 *arg1) {
    s32 diff;
    s32 temp;
    s32 dist;
    s32 result = 0;
    if (arg1 != NULL) {
        diff = arg0[1] - arg1[0];
        if (diff < 0) {
            diff = ~diff + 1;
        }
        temp = arg0[3] - arg1[2];
        if (temp < 0) {
            dist = diff - temp;
        } else {
            dist = diff + temp;
        }
        arg0[4] = dist;
        if (dist < g_GenerationEntityRange[-((s8 *) *arg0)[6]]) {
            result = 1;
            return result;
        }
    }
    return result;
}

extern s32 g_GenerationOwner;
extern s32 g_LocationTimer;
extern s32 *g_GenerationEntities[];
void dream_generation_create_effect(void);
void dream_generation_update_structure_entities(s32 *);
extern s32 g_GenerationEntryIndex;
extern u8 g_GenerationEntitySlotData[];
void dream_generation_create_effects(void);
void dream_generation_update_effects(void);
void dream_generation_build_entities(void *);
void dream_generation_update_border(void);
s32 dream_generation_update(s32 arg0, s32 arg1, s32 arg2) {
    s32 coords[4];
    s32 *position = NULL;
    s32 **cursor;
    s32 entity;
    s32 timer;
    s32 slot_offset;
    s32 i;

    if (arg0 != 0) {
        position = coords;
        (*(void (**)(s32, s32 *, s32))(*(u32 *)g_GenerationOwner + 0xE8))(
            g_GenerationOwner, position, arg0);
    }
    timer = g_LocationTimer;
    g_LocationTimer = timer + 1;
    if (timer == 0) {
        dream_generation_create_effect();
        dream_generation_create_effects();
        dream_generation_build_entities(position);
    }
    dream_generation_update_effects();
    dream_generation_update_structure_entities(position);
    dream_generation_update_border();
    g_GenerationEntryIndex = 0;
    cursor = g_GenerationEntities;
    i = 0;
    slot_offset = 0;
    do {
        entity = (s32)*cursor;
        if (entity != 0) {
            if (dream_generation_update_entity(entity, position, arg1) == 0) {
                *cursor = (s32 *)dream_generation_stop_entity(*cursor);
            }
        } else {
            *cursor = (s32 *)dream_generation_spawn_entity(
                (s32 *)(slot_offset + (s32)g_GenerationEntitySlotData), &arg2, (s32)position, arg1);
        }
        slot_offset += 0x68;
        i += 1;
        cursor += 1;
    } while (i < 2);
    return arg2;
}


extern s32 g_GenerationBorderRect0[];
extern s32 g_GenerationBorderRect1[];
extern s32 g_GenerationBorderRect2[];
extern s32 g_GenerationBorderRect3[];
extern s32 g_GenerationLocation;

void display_draw_border(void *, s32, void *);

void dream_generation_update_border(void) {
    if (g_GenerationLocation == 2) {
        display_draw_border(&g_GenerationBorderRect0, 1, &g_GenerationBorderRect1);
    } else if ((u32) (g_GenerationLocation - 3) < 3) {
        display_draw_border(&g_GenerationBorderRect2, 1, &g_GenerationBorderRect3);
    }
}

/*
 * The 14 callbacks below are g_GenerationEntityEffects[1..14] (0x800874B0),
 * installed as the sound_entity_init effect driver for a spawned generation
 * entry.  arg1 is the entity_context_t (see entity.h) reached as s32 slots:
 *   [0] state  [1] tick  [2] owner  [3] callback  [4] motion  [5] divisor
 *   slots[0] [6..10] and slots[1] [11..15] and slots[2] [16..20], each
 *   { handle, id, param, period, counter }.
 * Each handler records generation_entity_get_motion() in [4] and then writes
 * effect ids/params into the three slots according to the entity's tick.
 */
void generation_entity_effect_01(void *arg0, s32 *arg1) {
    s32 value;

    arg1[4] = generation_entity_get_motion();
    value = arg1[1];
    if (value == 0) {
        arg1[7] = 7;
        arg1[8] = 0;
        return;
    }
    if (value == 2) {
        arg1[12] = 7;
        arg1[13] = 0;
        return;
    }
    if (value == 5) {
        arg1[17] = 7;
        arg1[18] = 0;
        return;
    }
    if (value >= 8) {
        arg1[1] = -1;
    }
}

s32 generation_entity_get_motion();

void generation_entity_effect_02(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] == 0) {
        arg1[7] = 0x18;
        arg1[8] = -2;
        return;
    }
    if (arg1[1] >= 0x401) {
        arg1[1] = -1;
    }
}

void generation_entity_effect_03(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] == 0) {
        arg1[7] = 0xC;
        arg1[8] = 2;
        return;
    }
    if (arg1[1] >= 5) {
        arg1[1] = -1;
    }
}

void generation_entity_effect_04(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] % 20 == 0) {
        arg1[7] = 0x1E;
        arg1[9] = 0x20;
        arg1[8] = 0;
        arg1[10] = 0xA;
    }
    if (arg1[1] % 400 == 0) {
        arg1[12] = 0x1E;
        arg1[13] = 0;
    }
    arg1[17] = 6;
    arg1[19] = 0x20;
    arg1[18] = 0;
    arg1[20] = 0xA;
}

void generation_entity_effect_05(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] % 3 == 0) {
        arg1[7] = 0x1E;
        arg1[8] = 0;
    }
    if (arg1[1] % 5 == 0) {
        arg1[12] = 0x1E;
        arg1[13] = 0;
        arg1[14] = 0x18;
        arg1[15] = 0x18;
    }
    if (arg1[1] % 7 == 0) {
        arg1[7] = 0x1E;
        arg1[8] = 0;
    }
    arg1[17] = 6;
    arg1[18] = 1;
    arg1[19] = 0x2A;
    arg1[20] = 0xA;
}

void generation_entity_effect_06(void *arg0, s32 *arg1) {
    s32 temp;
    s32 v;

    arg1[4] = generation_entity_get_motion();
    temp = arg1[1];
    if (temp == 0) {
        arg1[7] = 0x1E;
        arg1[8] = -1;
        return;
    }
    if (temp < 0x32 && (temp / 5) * 5 == temp - 4) {
        arg1[12] = 0x1E;
        arg1[13] = 0;
        v = arg1[14] - arg1[1] * 2;
        arg1[14] = v;
        arg1[15] = v;
        return;
    }
    v = arg1[1];
    if ((u32) (v - 0x65) < 9U) {
        arg1[17] = 0xD;
        arg1[18] = 1;
        return;
    }
    if (v >= 0xC9) {
        arg1[1] = -1;
    }
}

void generation_entity_effect_07(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] == 0) {
        arg1[7] = 7;
        arg1[8] = 2;
        return;
    }
    if (arg1[1] >= 0x1B) {
        arg1[1] = -1;
    }
}

void generation_entity_effect_08(void *arg0, s32 *arg1) {
    s32 temp;

    arg1[4] = generation_entity_get_motion();
    temp = arg1[1];
    if (temp == 0) {
        arg1[7] = 0x14;
        arg1[8] = 1;
        return;
    }
    if (temp == 3) {
        arg1[8] = 2;
        arg1[9] = 0x18;
        arg1[7] = temp;
        arg1[10] = 0x14;
        return;
    }
    if (temp >= 0x33) {
        arg1[1] = -1;
    }
}

void generation_entity_effect_09(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] % 20 == 0) {
        arg1[7] = 9;
        arg1[8] = 0;
        arg1[9] = 0x40;
        arg1[10] = 0x40;
    }
}

void generation_entity_effect_10(void *arg0, s32 *arg1) {
    arg1[4] = generation_entity_get_motion();
    if (arg1[1] % 20 == 0) {
        arg1[7] = 9;
        arg1[8] = -2;
    }
}

void generation_entity_effect_11(void *arg0, s32 *arg1) {
    s32 temp;

    arg1[4] = generation_entity_get_motion();
    temp = arg1[1] % 20;
    if (temp == 1) {
        arg1[7] = 9;
        arg1[8] = -2;
        return;
    }
    if (temp == 0x10) {
        arg1[12] = 9;
        arg1[13] = -2;
    }
}

void generation_entity_effect_12(void *arg0, s32 *arg1) {
    s32 temp;

    generation_entity_effect_11(arg0, arg1);
    temp = arg1[1] % 70;
    if (temp == 0x32) {
        arg1[17] = 0x14;
        arg1[18] = 1;
    } else if ((u32) (temp - 0x36) < 5U) {
        arg1[17] = 0xD;
        arg1[18] = 1;
    } else if (temp == 0x3D) {
        arg1[17] = 9;
        arg1[18] = -1;
    }
}

void generation_entity_effect_13(void *arg0, s32 *arg1) {
    s32 temp;

    arg1[4] = generation_entity_get_motion();
    temp = arg1[1];
    if (temp == 0) {
        arg1[7] = 0x14;
        arg1[8] = -2;
        arg1[12] = 0x14;
        arg1[13] = -2;
        return;
    }
    if (temp == 4) {
        arg1[12] = 0x14;
        arg1[13] = -2;
        return;
    }
    if (temp == 0x14) {
        arg1[7] = 0x10;
        arg1[8] = -2;
        arg1[12] = 0x12;
        arg1[13] = -2;
        return;
    }
    if (temp >= 0xC9) {
        arg1[1] = -1;
    }
}

void generation_entity_effect_14(void *arg0, void *arg1) {
    s32 *p = (s32 *) arg1;

    p[4] = generation_entity_get_motion();
    if (p[1] == 0) {
        p[7] = 0x18;
        p[8] = 0;
    }
}

s32 generation_entity_get_motion(void *arg0) {
    s32 value;
    s32 divisor;

    value = g_GenerationEntityRange[-(*(s8 **) arg0)[6]];
    divisor = value / *(s32 *) ((u8 *) arg0 + 0x28);
    return *(s32 *) ((u8 *) arg0 + 0x10) / divisor;
}

extern s32 g_GenerationType;

s32 dream_generation_type_is_even(void) {
    return (g_GenerationType & 1) ^ 1;
}
