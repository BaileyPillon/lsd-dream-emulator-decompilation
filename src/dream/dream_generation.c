#include "common.h"
#include "graphics/effect_base.h"

extern u8 g_GenerationColorPalette[];
extern s32 g_GenerationHeightTable[];

extern s32 g_GenerationOwner;
extern s32 g_GenerationLocation;
extern s32 *g_GenerationEntityContext;
extern s32 g_LocationTimer;
extern s32 g_CurrentDay;
extern s32 g_GenerationSubMode;
extern s32 g_GenerationType;
extern s32 g_GenerationEntitySlot1[];

u8 *dream_generation_load(void);

s32 dream_generation_start(void *a0, s32 a1, s32 *a2, s32 a3, s32 a4) {
    s32 *p;
    s32 i;

    if (g_GenerationOwner == 0) {
        i = 1;
        p = g_GenerationEntitySlot1;
        g_GenerationOwner = (s32) a0;
        g_GenerationLocation = a1;
        g_GenerationEntityContext = a2;
        g_GenerationType = -1;
        g_CurrentDay = a3;
        g_GenerationSubMode = a4;
        g_LocationTimer = 0;
        do {
            *p = 0;
            i--;
            p--;
        } while (i >= 0);
        return dream_generation_load();
    }
    return 0;
}

extern s8 *g_GenerationLocationEntries[];
extern u8 *g_GenerationInfo[];
extern s32 g_GenerationEffectColor;
void dream_generation_apply_entry(u8 *, s8 *);
s8 *dream_generation_pick_entry(void);

u8 *dream_generation_load(void) {
    s8 *s0 = g_GenerationLocationEntries[g_GenerationLocation];

    if (s0 == NULL) {
        s0 = dream_generation_pick_entry();
    }
    dream_generation_apply_entry((u8 *) g_GenerationInfo, s0);
    if (s0[1] >= 4) {
        g_GenerationEffectColor = (s32) (g_GenerationColorPalette + s0[2] * 3);
    }
    return (u8 *) g_GenerationInfo;
}

void dream_generation_apply_entry(u8 *arg0, s8 *arg1) {
    *(void **) (arg0 + 0xC) = (u8 *) &g_GenerationColorPalette + arg1[3] * 3;
    *(void **) (arg0 + 0x18) = (u8 *) &g_GenerationColorPalette + arg1[2] * 3;
    *(s32 *) (arg0 + 0x1C) = g_GenerationHeightTable[arg1[1]];
    *(s32 *) (arg0 + 0x14) = arg1[0];
}

extern s32 g_GenerationEffectColor;
extern s32 g_GenerationEffectOrigin[];
extern s32 g_GenerationEffectScreen[];
extern s32 *g_GenerationEntityContext;
extern effect_base_t *g_GenerationEffect;

void dream_generation_create_effect(void) {
    void **ctx;
    s32 result;

    if (g_GenerationEffectColor != 0) {
        g_GenerationEffect = effect_base_create((u32) g_GenerationEffectScreen, (u32) g_GenerationEffectColor, 0);
        g_GenerationEffect->vtable->set_enabled(g_GenerationEffect, 1);
        g_GenerationEffect->vtable->set_mode(g_GenerationEffect, 0);
        ctx = *(void ***) ((u8 *) g_GenerationEntityContext + 0xC);
        result = (*(s32(**)(void *))((u8 *) *ctx + 0xAC))(ctx);
        g_GenerationEffect->vtable->attach_to(g_GenerationEffect, result, g_GenerationEffectOrigin);
    }
}

extern s32 g_GenerationEffectColor;
extern effect_base_t *g_GenerationEffect;

void dream_generation_destroy_effect(void) {
    if (g_GenerationEffectColor != 0) {
        g_GenerationEffect->vtable->Destroy(g_GenerationEffect);
        g_GenerationEffectColor = 0;
    }
}

extern s8 g_GenerationEntryCounts[];
extern u8 *g_GenerationEntryTables[];
extern u8 g_GenerationEffectDataAlt[];
extern u8 g_GenerationEffectData[];
extern s32 g_GenerationFlags;
extern s32 g_GenerationIndex;
extern s32 g_GenerationTablePtr;
extern s32 g_GenerationDataPtr;

