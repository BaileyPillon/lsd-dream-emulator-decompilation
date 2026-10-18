// Optional return/data analysis. Original CPU source and guest RAM are read-only.
#ifndef LSD_DISPATCH_RETURN_OBSERVER_H
#define LSD_DISPATCH_RETURN_OBSERVER_H
#include "dispatch_flow_observer.h"

struct LsdReturnContext { uint32_t pc, ram, fetch, rs, sp, flags, sr; };
struct LsdMethodReturn {
    uint32_t frame, ordinal, entry_id, parent_id, kind, base_ordinal, entry_frame;
    int32_t entry_timestamp;
    uint32_t entry_pc, entry_sp, entry_ra, a0, a1, a2, a3;
    uint32_t return_pc, return_sp, return_ra, v0, v1;
    int32_t timestamp;
    uint32_t jump_pc, delay_pc, jump_ram, jump_fetch, delay_ram, delay_fetch;
    uint32_t jump_rs, jump_sp, delay_sp, jump_flags, delay_flags, jump_sr, delay_sr, sr;
    uint32_t a0_words[11], table_words[35], memory_words[4];
    uint32_t buffer_address, buffer_bytes, buffer_offset, buffer_status, helper_code_bytes, helper_code_offset;
    uint32_t sequence_low, sequence_high, entry_sequence_low, entry_sequence_high;
    uint32_t entry_transfer_pc, entry_delay_pc, entry_transfer_ram, entry_transfer_fetch, entry_delay_ram, entry_delay_fetch;
    uint32_t entry_transfer_flags, entry_delay_flags, entry_transfer_sr, entry_delay_sr;
    uint32_t entry_transfer_rs, entry_transfer_sp, entry_delay_sp, entry_a0_words[11];
    uint32_t read_request_entries, read_poll_entries, read_poll_returns, last_poll_value;
    uint32_t request_a0, request_a1, request_a2, last_poll_frame;
    int32_t last_poll_timestamp;
    uint32_t poll_return_pc, poll_return_sp, poll_jump_pc, poll_delay_pc;
    uint32_t poll_jump_ram, poll_jump_fetch, poll_delay_ram, poll_delay_fetch, poll_jump_rs;
    uint32_t poll_jump_flags, poll_delay_flags, poll_jump_sr, poll_delay_sr;
    uint32_t poll_sequence_low, poll_sequence_high, request_sequence_low, request_sequence_high;
    uint32_t request_call_pc, request_ra, poll_call_pc, poll_ra, poll_entry_sp;
};
static_assert(sizeof(LsdMethodReturn) == 600, "Method return transport layout");
struct LsdReturnPending { LsdMethodReturn e; uint32_t code[1024]; bool poll_active; };
static LsdReturnPending lsd_return_pending[64];
static LsdMethodReturn lsd_return_events[1024];
static uint8_t lsd_return_data[8 * 1024 * 1024];
static uint32_t lsd_return_count, lsd_return_total, lsd_return_entries, lsd_return_depth, lsd_return_max_depth;
static uint32_t lsd_return_overflow, lsd_return_mismatches, lsd_return_data_bytes;
static uint32_t lsd_return_read_pc, lsd_return_helper_pc, lsd_return_helper_bytes;
static uint32_t lsd_return_request_pc, lsd_return_poll_pc, lsd_return_request_call, lsd_return_poll_call;
static LsdReturnContext lsd_return_previous, lsd_return_before_previous;

