// Optional catalogue observer; original game code and emulated RAM are read-only.
#ifndef LSD_NPC_CATALOGUE_OBSERVER_H
#define LSD_NPC_CATALOGUE_OBSERVER_H
#include <string.h>
#include "npc_entry_observer.h"

struct LsdNpcCatalogueEvent {
    uint32_t frame, pc, entity, ra, sp;
    int32_t timestamp;
    uint32_t instruction, context_tick;
    uint32_t entity_vtable, entity_id, context_state, context_owner, context_callback;
};
static_assert(sizeof(LsdNpcCatalogueEvent) == 52, "NPC catalogue record layout");
static uint8_t lsd_catalogue_targets[65536];
static LsdNpcCatalogueEvent lsd_catalogue_events[1024];
static uint32_t lsd_catalogue_count, lsd_catalogue_total, lsd_catalogue_overflow;
static uint32_t lsd_catalogue_target_count, lsd_catalogue_frame;

static void LsdNpcCatalogueEntry(const pscpu_timestamp_t timestamp, uint32_t pc) {
    // Preserve the existing selected-PC trace and its independent totals.
    LsdNpcCpuEntry(timestamp, pc);
    if ((pc & 3) || pc < 0x80010000 || pc >= 0x80200000) return;
    const uint32_t word = (pc - 0x80000000) >> 2;
    if (!(lsd_catalogue_targets[word >> 3] & (1u << (word & 7)))) return;
    ++lsd_catalogue_total;
    if (lsd_catalogue_count == 1024) { ++lsd_catalogue_overflow; return; }
    LsdNpcCatalogueEvent& event = lsd_catalogue_events[lsd_catalogue_count++];
    event.frame = lsd_catalogue_frame;
    event.pc = pc;
    event.entity = CPU->GetRegister(4, NULL, 0);
    event.ra = CPU->GetRegister(31, NULL, 0);
    event.sp = CPU->GetRegister(29, NULL, 0);
    event.timestamp = timestamp;
    event.instruction = LsdReadMainWord(pc);
    event.context_tick = LsdReadMainWord(event.entity + 0xA0);
    event.entity_vtable = LsdReadMainWord(event.entity);
    event.entity_id = LsdReadMainWord(event.entity + 0x98);
    event.context_state = LsdReadMainWord(event.entity + 0x9C);
    event.context_owner = LsdReadMainWord(event.entity + 0xA4);
    event.context_callback = LsdReadMainWord(event.entity + 0xA8);
}
ECL_EXPORT int LsdResetNpcCatalogue() {
    if (!CPU) return 0;
    memset(lsd_catalogue_targets, 0, sizeof(lsd_catalogue_targets));
    lsd_catalogue_count = lsd_catalogue_total = lsd_catalogue_overflow = 0;
    lsd_catalogue_target_count = 0;
    return 1;
}
ECL_EXPORT int LsdAddNpcCatalogueTarget(uint32_t pc) {
    if ((pc & 3) || pc < 0x80010000 || pc >= 0x80200000 || lsd_catalogue_target_count == 128) return 0;
    const uint32_t word = (pc - 0x80000000) >> 2;
    const uint8_t bit = (uint8_t)(1u << (word & 7));
    if (lsd_catalogue_targets[word >> 3] & bit) return 0;
    lsd_catalogue_targets[word >> 3] |= bit;
    ++lsd_catalogue_target_count;
    return 1;
}
ECL_EXPORT int LsdStartNpcCatalogue() {
    if (!CPU || !lsd_catalogue_target_count || !lsd_npc_watch) return 0;
    CPU->SetCPUHook(LsdNpcCatalogueEntry, NULL);
    return 1;
}
ECL_EXPORT void LsdBeginNpcCatalogueFrame(uint32_t frame) {
    lsd_catalogue_frame = frame;
    lsd_catalogue_count = 0;
}
ECL_EXPORT uint32_t LsdGetNpcCatalogueCount() { return lsd_catalogue_count; }
ECL_EXPORT uint32_t LsdGetNpcCatalogueTotal() { return lsd_catalogue_total; }
ECL_EXPORT uint32_t LsdGetNpcCatalogueOverflow() { return lsd_catalogue_overflow; }
ECL_EXPORT const LsdNpcCatalogueEvent* LsdGetNpcCatalogueEvents() { return lsd_catalogue_events; }
#endif