s8 *dream_generation_pick_entry(void) {
    s32 temp_v1;
    s8 temp_a0;
    s32 idx;
    s8 *entry;
    u8 *p;

    temp_v1 = g_CurrentDay + g_GenerationLocation;
    temp_a0 = g_GenerationEntryCounts[4 + (temp_v1 & 0xF)];
    g_GenerationType = temp_a0;
    idx = temp_v1 % g_GenerationEntryCounts[temp_a0];
    g_GenerationIndex = idx;
    entry = (s8 *) (g_GenerationEntryTables[temp_a0] + idx * 4);
    if (temp_a0 == 0) {
        p = g_GenerationEffectData;
        g_GenerationDataPtr = (s32) (g_GenerationColorPalette + entry[3] * 3);
        if (entry[2] != 0x12) {
            p = g_GenerationEffectDataAlt;
        }
        g_GenerationTablePtr = (s32) p;
        if (idx < 4) {
            g_GenerationFlags = 1;
        } else if (idx < 6) {
            g_GenerationFlags = 2;
        }
    }
    return entry;
}

/* Each coordinate/size pair occupies two consecutive words in the original data. */
extern s32 g_GenerationEffectX[2];
extern s32 g_GenerationEffectY;
extern s32 g_GenerationEffectW[2];
extern s32 g_GenerationEffectH;
extern effect_base_t *g_GenerationEffects[];

effect_base_t *effect_base_create(u32, u32, u32);

void dream_generation_create_effects(void) {
    s32 coords[4];
    s32 i;
    s32 offset;
    effect_base_t **base;
    effect_base_t **cursor;
    void **ctx;
    s32 result;

    if (g_GenerationFlags != 0) {
        __builtin_memcpy(coords, g_GenerationEffectX, 8);
        if (g_GenerationFlags == 2) {
            coords[1] += 0x1E;
        }
        __builtin_memcpy(coords + 2, g_GenerationEffectW, 8);
        g_GenerationEffects[0] = effect_base_create((u32)&coords[2], g_GenerationTablePtr, 0x1FFF);
        i = 1;
        offset = 3;
        base = g_GenerationEffects;
        cursor = base + 1;
        do {
            *cursor = effect_base_create((u32)&coords[2], offset + g_GenerationTablePtr, 0x1FFF);
            i++;
            (*cursor)->vtable->attach_to(*cursor, (s32)base[0], coords);
            cursor++;
            offset += 3;
            coords[1] += 3;
            coords[3] -= 7;
        } while (i < 0x12);
        ctx = *(void ***)((u8 *)g_GenerationEntityContext + 0xC);
        result = (*(s32 (**)(void *))((u8 *)*ctx + 0xAC))(ctx);
        g_GenerationEffects[0]->vtable->attach_to(g_GenerationEffects[0], result, coords);
    }
}


void dream_generation_shift_color(u8 *, u8 *, s32);

void dream_generation_update_effects(void) {
    u8 color[8];
    s32 data[2];
    s32 temp;
    s32 step;
    s32 i;
    s32 offset;
    effect_base_t **obj;
    effect_base_t *item;
    void *ctx;

    if (g_GenerationFlags != 0) {
        ctx = *(void **)((u8 *)g_GenerationEntityContext + 0xC);
        temp = (*(s32 *)((u8 *)ctx + 0x18) - *(s32 *)((u8 *)ctx + 0x24)) / 600;
        step = temp * 3;
        if (step > 0) {
            __builtin_memcpy(data, g_GenerationEffectX, sizeof(data));
            i = 0;
            if (g_GenerationFlags == 2) {
                data[1] += 0x1E;
            }
            obj = g_GenerationEffects;
            offset = 0;
            data[1] += step * 3;
            do {
                dream_generation_shift_color(color, (u8 *)(offset + g_GenerationTablePtr), step);
                item = *obj;
                item->vtable->set_color(item, 1, color);
                item = *obj;
                i++;
                offset += 3;
                item->vtable->set_offset(item, (s32)data);
                data[1] += 3;
                obj++;
            } while (i < 0x12);
            dream_generation_shift_color(color, (u8 *)g_GenerationDataPtr, step);
            (*(void (**)(void *, void *))((u8 *)*(void **)ctx + 0x64))(ctx, color);
        }
    }
}


void dream_generation_shift_color(u8 *arg0, u8 *arg1, s32 arg2) {
    arg0[0] = arg1[0] - arg2;
    arg0[1] = arg1[1] - arg2;
    arg0[2] = arg1[2] + arg2;
}

