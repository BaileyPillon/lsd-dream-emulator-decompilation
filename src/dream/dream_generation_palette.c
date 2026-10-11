#include "common.h"
#include <psx/rand.h>
extern s32 g_GenerationSampleOffsets[];
extern s32 g_GenerationSpawnParams;
extern s32 g_GenerationSpawnSample[];
extern s32 g_GenerationSpawnRoll;
extern s32 g_GenerationSpawnSprite[];
extern u8 g_GenerationSpriteData[];
extern s32 g_GenerationSpawnIndex[];
void dream_generation_seed_palette_random(s32 unused, s32 arg1) {
    if (arg1 == 0) {
        arg1 = g_GenerationSampleOffsets[rand() & 3];
    }
    g_GenerationSpawnSample[0] = arg1;
    g_GenerationSpawnParams = (rand() % 23) << 11;
    if (rand() & 1) {
        g_GenerationSpawnParams = -g_GenerationSpawnParams;
    }
    g_GenerationSpawnRoll = (rand() % 23) << 11;
    if (rand() & 1) {
        g_GenerationSpawnRoll = -g_GenerationSpawnRoll;
    }
    g_GenerationSpawnSprite[0] = ((u32)rand() % 7) * 12 + (s32)g_GenerationSpriteData;
    g_GenerationSpawnIndex[0] = rand() % 5;
}
