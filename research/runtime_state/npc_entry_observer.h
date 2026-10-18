// Optional analysis extension for BizHawk 2.11.1 shock.cpp.
// The separate builder includes this after the unmodified adapter.
// No game code or emulated MainRAM is written by this observer.
#ifndef LSD_NPC_ENTRY_OBSERVER_H
#define LSD_NPC_ENTRY_OBSERVER_H


// Optional host analysis only. Original CPU execution uses its existing hook.
struct LsdNpcTraceEvent {
    uint32_t frame, pc, entity, ra, sp;
    int32_t timestamp;
    uint32_t instruction, context_tick;
};
static_assert(sizeof(LsdNpcTraceEvent) == 32, "NPC trace record layout");
static LsdNpcTraceEvent lsd_npc_events[256];
static uint32_t lsd_npc_count, lsd_npc_frame, lsd_npc_watch;
static uint32_t lsd_npc_total, lsd_npc_overflow;

static uint32_t LsdReadMainWord(uint32_t address) {
    uint32_t offset = address & 0x1FFFFFFF;
    if ((offset & 3) || offset > 2048 * 1024 - 4) return 0xFFFFFFFF;
    const uint8_t* p = MainRAM.data8 + offset;
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void LsdNpcCpuEntry(const pscpu_timestamp_t timestamp, uint32_t pc) {
    if (pc != lsd_npc_watch) return;
    ++lsd_npc_total;
    if (lsd_npc_count == 256) { ++lsd_npc_overflow; return; }
    LsdNpcTraceEvent& event = lsd_npc_events[lsd_npc_count++];
    event.frame = lsd_npc_frame;
    event.pc = pc;
    event.entity = CPU->GetRegister(4, NULL, 0);
    event.ra = CPU->GetRegister(31, NULL, 0);
    event.sp = CPU->GetRegister(29, NULL, 0);
    event.timestamp = timestamp;
    event.instruction = LsdReadMainWord(pc);
    event.context_tick = LsdReadMainWord(event.entity + 0xA0);
}
ECL_EXPORT int LsdConfigureNpcTrace(uint32_t pc) {
    if (!CPU || (pc & 3) || pc < 0x80010000 || pc >= 0x80200000) return 0;
    lsd_npc_count = lsd_npc_total = lsd_npc_overflow = 0;
    lsd_npc_watch = pc;
    CPU->SetCPUHook(LsdNpcCpuEntry, NULL);
    return 1;
}
ECL_EXPORT void LsdBeginNpcTraceFrame(uint32_t frame) {
    lsd_npc_frame = frame;
    lsd_npc_count = 0;
}
ECL_EXPORT uint32_t LsdGetNpcTraceCount() { return lsd_npc_count; }
ECL_EXPORT uint32_t LsdGetNpcTraceTotal() { return lsd_npc_total; }
ECL_EXPORT uint32_t LsdGetNpcTraceOverflow() { return lsd_npc_overflow; }
ECL_EXPORT const LsdNpcTraceEvent* LsdGetNpcTraceEvents() { return lsd_npc_events; }
ECL_EXPORT void LsdDisableNpcTrace() { CPU->SetCPUHook(NULL, NULL); }

#endif