extern s32 g_GenerationFlags;
extern effect_base_t *g_GenerationEffects[];

void dream_generation_destroy_effects(void) {
    if (g_GenerationFlags != 0) {
        destroy_list(g_GenerationEffects, 0x12);
        g_GenerationFlags = 0;
    }
}

extern s32 g_GenerationStructureCount;
extern base_class_t *g_GenerationStructures[];
void generation_apply_context(s32, void *, s32, s32);
s32 *dream_generation_create_structures_random(s32 *, s32, s32);
s32 *dream_generation_create_structures_type1(s32 *, s32, s32);
s32 *dream_generation_create_structures_type0(s32 *, s32);
s32 *dream_generation_create_structures_type2(s32 *, s32);
void dream_generation_build_entities(void *arg0) {
    s32 count;
    s32 extra;
    s32 *next;
    if (g_GenerationType >= 0) {
        generation_apply_context(g_GenerationType, (void *)g_GenerationEntityContext[1],
                                 g_GenerationEntityContext[2], g_GenerationEntityContext[3]);
        count = ((s8 *)g_GenerationHeightTable)[0x18 + (rand() & 3)];
        extra = g_GenerationType == 2 ? 16-count : 0;
        g_GenerationStructureCount = count + extra;
        next = dream_generation_create_structures_random((s32 *)g_GenerationStructures, count, (s32)arg0);
        next = dream_generation_create_structures_type1(next, extra, (s32)arg0);
        if (g_GenerationType == 0) {
            dream_generation_create_structures_type0(next, (s32)arg0);
        } else if (g_GenerationType != 2) {
            return;
        } else {
            dream_generation_create_structures_type2(next, (s32)arg0);
        }
        g_GenerationStructureCount += 1;
    }
}

extern s32 g_GenerationStructureCount;
extern base_class_t *g_GenerationStructures[];

void dream_generation_update_structure_entities(s32 arg0) {
    s32 i;
    base_class_t **cursor;
    /* Retain the original stack layout with GCC 2.6.3. */
    s32 pad[2];

    if (g_GenerationType >= 0) {
        if (g_GenerationStructureCount > 0) {
            cursor = g_GenerationStructures;
            i = 0;
            do {
                base_class_t *obj = *cursor;

                ((void (*)(base_class_t *, s32))(*(u32 *)((u8 *)obj->vtable + 0xEC)))(obj, arg0);
                cursor++;
                i++;
            } while (i < g_GenerationStructureCount);
        }
    }
}

extern s32 g_GenerationType;
extern s32 g_GenerationStructureCount;
extern base_class_t *g_GenerationStructures[];

void dream_generation_destroy_structures(void) {
    if (g_GenerationType >= 0) {
        destroy_list(g_GenerationStructures, g_GenerationStructureCount);
    }
}

extern s32 *g_GenerationEntities[];
s32 dream_generation_stop_entity(s32 *);

void dream_generation_stop(void) {
    s32 **p;
    s32 i;

    dream_generation_destroy_effect();
    i = 0;
    dream_generation_destroy_effects();
    dream_generation_destroy_structures();
    p = g_GenerationEntities;
    do {
        *p = (s32 *) dream_generation_stop_entity(*p);
        i++;
        p++;
    } while (i < 2);
    if (g_GenerationOwner != 0) {
        g_GenerationOwner = 0;
    }
}

extern s32 g_GenerationSampleOffsets[];
extern s32 g_GenerationStructureSprite[];
extern void *g_GenerationSpawnSpriteSet[];
extern s32 g_GenerationSpawnParams[];
extern s32 g_GenerationSpawnRandom[];
extern u8 g_GenerationStructureSpriteData[];
void dream_generation_seed_palette_daily(void);
void dream_generation_seed_palette_random(s32, s32);
s32 generation_structure_create(s32, void *, s32, s32);

s32 *dream_generation_create_structures_random(s32 *arg0, s32 arg1, s32 arg2) {
    void (*seed)(s32, s32);
    s32 i;
    s32 index;

    g_GenerationSpawnRandom[0] = rand() % 7;
    g_GenerationSpawnSpriteSet[0] = (void *) (((u32) rand() % 5) * 12 + (s32) g_GenerationStructureSpriteData);
    index = (u32) rand() % 5;
    if (index != 0) {
        index = g_GenerationSampleOffsets[index];
    }
    seed = dream_generation_seed_palette_daily;
    if (g_CurrentDay != (g_CurrentDay / 7) * 7) {
        seed = dream_generation_seed_palette_random;
    }
    for (i = 0; i < arg1; i++) {
        seed(arg2, index);
        *arg0 = generation_structure_create(0, g_GenerationSpawnParams, g_GenerationOwner, arg2);
        arg0 += 1;
    }
    return arg0;
}

