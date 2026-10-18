// Optional analysis adapter. No original game code or emulated RAM is written.
#ifndef LSD_DISPATCH_ENTRY_OBSERVER_H
#define LSD_DISPATCH_ENTRY_OBSERVER_H
#include <string.h>

struct LsdDispatchEvent {
    uint32_t frame, pc, a0, a1, a2, a3, ra, sp;
    int32_t timestamp;
    uint32_t instruction, transfer_pc, delay_pc, transfer_word, delay_word;
    uint32_t a0_words[11], a0_table_words[35], memory_words[4], code_bytes, code_words[1024];
};
static_assert(sizeof(LsdDispatchEvent) == 4356, "Method entry transport layout");
struct LsdDispatchTarget { uint32_t pc, bytes; };
static LsdDispatchTarget lsd_dispatch_targets[16];
static uint8_t lsd_dispatch_index[524288];
static LsdDispatchEvent lsd_dispatch_events[1024];
static uint32_t lsd_dispatch_words[4];
static uint32_t lsd_dispatch_count, lsd_dispatch_total, lsd_dispatch_overflow;
static uint32_t lsd_dispatch_target_count, lsd_dispatch_frame;
static uint32_t lsd_dispatch_previous, lsd_dispatch_before_previous;
static bool lsd_dispatch_words_configured;

static bool LsdDispatchReadable(uint32_t address) {
    const uint32_t offset = address & 0x1FFFFFFF;
    return !(offset & 3) && offset <= 2048 * 1024 - 4;
}
static uint32_t LsdDispatchRead(uint32_t address) {
    if (!LsdDispatchReadable(address)) return 0xFFFFFFFF;
    const uint8_t* p = MainRAM.data8 + (address & 0x1FFFFFFF);
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void LsdDispatchCpuEntry(const pscpu_timestamp_t timestamp, uint32_t pc) {
    uint32_t index = 0;
    if (!(pc & 3) && pc >= 0x80010000 && pc < 0x80200000)
        index = lsd_dispatch_index[(pc - 0x80000000) >> 2];
    if (index) {
        ++lsd_dispatch_total;
        if (lsd_dispatch_count == 1024) ++lsd_dispatch_overflow;
        else {
            LsdDispatchEvent& e = lsd_dispatch_events[lsd_dispatch_count++];
            e.frame = lsd_dispatch_frame; e.pc = pc;
            e.a0 = CPU->GetRegister(4, NULL, 0); e.a1 = CPU->GetRegister(5, NULL, 0);
            e.a2 = CPU->GetRegister(6, NULL, 0); e.a3 = CPU->GetRegister(7, NULL, 0);
            e.ra = CPU->GetRegister(31, NULL, 0); e.sp = CPU->GetRegister(29, NULL, 0);
            e.timestamp = timestamp; e.instruction = LsdDispatchRead(pc);
            e.transfer_pc = lsd_dispatch_before_previous; e.delay_pc = lsd_dispatch_previous;
            e.transfer_word = LsdDispatchRead(e.transfer_pc); e.delay_word = LsdDispatchRead(e.delay_pc);
            for (unsigned i = 0; i < 11; ++i) e.a0_words[i] = LsdDispatchRead(e.a0 + 4 * i);
            for (unsigned i = 0; i < 35; ++i) e.a0_table_words[i] = LsdDispatchRead(e.a0_words[0] + 4 * i);
            for (unsigned i = 0; i < 4; ++i) e.memory_words[i] = LsdDispatchRead(lsd_dispatch_words[i]);
            e.code_bytes = lsd_dispatch_targets[index - 1].bytes;
            memcpy(e.code_words, MainRAM.data8 + (pc & 0x1FFFFFFF), e.code_bytes);
        }
    }
    lsd_dispatch_before_previous = lsd_dispatch_previous;
    lsd_dispatch_previous = pc;
}
ECL_EXPORT int LsdResetDispatchTrace() {
    if (!CPU) return 0;
    memset(lsd_dispatch_index, 0, sizeof(lsd_dispatch_index));
    lsd_dispatch_count = lsd_dispatch_total = lsd_dispatch_overflow = 0;
    lsd_dispatch_target_count = 0; lsd_dispatch_words_configured = false;
    lsd_dispatch_previous = lsd_dispatch_before_previous = 0xFFFFFFFF;
    return 1;
}
ECL_EXPORT int LsdAddDispatchTarget(uint32_t pc, uint32_t bytes) {
    if ((pc & 3) || pc < 0x80010000 || pc >= 0x80200000 || !bytes || (bytes & 3) ||
        bytes > 4096 || bytes > 0x80200000 - pc || lsd_dispatch_target_count == 16) return 0;
    const uint32_t word = (pc - 0x80000000) >> 2;
    if (lsd_dispatch_index[word]) return 0;
    lsd_dispatch_targets[lsd_dispatch_target_count] = {pc, bytes};
    lsd_dispatch_index[word] = ++lsd_dispatch_target_count;
    return 1;
}
ECL_EXPORT int LsdConfigureDispatchWords(uint32_t a, uint32_t b, uint32_t c, uint32_t d) {
    if (!LsdDispatchReadable(a) || !LsdDispatchReadable(b) ||
        !LsdDispatchReadable(c) || !LsdDispatchReadable(d)) return 0;
    lsd_dispatch_words[0] = a; lsd_dispatch_words[1] = b;
    lsd_dispatch_words[2] = c; lsd_dispatch_words[3] = d;
    lsd_dispatch_words_configured = true;
    return 1;
}
ECL_EXPORT int LsdStartDispatchTrace() {
    if (!CPU || !lsd_dispatch_target_count || !lsd_dispatch_words_configured) return 0;
    CPU->SetCPUHook(LsdDispatchCpuEntry, NULL);
    return 1;
}
ECL_EXPORT void LsdBeginDispatchFrame(uint32_t frame) { lsd_dispatch_frame = frame; lsd_dispatch_count = 0; }
ECL_EXPORT uint32_t LsdGetDispatchCount() { return lsd_dispatch_count; }
ECL_EXPORT uint32_t LsdGetDispatchTotal() { return lsd_dispatch_total; }
ECL_EXPORT uint32_t LsdGetDispatchOverflow() { return lsd_dispatch_overflow; }
ECL_EXPORT const LsdDispatchEvent* LsdGetDispatchEvents() { return lsd_dispatch_events; }
ECL_EXPORT void LsdDisableDispatchTrace() { CPU->SetCPUHook(NULL, NULL); }
#endif