static bool LsdReturnInBody(uint32_t pc) {
    if (pc >= lsd_return_helper_pc && pc - lsd_return_helper_pc < lsd_return_helper_bytes) return true;
    for (unsigned i = 0; i < lsd_dispatch_target_count; ++i)
        if (pc >= lsd_dispatch_targets[i].pc && pc - lsd_dispatch_targets[i].pc < lsd_dispatch_targets[i].bytes) return true;
    return false;
}
static uint32_t LsdReturnAppend(const void* data, uint32_t bytes) {
    const uint32_t offset = lsd_return_data_bytes;
    if (bytes > sizeof(lsd_return_data) - offset) { ++lsd_return_overflow; return 0; }
    memcpy(lsd_return_data + offset, data, bytes); lsd_return_data_bytes += bytes;
    return offset;
}
static void LsdReturnPush(uint32_t pc, uint32_t kind, uint32_t base, pscpu_timestamp_t timestamp, uint64_t sequence) {
    ++lsd_return_entries;
    if (lsd_return_depth == 64) { ++lsd_return_overflow; return; }
    LsdReturnPending& p = lsd_return_pending[lsd_return_depth];
    memset(&p, 0, sizeof(p));
    LsdMethodReturn& e = p.e;
    e.entry_id = lsd_return_entries;
    e.parent_id = lsd_return_depth ? lsd_return_pending[lsd_return_depth - 1].e.entry_id : 0;
    e.kind = kind; e.base_ordinal = base; e.entry_pc = pc;
    e.entry_frame = lsd_dispatch_frame; e.entry_timestamp = timestamp;
    e.entry_sp = CPU->GetRegister(29, NULL, 0); e.entry_ra = CPU->GetRegister(31, NULL, 0);
    e.a0 = CPU->GetRegister(4, NULL, 0); e.a1 = CPU->GetRegister(5, NULL, 0);
    e.a2 = CPU->GetRegister(6, NULL, 0); e.a3 = CPU->GetRegister(7, NULL, 0);
    for (unsigned i = 0; i < 11; ++i) e.entry_a0_words[i] = LsdDispatchRead(e.a0 + 4 * i);
    e.entry_sequence_low = (uint32_t)sequence; e.entry_sequence_high = (uint32_t)(sequence >> 32);
    const LsdReturnContext& a = lsd_return_before_previous;
    const LsdReturnContext& b = lsd_return_previous;
    e.entry_transfer_pc = a.pc; e.entry_delay_pc = b.pc;
    e.entry_transfer_ram = a.ram; e.entry_transfer_fetch = a.fetch;
    e.entry_delay_ram = b.ram; e.entry_delay_fetch = b.fetch;
    e.entry_transfer_flags = a.flags; e.entry_delay_flags = b.flags;
    e.entry_transfer_sr = a.sr; e.entry_delay_sr = b.sr;
    e.entry_transfer_rs = a.rs; e.entry_transfer_sp = a.sp; e.entry_delay_sp = b.sp;
    if (kind == 2) {
        if (!lsd_return_depth || lsd_return_pending[lsd_return_depth - 1].e.entry_pc != lsd_return_read_pc)
            ++lsd_return_mismatches;
        e.helper_code_bytes = lsd_return_helper_bytes;
        memcpy(p.code, MainRAM.data8 + (pc & 0x1FFFFFFF), e.helper_code_bytes);
    }
    ++lsd_return_depth;
    if (lsd_return_depth > lsd_return_max_depth) lsd_return_max_depth = lsd_return_depth;
}
static void LsdReturnFinish(uint32_t pc, pscpu_timestamp_t timestamp, uint64_t sequence) {
    LsdReturnPending& p = lsd_return_pending[lsd_return_depth - 1];
    ++lsd_return_total;
    if (lsd_return_count == 1024) { ++lsd_return_overflow; --lsd_return_depth; return; }
    LsdMethodReturn& e = lsd_return_events[lsd_return_count++]; e = p.e;
    e.frame = lsd_dispatch_frame; e.ordinal = lsd_return_total; e.timestamp = timestamp;
    e.return_pc = pc; e.return_sp = CPU->GetRegister(29, NULL, 0); e.return_ra = CPU->GetRegister(31, NULL, 0);
    e.v0 = CPU->GetRegister(2, NULL, 0); e.v1 = CPU->GetRegister(3, NULL, 0);
    e.sr = CPU->GetRegister(PS_CPU::GSREG_SR, NULL, 0);
    const LsdReturnContext& a = lsd_return_before_previous;
    const LsdReturnContext& b = lsd_return_previous;
    e.jump_pc = a.pc; e.delay_pc = b.pc; e.jump_ram = a.ram; e.jump_fetch = a.fetch;
    e.delay_ram = b.ram; e.delay_fetch = b.fetch; e.jump_rs = a.rs;
    e.jump_sp = a.sp; e.delay_sp = b.sp; e.jump_flags = a.flags; e.delay_flags = b.flags;
    e.jump_sr = a.sr; e.delay_sr = b.sr;
    e.sequence_low = (uint32_t)sequence; e.sequence_high = (uint32_t)(sequence >> 32);
    for (unsigned i = 0; i < 11; ++i) e.a0_words[i] = LsdDispatchRead(e.a0 + 4 * i);
    for (unsigned i = 0; i < 35; ++i) e.table_words[i] = LsdDispatchRead(e.a0_words[0] + 4 * i);
    for (unsigned i = 0; i < 4; ++i) e.memory_words[i] = LsdDispatchRead(lsd_dispatch_words[i]);
    if (e.helper_code_bytes) e.helper_code_offset = LsdReturnAppend(p.code, e.helper_code_bytes);
    if (e.entry_pc == lsd_return_read_pc || e.kind == 2) {
        e.buffer_address = e.a1;
        const uint32_t offset = e.a1 & 0x1FFFFFFF;
        if (!(e.sr & 0x10000) && offset < 0x200000 && e.a2 && e.a2 <= 0x200000 - offset) {
            e.buffer_bytes = e.a2; e.buffer_status = 1;
            e.buffer_offset = LsdReturnAppend(MainRAM.data8 + offset, e.buffer_bytes);
        } else e.buffer_status = 2;
    }
    if (p.poll_active) ++lsd_return_mismatches;
    --lsd_return_depth;
}
static void LsdDispatchReturnHook(const pscpu_timestamp_t timestamp, uint32_t pc) {
    const uint64_t sequence = lsd_flow_sequence;
    const uint32_t sp = CPU->GetRegister(29, NULL, 0);
    if (lsd_return_depth) {
        LsdReturnPending& p = lsd_return_pending[lsd_return_depth - 1];
        if (p.e.kind == 2) {
            if (p.poll_active && pc == lsd_return_poll_call + 8 && sp == p.e.poll_entry_sp) {
                p.poll_active = false; ++p.e.read_poll_returns;
                p.e.last_poll_value = CPU->GetRegister(2, NULL, 0);
                p.e.last_poll_frame = lsd_dispatch_frame; p.e.last_poll_timestamp = timestamp;
                p.e.poll_return_pc = pc; p.e.poll_return_sp = sp;
                const LsdReturnContext& a = lsd_return_before_previous;
                const LsdReturnContext& b = lsd_return_previous;
                p.e.poll_jump_pc = a.pc; p.e.poll_delay_pc = b.pc;
                p.e.poll_jump_ram = a.ram; p.e.poll_jump_fetch = a.fetch;
                p.e.poll_delay_ram = b.ram; p.e.poll_delay_fetch = b.fetch;
                p.e.poll_jump_rs = a.rs; p.e.poll_jump_flags = a.flags; p.e.poll_delay_flags = b.flags;
                p.e.poll_jump_sr = a.sr; p.e.poll_delay_sr = b.sr;
                p.e.poll_sequence_low = (uint32_t)sequence; p.e.poll_sequence_high = (uint32_t)(sequence >> 32);
            }
            if (pc == lsd_return_request_pc || pc == lsd_return_poll_pc) {
                const uint32_t call = pc == lsd_return_request_pc ? lsd_return_request_call : lsd_return_poll_call;
                if (lsd_return_before_previous.pc != call || lsd_return_previous.pc != call + 4 ||
                    CPU->GetRegister(31, NULL, 0) != call + 8) ++lsd_return_mismatches;
                if (pc == lsd_return_request_pc) {
                    ++p.e.read_request_entries;
                    p.e.request_a0 = CPU->GetRegister(4, NULL, 0); p.e.request_a1 = CPU->GetRegister(5, NULL, 0);
                    p.e.request_a2 = CPU->GetRegister(6, NULL, 0);
                    p.e.request_call_pc = lsd_return_before_previous.pc; p.e.request_ra = CPU->GetRegister(31, NULL, 0);
                    p.e.request_sequence_low = (uint32_t)sequence; p.e.request_sequence_high = (uint32_t)(sequence >> 32);
                } else {
                    if (p.poll_active) ++lsd_return_mismatches;
                    p.poll_active = true; ++p.e.read_poll_entries;
                    p.e.poll_call_pc = lsd_return_before_previous.pc; p.e.poll_ra = CPU->GetRegister(31, NULL, 0);
                    p.e.poll_entry_sp = sp;
                }
            }
        }
        if (pc == p.e.entry_ra && sp == p.e.entry_sp) LsdReturnFinish(pc, timestamp, sequence);
    }
    const uint32_t total = lsd_dispatch_total;
    LsdDispatchFlowHook(timestamp, pc);
    if (lsd_dispatch_total != total) LsdReturnPush(pc, 1, lsd_dispatch_total, timestamp, sequence);
    if (pc == lsd_return_helper_pc) LsdReturnPush(pc, 2, 0, timestamp, sequence);
    LsdReturnContext current = {}; current.pc = pc;
    const bool watched = !(pc & 3) && pc >= 0x80010000 && pc < 0x80200000 &&
        (LsdReturnInBody(pc) || lsd_flow_windows[(pc - 0x80000000) >> 2] ||
         (lsd_return_depth && lsd_return_pending[lsd_return_depth - 1].poll_active));
    if (watched) {
        current.ram = LsdDispatchRead(pc); current.fetch = current.ram; current.flags = 1;
        if (CPU->PeekCheckICache(pc, &current.fetch)) current.flags |= 2;
        current.rs = CPU->GetRegister((current.fetch >> 21) & 31, NULL, 0); current.sp = sp;
        current.sr = CPU->GetRegister(PS_CPU::GSREG_SR, NULL, 0);
    }
    lsd_return_before_previous = lsd_return_previous; lsd_return_previous = current;
}
ECL_EXPORT int LsdResetDispatchReturns() {
    lsd_return_count = lsd_return_total = lsd_return_entries = lsd_return_depth = lsd_return_max_depth = 0;
    lsd_return_overflow = lsd_return_mismatches = lsd_return_data_bytes = 0;
    lsd_return_read_pc = lsd_return_helper_pc = lsd_return_helper_bytes = 0;
    lsd_return_request_pc = lsd_return_poll_pc = lsd_return_request_call = lsd_return_poll_call = 0;
    lsd_return_previous = {}; lsd_return_before_previous = {}; return 1;
}
ECL_EXPORT int LsdConfigureDispatchReturns(uint32_t read, uint32_t helper, uint32_t bytes) {
    if ((read & 3) || read < 0x80010000 || read >= 0x80200000 ||
        !lsd_dispatch_index[(read - 0x80000000) >> 2] || (helper & 3) || helper < 0x80010000 ||
        helper >= 0x80200000 || !bytes || bytes > 4096 || (bytes & 3) || bytes > 0x80200000 - helper ||
        lsd_dispatch_index[(helper - 0x80000000) >> 2]) return 0;
    lsd_return_read_pc = read; lsd_return_helper_pc = helper; lsd_return_helper_bytes = bytes;
    return 1;
}
ECL_EXPORT int LsdConfigureDispatchReturnIO(uint32_t request, uint32_t poll, uint32_t request_call, uint32_t poll_call) {
    if (!lsd_return_helper_bytes || !LsdDispatchReadable(request) || !LsdDispatchReadable(poll) ||
        request_call < lsd_return_helper_pc || request_call - lsd_return_helper_pc >= lsd_return_helper_bytes - 4 ||
        poll_call < lsd_return_helper_pc || poll_call - lsd_return_helper_pc >= lsd_return_helper_bytes - 4) return 0;
    lsd_return_request_pc = request; lsd_return_poll_pc = poll;
    lsd_return_request_call = request_call; lsd_return_poll_call = poll_call; return 1;
}
ECL_EXPORT int LsdStartDispatchReturns() {
    if (!CPU || !lsd_return_read_pc || !lsd_return_helper_pc || !lsd_return_request_pc || !lsd_return_poll_pc || !lsd_flow_window_count) return 0;
    CPU->SetCPUHook(LsdDispatchReturnHook, NULL); return 1;
}
ECL_EXPORT void LsdBeginDispatchReturnFrame() { lsd_return_count = lsd_return_data_bytes = 0; }
ECL_EXPORT uint32_t LsdGetDispatchReturnCount() { return lsd_return_count; }
ECL_EXPORT uint32_t LsdGetDispatchReturnTotal() { return lsd_return_total; }
ECL_EXPORT uint32_t LsdGetDispatchReturnEntries() { return lsd_return_entries; }
ECL_EXPORT uint32_t LsdGetDispatchReturnOverflow() { return lsd_return_overflow; }
ECL_EXPORT uint32_t LsdGetDispatchReturnMismatches() { return lsd_return_mismatches; }
ECL_EXPORT uint32_t LsdGetDispatchReturnPending() { return lsd_return_depth; }
ECL_EXPORT uint32_t LsdGetDispatchReturnMaxDepth() { return lsd_return_max_depth; }
ECL_EXPORT const LsdMethodReturn* LsdGetDispatchReturnEvents() { return lsd_return_events; }
ECL_EXPORT const uint8_t* LsdGetDispatchReturnData() { return lsd_return_data; }
ECL_EXPORT uint32_t LsdGetDispatchReturnDataBytes() { return lsd_return_data_bytes; }
#endif