s32 *dream_generation_create_structures_type1(s32 *arg0, s32 arg1, s32 arg2) {
    s32 temp_s4;
    s32 var_s0;

    temp_s4 = g_GenerationSampleOffsets[2];
    g_GenerationSpawnSpriteSet[0] = g_GenerationStructureSprite;
    for (var_s0 = 0; var_s0 < arg1; var_s0++) {
        dream_generation_seed_palette_random(arg2, temp_s4);
        *arg0 = generation_structure_create(1, g_GenerationSpawnParams, g_GenerationOwner, arg2);
        arg0 += 1;
    }
    return arg0;
}

extern s32 g_GenerationSpawnParams[];
extern s32 g_GenerationSpawnSample[];
extern s32 g_GenerationSpawnRoll[];
extern s32 g_GenerationSpawnColor[];
extern u8 g_GenerationSpriteData[];
extern u8 g_GenerationEntityColorsA[];

s32 *dream_generation_create_structures_type0(s32 *arg0, s32 arg1) {
    dream_generation_seed_palette_random(arg1, g_GenerationSampleOffsets[2]);
    if (g_GenerationFlags != 0 && g_GenerationTablePtr == (s32)g_GenerationEffectData) {
        g_GenerationSpawnParams[0] = 0xFFFF5000;
        g_GenerationSpawnSample[0] = -0x2000;
        g_GenerationSpawnRoll[0] = 0;
        g_GenerationSpawnColor[0] = (s32)g_GenerationEntityColorsA + 3;
    } else {
        if (g_GenerationSpawnRoll[0] > 0) {
            g_GenerationSpawnRoll[0] = -g_GenerationSpawnRoll[0];
        }
        if (g_GenerationSpawnRoll[0] < -0x7800) {
            g_GenerationSpawnRoll[0] = -0x7800;
        }
        g_GenerationSpawnColor[0] = (s32)g_GenerationEntityColorsA + ((u32)rand() % 3) * 3;
    }
    g_GenerationSpawnParams[3] = (s32)g_GenerationSpriteData;
    *arg0++ = generation_structure_create(3, g_GenerationSpawnParams, g_GenerationOwner, arg1);
    return arg0;
}

extern s32 g_GenerationSpawnColor[];
extern u8 g_GenerationEntityColorsB[];
extern s32 g_GenerationEntityParamsAlt[];
extern u8 g_GenerationSpriteData[];
s32 *dream_generation_create_structures_type2(s32 *arg0, s32 arg1) {
    s32 temp;
    s32 day;
    s32 *p;

    temp = rand();
    day = g_CurrentDay;
    p = g_GenerationSpawnColor;
    *p++ = (s32)g_GenerationEntityColorsB + ((u32)temp % 3) * 3;
    *p++ = (day != (day / 20) * 20) ? g_GenerationEntityParamsAlt[0] : 0;
    dream_generation_seed_palette_random(arg1, g_GenerationSampleOffsets[2]);
    g_GenerationSpawnParams[3] = (s32)g_GenerationSpriteData;
    g_GenerationSpawnRandom[0] = rand() % 6;
    *arg0++ = generation_structure_create(2, g_GenerationSpawnParams, g_GenerationOwner, arg1);
    return arg0;
}


void generation_entity_effect_01(void *arg0, s32 *arg1);
void generation_entity_effect_02(void *arg0, s32 *arg1);
void generation_entity_effect_03(void *arg0, s32 *arg1);
void generation_entity_effect_04(void *arg0, s32 *arg1);
void generation_entity_effect_05(void *arg0, s32 *arg1);
void generation_entity_effect_06(void *arg0, s32 *arg1);
void generation_entity_effect_07(void *arg0, s32 *arg1);
void generation_entity_effect_08(void *arg0, s32 *arg1);
void generation_entity_effect_09(void *arg0, s32 *arg1);
void generation_entity_effect_10(void *arg0, s32 *arg1);
void generation_entity_effect_11(void *arg0, s32 *arg1);
void generation_entity_effect_12(void *arg0, s32 *arg1);
void generation_entity_effect_13(void *arg0, s32 *arg1);
void generation_entity_effect_14(void *arg0, void *arg1);

