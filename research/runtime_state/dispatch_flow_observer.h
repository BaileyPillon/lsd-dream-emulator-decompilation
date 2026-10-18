// Optional read-only context for the existing method-entry observer.
#ifndef LSD_DISPATCH_FLOW_OBSERVER_H
#define LSD_DISPATCH_FLOW_OBSERVER_H
#include "dispatch_entry_observer.h"

struct LsdFlowInstruction {
    uint32_t pc, ram_word, fetch_word, rs_value, rt_value, load_address, load_word, flags, sr;
    int32_t timestamp;
};
struct LsdFlowEvent {
    uint32_t frame, ordinal, pc, history_count, sequence_low, sequence_high;
    LsdFlowInstruction history[16];
};
static_assert(sizeof(LsdFlowInstruction) == 40, "Flow instruction layout");
static_assert(sizeof(LsdFlowEvent) == 664, "Flow event layout");
static uint8_t lsd_flow_windows[524288];
static LsdFlowInstruction lsd_flow_history[16];
static LsdFlowEvent lsd_flow_events[1024];
static uint32_t lsd_flow_count, lsd_flow_total, lsd_flow_overflow, lsd_flow_window_count;
static uint64_t lsd_flow_sequence;

static void LsdDispatchFlowHook(const pscpu_timestamp_t timestamp, uint32_t pc) {
    const uint32_t before = lsd_dispatch_total;
    LsdDispatchCpuEntry(timestamp, pc);
    if (lsd_dispatch_total != before) {
        ++lsd_flow_total;
        if (lsd_flow_count == 1024) ++lsd_flow_overflow;
        else {
            LsdFlowEvent& e = lsd_flow_events[lsd_flow_count++];
            e.frame = lsd_dispatch_frame; e.ordinal = lsd_flow_total; e.pc = pc;
            e.history_count = lsd_flow_sequence < 16 ? (uint32_t)lsd_flow_sequence : 16;
            e.sequence_low = (uint32_t)lsd_flow_sequence;
            e.sequence_high = (uint32_t)(lsd_flow_sequence >> 32);
            memset(e.history, 0, sizeof(e.history));
            for (unsigned i = 0; i < e.history_count; ++i)
                e.history[i] = lsd_flow_history[(lsd_flow_sequence - e.history_count + i) & 15];
        }
    }
    LsdFlowInstruction& h = lsd_flow_history[lsd_flow_sequence++ & 15];
    memset(&h, 0, sizeof(h)); h.pc = pc; h.timestamp = timestamp;
    if ((pc & 3) || pc < 0x80010000 || pc >= 0x80200000 ||
        !lsd_flow_windows[(pc - 0x80000000) >> 2]) return;
    h.ram_word = LsdDispatchRead(pc); h.fetch_word = h.ram_word; h.flags = 1;
    if (CPU->PeekCheckICache(pc, &h.fetch_word)) h.flags |= 2;
    h.rs_value = CPU->GetRegister((h.fetch_word >> 21) & 31, NULL, 0);
    h.rt_value = CPU->GetRegister((h.fetch_word >> 16) & 31, NULL, 0);
    h.sr = CPU->GetRegister(PS_CPU::GSREG_SR, NULL, 0);
    if ((h.fetch_word >> 26) == 35) {
        h.load_address = h.rs_value + (int32_t)(int16_t)(h.fetch_word & 0xFFFF);
        if (!(h.sr & 0x10000) && LsdDispatchReadable(h.load_address)) {
            h.load_word = LsdDispatchRead(h.load_address); h.flags |= 4;
        }
    }
}
ECL_EXPORT int LsdResetDispatchFlow() {
    memset(lsd_flow_windows, 0, sizeof(lsd_flow_windows));
    memset(lsd_flow_history, 0, sizeof(lsd_flow_history));
    lsd_flow_count = lsd_flow_total = lsd_flow_overflow = lsd_flow_window_count = 0;
    lsd_flow_sequence = 0; return 1;
}
ECL_EXPORT int LsdAddDispatchFlowSite(uint32_t pc) {
    if ((pc & 3) || pc < 0x8001003C || pc >= 0x801FFFFC || lsd_flow_window_count == 16) return 0;
    for (unsigned i = 0; i < 17; ++i) lsd_flow_windows[(pc - 60 + i * 4 - 0x80000000) >> 2] = 1;
    ++lsd_flow_window_count; return 1;
}
ECL_EXPORT int LsdStartDispatchFlow() {
    if (!CPU || !lsd_dispatch_target_count || !lsd_flow_window_count) return 0;
    CPU->SetCPUHook(LsdDispatchFlowHook, NULL); return 1;
}
ECL_EXPORT void LsdBeginDispatchFlowFrame() { lsd_flow_count = 0; }
ECL_EXPORT uint32_t LsdGetDispatchFlowCount() { return lsd_flow_count; }
ECL_EXPORT uint32_t LsdGetDispatchFlowTotal() { return lsd_flow_total; }
ECL_EXPORT uint32_t LsdGetDispatchFlowOverflow() { return lsd_flow_overflow; }
ECL_EXPORT const LsdFlowEvent* LsdGetDispatchFlowEvents() { return lsd_flow_events; }
#endif