/* .sdata companions (defined in dream_generation_sdata.c). */
extern u8 g_GenerationInfoColor[];
extern u8 g_GenerationEntityColorDefault[];
extern s8 g_GenerationEntryDefault[];
extern s8 g_GenerationEntryA[];
extern s8 g_GenerationEntryB[];
extern s8 g_GenerationEntryC[];

/*
 * Dream generation .data tables.  All objects are kept larger than 8
 * bytes so GCC's -G8 small-data rule keeps them in .data; the few
 * original <=8-byte tables are folded into the neighbouring tables
 * (see the size comments in config/symbols.txt) and are referenced
 * through their base symbol plus a constant offset.
 */

u8 g_GenerationSpriteData[84] = {
    0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x3C,
    0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x78, 0x00, 0x01, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0xB4, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x00, 0xE6, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00, 0xFB, 0xFF, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00,
    0x00, 0x00, 0x01, 0x00, 0xFD, 0xFF, 0x01, 0x00, 0xB4, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x00,
};

u8 g_GenerationStructureSpriteData[60] = {
    0x07, 0x00, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x07, 0x00, 0x01, 0x00, 0x06, 0x00, 0x01,
    0x00, 0x01, 0x00, 0x01, 0x00, 0x07, 0x00, 0x01, 0x00, 0x07, 0x00, 0x01, 0x00, 0x01, 0x00,
    0x01, 0x00, 0x06, 0x00, 0x01, 0x00, 0x07, 0x00, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x02,
    0x00, 0x01, 0x00, 0x02, 0x00, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x07, 0x00, 0x01, 0x00,
};

s32 g_GenerationStructureSprite[6] = {
    0x00010001, 0x00010001, 0x00010001, 0x00010002, 0x00010001, 0x00010002,
};

u8 g_GenerationEntityColorsA[12] = {
    0xFF, 0xE6, 0xB4, 0xFF, 0xB4, 0xB4, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00,
};

u8 g_GenerationEntityColorsB[12] = {
    0xFF, 0x80, 0x00, 0xC8, 0xC8, 0xFF, 0x80, 0x80, 0xFF, 0x00, 0x00, 0x00,
};

u8 g_GenerationEffectDataAlt[56] = {
    0x37, 0x77, 0x94, 0x3C, 0x79, 0x97, 0x41, 0x7B, 0x9A, 0x46, 0x7D, 0x9D, 0x4B, 0x7F, 0xA0, 0x50, 0x81, 0xA3, 0x55,
    0x83, 0xA6, 0x5A, 0x85, 0xA9, 0x5F, 0x87, 0xAC, 0x64, 0x89, 0xAF, 0x69, 0x8B, 0xB2, 0x6E, 0x8D, 0xB5, 0x73, 0x8F,
    0xB8, 0x78, 0x96, 0xBB, 0x7B, 0x98, 0xBE, 0x7E, 0x99, 0xC0, 0x80, 0x9A, 0xC1, 0x82, 0x9B, 0xC2, 0x00, 0x00,
};

u8 g_GenerationEffectData[56] = {
    0x37, 0x77, 0x94, 0x3C, 0x79, 0x97, 0x41, 0x7B, 0x9A, 0x46, 0x7D, 0x9D, 0x4B, 0x7F, 0xA0, 0x50, 0x81, 0xA3, 0x5A,
    0x83, 0xA6, 0x6E, 0x85, 0xA9, 0x82, 0x87, 0xAC, 0x96, 0x89, 0xAF, 0xAA, 0x8B, 0xB2, 0xBE, 0x8D, 0xB5, 0xD2, 0x8F,
    0xB8, 0xE6, 0x96, 0xBB, 0xEB, 0x98, 0xBE, 0xF0, 0x99, 0xC0, 0xF5, 0x9A, 0xC1, 0xFA, 0x9B, 0xC2, 0x00, 0x00,
};

u8 g_GenerationInfoDefaultA[20] = {
    0x32, 0x00, 0x2C, 0x01, 0x3C, 0x00, 0x00, 0x00, 0xF4, 0x01,
    0xC4, 0xFF, 0xD4, 0xFE, 0x14, 0x00, 0x14, 0x00, 0x00, 0x00,
};

u8 g_GenerationInfoDefaultB[12] = {
    0xC8, 0xC8, 0xC8, 0xC8, 0xF0, 0xF0, 0xFF, 0xE6, 0xE6, 0x00, 0x00, 0x00,
};

u8 g_GenerationColorPalette[72] = {
    0x00, 0x00, 0x00, 0x40, 0x40, 0x40, 0x80, 0x80, 0x80, 0xFF, 0xFF, 0xFF, 0x40, 0x00, 0x00, 0x08, 0x20, 0x08,
    0x20, 0x20, 0x08, 0x18, 0x08, 0x08, 0x18, 0x18, 0x08, 0x18, 0x18, 0x80, 0x08, 0x08, 0x18, 0xFF, 0x00, 0x00,
    0x64, 0x8C, 0xB4, 0x32, 0x77, 0x91, 0x82, 0x9B, 0xC2, 0x00, 0x64, 0xBE, 0x00, 0x32, 0x1E, 0x46, 0x32, 0x00,
    0xFA, 0x9B, 0xC2, 0x00, 0xFF, 0x00, 0x78, 0x8C, 0xB4, 0x78, 0x00, 0xB4, 0xB4, 0x00, 0x78, 0x00, 0x00, 0x00,
};

s32 g_GenerationHeightTable[7] = {
    0x00006800, 0x00005000, 0x00003800, 0x00002000, 0x00001000, 0x00000800, 0x10080300,
};

s32 g_GenerationSampleOffsets[4] = {
    0xFFFFE800,
    0xFFFFD800,
    0xFFFFC800,
    0xFFFFB000,
};

s8 g_GenerationEntryTableData[144] = {
    0x00, 0x02, 0x0A, 0x0A, 0x00, 0x01, 0x0E, 0x0D, 0x00, 0x01, 0x0E, 0x0D, 0x00, 0x02, 0x0E, 0x0D, 0x00, 0x01,
    0x12, 0x0D, 0x00, 0x02, 0x12, 0x0D, 0x00, 0x01, 0x0E, 0x0D, 0x00, 0x02, 0x0E, 0x0D, 0x00, 0x02, 0x14, 0x0C,
    0x00, 0x03, 0x03, 0x03, 0x00, 0x02, 0x03, 0x03, 0x00, 0x01, 0x03, 0x03, 0x00, 0x00, 0x15, 0x15, 0x00, 0x01,
    0x13, 0x13, 0x00, 0x02, 0x02, 0x02, 0x00, 0x03, 0x02, 0x02, 0x00, 0x04, 0x02, 0x02, 0x00, 0x03, 0x15, 0x16,
    0x00, 0x04, 0x01, 0x01, 0x00, 0x02, 0x03, 0x00, 0x01, 0x02, 0x03, 0x00, 0x02, 0x02, 0x03, 0x00, 0x00, 0x02,
    0x07, 0x0A, 0x01, 0x02, 0x07, 0x0A, 0x02, 0x02, 0x07, 0x0A, 0x00, 0x02, 0x08, 0x0A, 0x01, 0x02, 0x08, 0x0A,
    0x02, 0x02, 0x08, 0x0A, 0x00, 0x02, 0x06, 0x06, 0x00, 0x02, 0x05, 0x05, 0x00, 0x01, 0x04, 0x04, 0x00, 0x03,
    0x00, 0x00, 0x00, 0x03, 0x09, 0x09, 0x00, 0x03, 0x16, 0x11, 0x00, 0x03, 0x10, 0x10, 0x00, 0x03, 0x11, 0x11,
};

u8 *g_GenerationEntryTables[4] = {
    (u8 *) (g_GenerationEntryTableData + 0x08),
    (u8 *) (g_GenerationEntryTableData + 0x24),
    (u8 *) (g_GenerationEntryTableData + 0x4C),
    (u8 *) (g_GenerationEntryTableData + 0x7C),
};

s8 g_GenerationEntryCounts[20] = {
    0x07, 0x0A, 0x0C, 0x05, 0x00, 0x01, 0x02, 0x03, 0x01, 0x02,
    0x03, 0x00, 0x00, 0x00, 0x02, 0x02, 0x01, 0x03, 0x01, 0x00,
};

s8 *g_GenerationLocationEntries[14] = {
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    (s8 *) (g_GenerationEntryTableData + 0x00),
    g_GenerationEntryDefault,
    g_GenerationEntryDefault,
    g_GenerationEntryB,
    g_GenerationEntryDefault,
    g_GenerationEntryC,
    g_GenerationEntryA,
    g_GenerationEntryA,
    NULL,
};

u8 *g_GenerationInfo[3] = {
    g_GenerationInfoDefaultA,
    g_GenerationInfoDefaultB,
    g_GenerationInfoColor,
};

s32 g_GenerationEntityParamsAlt[5] = {
    0, (s32) g_GenerationEntityColorDefault, -1, 0, 0,
};

s32 g_GenerationBorderRect0[3] = {
    0x01F00000,
    0x000000F8,
    0x00000008,
};

s32 g_GenerationBorderRect1[3] = {
    0x01F00100,
    0x00000001,
    0x00000008,
};

s32 g_GenerationBorderRect2[3] = {
    0x01F80000,
    0x000000F8,
    0x00000008,
};

s32 g_GenerationBorderRect3[3] = {
    0x01F80100,
    0x00000001,
    0x00000008,
};

s32 g_GenerationEntityRange[15] = {
    0x00000000, 0x00014000, 0x0000A000, 0x00004000, 0x0000A000, 0x0000F000, 0x00014000, 0x00014000,
    0x0000A000, 0x0000A000, 0x00005000, 0x0000A000, 0x0000F000, 0x0000A000, 0x00001000,
};

s32 g_GenerationEntityEffects[17] = {
    0,
    (s32) generation_entity_effect_01,
    (s32) generation_entity_effect_02,
    (s32) generation_entity_effect_03,
    (s32) generation_entity_effect_04,
    (s32) generation_entity_effect_05,
    (s32) generation_entity_effect_06,
    (s32) generation_entity_effect_07,
    (s32) generation_entity_effect_08,
    (s32) generation_entity_effect_09,
    (s32) generation_entity_effect_10,
    (s32) generation_entity_effect_11,
    (s32) generation_entity_effect_12,
    (s32) generation_entity_effect_13,
    (s32) generation_entity_effect_14,
    0,
    0,
};

s8 g_GenerationStageEntryData[448] = {
    0x00, 0x02, 0x06, 0x08, 0x00, 0x00, 0x0E, 0x00, 0x04, 0x03, 0x0B, 0x04, 0x00, 0x00, 0x09, 0x00, 0x03, 0x00, 0x10,
    0x09, 0x00, 0x00, 0x04, 0x00, 0x04, 0x01, 0x06, 0x02, 0x00, 0x00, 0x04, 0x00, 0x04, 0x01, 0x05, 0x0E, 0x00, 0x00,
    0x04, 0x00, 0x03, 0x02, 0x0F, 0x05, 0x00, 0x00, 0x04, 0x00, 0x03, 0x02, 0x0F, 0x11, 0x00, 0x00, 0x04, 0x00, 0x04,
    0x03, 0x05, 0x09, 0x00, 0x00, 0x04, 0x00, 0x03, 0x04, 0x10, 0x01, 0x00, 0x00, 0x04, 0x00, 0x03, 0x04, 0x10, 0x0D,
    0x00, 0x00, 0x04, 0x00, 0x07, 0x04, 0x07, 0x06, 0x00, 0x00, 0x01, 0x00, 0x0A, 0x04, 0x0E, 0x0B, 0x00, 0x00, 0x01,
    0x00, 0x05, 0x01, 0x03, 0x0A, 0x00, 0x00, 0x02, 0x00, 0x09, 0x03, 0x00, 0x06, 0x00, 0x00, 0x05, 0x00, 0x0A, 0x00,
    0x09, 0x0A, 0x00, 0x00, 0x05, 0x00, 0x0A, 0x00, 0x09, 0x0A, 0x00, 0x00, 0x05, 0x00, 0x0A, 0x00, 0x09, 0x0A, 0x00,
    0x00, 0x05, 0x00, 0x02, 0x00, 0x09, 0x09, 0x00, 0x00, 0x0C, 0x00, 0x0A, 0x00, 0x09, 0x0A, 0x00, 0x00, 0x0C, 0x00,
    0x0A, 0x00, 0x09, 0x0A, 0x00, 0x00, 0x0C, 0x00, 0x04, 0x01, 0x09, 0x00, 0x00, 0x00, 0x01, 0x00, 0x04, 0x01, 0x08,
    0x13, 0x00, 0x00, 0x01, 0x00, 0x08, 0x02, 0x0A, 0x0C, 0x00, 0x00, 0x01, 0x00, 0x07, 0x04, 0x07, 0x05, 0x00, 0x00,
    0x01, 0x00, 0x0A, 0x04, 0x0E, 0x0C, 0x00, 0x00, 0x01, 0x00, 0x02, 0x05, 0x02, 0x0B, 0x00, 0x00, 0x01, 0x00, 0x05,
    0x07, 0x13, 0x07, 0x00, 0x00, 0x01, 0x00, 0x03, 0x00, 0x03, 0x0A, 0x00, 0x00, 0x0C, 0x00, 0x0A, 0x00, 0x01, 0x13,
    0x00, 0x00, 0x0C, 0x00, 0x05, 0x01, 0x13, 0x07, 0x00, 0x00, 0x0C, 0x00, 0x0C, 0x01, 0x00, 0x0C, 0x00, 0x00, 0x0C,
    0x00, 0x07, 0x02, 0x04, 0x03, 0x00, 0x00, 0x0C, 0x00, 0x09, 0x02, 0x11, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x07, 0x05,
    0x0F, 0x08, 0x00, 0x00, 0x0C, 0x00, 0x06, 0x07, 0x05, 0x08, 0x00, 0x00, 0x0C, 0x00, 0x05, 0x08, 0x07, 0x0B, 0x00,
    0x00, 0x0C, 0x00, 0x0D, 0x0D, 0x0F, 0x0F, 0x00, 0x00, 0x0C, 0x00, 0x01, 0x0E, 0x01, 0x0F, 0x00, 0x00, 0x0C, 0x00,
    0x0D, 0x0E, 0x09, 0x09, 0x00, 0x00, 0x0C, 0x00, 0x05, 0x03, 0x02, 0x09, 0x00, 0x00, 0x03, 0x00, 0x00, 0x02, 0x10,
    0x11, 0x00, 0x00, 0x08, 0x00, 0x01, 0x04, 0x10, 0x0D, 0x00, 0x00, 0x06, 0x00, 0x01, 0x04, 0x11, 0x00, 0x00, 0x00,
    0x06, 0x00, 0x02, 0x04, 0x0E, 0x02, 0x00, 0x00, 0x06, 0x00, 0x04, 0x05, 0x00, 0x06, 0x00, 0x00, 0x0B, 0x00, 0x04,
    0x05, 0x00, 0x06, 0x00, 0x00, 0x07, 0x00, 0x02, 0x05, 0x02, 0x02, 0x00, 0x00, 0x07, 0x00, 0x00, 0x04, 0x12, 0x0F,
    0x00, 0x00, 0x07, 0x00, 0x01, 0x03, 0x08, 0x0D, 0x00, 0x00, 0x07, 0x00, 0x00, 0x02, 0x12, 0x11, 0x00, 0x00, 0x07,
    0x00, 0x01, 0x01, 0x07, 0x13, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x12, 0x12, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
    0x12, 0x05, 0x00, 0x00, 0x07, 0x00, 0x02, 0x00, 0x08, 0x0A, 0x00, 0x00, 0x0A, 0x00, 0x01, 0x01, 0x0C, 0x08, 0x00,
    0x00, 0x0A, 0x00, 0x00, 0x00, 0x03, 0x09, 0x00, 0x00, 0x0D, 0x00,
};

s32 *g_GenerationStageEntries[14] = {
    (s32 *) (g_GenerationStageEntryData + 0x000),
    NULL,
    (s32 *) (g_GenerationStageEntryData + 0x008),
    (s32 *) (g_GenerationStageEntryData + 0x050),
    (s32 *) (g_GenerationStageEntryData + 0x138),
    (s32 *) (g_GenerationStageEntryData + 0x160),
    NULL,
    NULL,
    NULL,
    NULL,
    (s32 *) (g_GenerationStageEntryData + 0x1A8),
    (s32 *) (g_GenerationStageEntryData + 0x1B0),
    NULL,
    (s32 *) (g_GenerationStageEntryData + 0x1B8),
};

s8 g_GenerationStageEntryCounts[16] = {
    0x01, 0x00, 0x09, 0x1D, 0x05, 0x09, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x01, 0x00, 0x00,
};
