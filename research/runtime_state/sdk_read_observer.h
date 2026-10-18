// Optional SDK boundary observation. Reads original CPU state and RAM only.
#ifndef LSD_SDK_READ_OBSERVER_H
#define LSD_SDK_READ_OBSERVER_H
#include "dispatch_return_observer.h"

struct LsdSdkReadEvent {
    uint32_t frame, ordinal, entry_id, parent_id, kind, entry_frame;
    int32_t entry_timestamp;
    uint32_t entry_pc, entry_sp, entry_ra, a0, a1, a2, a3;
    uint32_t return_pc, return_sp, return_ra, v0, v1;
    int32_t timestamp;
    uint32_t entry_sequence_low, entry_sequence_high, sequence_low, sequence_high;
    LsdReturnContext entry_jump, entry_delay, jump, delay;
    uint32_t entry_sr, sr, arg_readable, arg_words[4];
    uint32_t entry_sdk_words[16], sdk_words[16], entry_cd_words[8], cd_words[8];
    uint32_t code_bytes, code_offset, buffer_address, buffer_bytes, buffer_offset, buffer_status;
    uint32_t transfer_id, transfer_sectors, transfer_mode;
};
static_assert(sizeof(LsdSdkReadEvent) == 464, "SDK read transport layout");
struct LsdSdkTarget { uint32_t pc, bytes, kind; };
struct LsdSdkPending { LsdSdkReadEvent e; uint32_t code[1024], receiver_words[11]; };
static LsdSdkTarget lsd_sdk_targets[16];
static uint8_t lsd_sdk_windows[524288];
static LsdSdkPending lsd_sdk_pending[64];
static LsdSdkReadEvent lsd_sdk_events[32768];
static uint8_t lsd_sdk_data[32 * 1024 * 1024];
static uint32_t lsd_sdk_target_count, lsd_sdk_count, lsd_sdk_total, lsd_sdk_entries;
static uint32_t lsd_sdk_depth, lsd_sdk_max_depth, lsd_sdk_overflow, lsd_sdk_mismatches, lsd_sdk_data_bytes;
static uint32_t lsd_sdk_transfer, lsd_sdk_destination, lsd_sdk_sectors, lsd_sdk_mode;
static uint32_t lsd_sdk_completions, lsd_sdk_failures, lsd_sdk_unassociated, lsd_sdk_overlaps;
static LsdReturnContext lsd_sdk_previous, lsd_sdk_before_previous;

static uint32_t LsdSdkAppend(const void* data, uint32_t bytes) {
    uint32_t offset = lsd_sdk_data_bytes;
    if (bytes > sizeof(lsd_sdk_data) - offset) { ++lsd_sdk_overflow; return 0; }
    memcpy(lsd_sdk_data + offset, data, bytes); lsd_sdk_data_bytes += bytes;
    return offset;
}
static void LsdSdkWords(uint32_t* sdk, uint32_t* cd) {
    for (unsigned i = 0; i < 16; ++i) sdk[i] = LsdDispatchRead(0x8006D8DC + i * 4);
    for (unsigned i = 0; i < 8; ++i) cd[i] = LsdDispatchRead(0x8006D5FC + i * 4);
}
static void LsdSdkFinish(uint32_t pc, pscpu_timestamp_t timestamp, uint64_t sequence) {
    LsdSdkPending& p = lsd_sdk_pending[lsd_sdk_depth - 1];
    ++lsd_sdk_total;
    if (lsd_sdk_count == 32768) { ++lsd_sdk_overflow; --lsd_sdk_depth; return; }
    LsdSdkReadEvent& e = lsd_sdk_events[lsd_sdk_count++]; e = p.e;
    e.frame = lsd_dispatch_frame; e.ordinal = lsd_sdk_total; e.timestamp = timestamp;
    e.return_pc = pc; e.return_sp = CPU->GetRegister(29, NULL, 0); e.return_ra = CPU->GetRegister(31, NULL, 0);
    e.v0 = CPU->GetRegister(2, NULL, 0); e.v1 = CPU->GetRegister(3, NULL, 0);
    e.sr = CPU->GetRegister(PS_CPU::GSREG_SR, NULL, 0);
    e.sequence_low = (uint32_t)sequence; e.sequence_high = (uint32_t)(sequence >> 32);
    e.jump = lsd_sdk_before_previous; e.delay = lsd_sdk_previous;
    LsdSdkWords(e.sdk_words, e.cd_words);
    e.code_offset = LsdSdkAppend(p.code, e.code_bytes);
    if (e.kind == 1 && e.v0 == 1) {
        if (lsd_sdk_transfer) { ++lsd_sdk_overlaps; e.buffer_status = 3; }
        lsd_sdk_transfer = e.entry_id; lsd_sdk_destination = e.a1;
        lsd_sdk_sectors = e.a0; lsd_sdk_mode = e.a2;
    }
    e.transfer_id = lsd_sdk_transfer; e.transfer_sectors = lsd_sdk_sectors; e.transfer_mode = lsd_sdk_mode;
    if (e.kind == 2 && (int32_t)e.v0 <= 0) {
        if (!lsd_sdk_transfer) { ++lsd_sdk_unassociated; e.buffer_status = 2; }
        else if (e.v0) { ++lsd_sdk_failures; e.buffer_status = 5; }
        else {
            const uint32_t offset = lsd_sdk_destination & 0x1FFFFFFF;
            e.buffer_address = lsd_sdk_destination;
            if (!(e.sr & 0x10000) && lsd_sdk_mode == 0x80 && lsd_sdk_sectors &&
                offset < 0x200000 && lsd_sdk_sectors <= (0x200000 - offset) / 2048) {
                e.buffer_bytes = lsd_sdk_sectors * 2048; e.buffer_status = 1;
                e.buffer_offset = LsdSdkAppend(MainRAM.data8 + offset, e.buffer_bytes);
                ++lsd_sdk_completions;
            } else e.buffer_status = 4;
        }
        lsd_sdk_transfer = lsd_sdk_destination = lsd_sdk_sectors = lsd_sdk_mode = 0;
    }
    if (e.kind >= 5) {
        const uint32_t address = e.kind == 5 ? e.v0 : e.a0;
        const uint32_t offset = address & 0x1FFFFFFF;
        if (address && !(e.sr & 0x10000)) {
            if (e.kind == 5 && offset >= 4 && offset <= 0x200000 - 12) {
                e.buffer_address = address - 4; e.buffer_bytes = 16; e.buffer_status = 7;
                e.buffer_offset = LsdSdkAppend(MainRAM.data8 + offset - 4, 16);
            } else if (e.kind == 6 && offset >= 4 && offset <= 0x200000 - 12) {
                uint32_t pair[8]; memcpy(pair, p.receiver_words, 16);
                memcpy(pair + 4, MainRAM.data8 + offset - 4, 16);
                e.buffer_address = address - 4; e.buffer_bytes = 32; e.buffer_status = 8;
                e.buffer_offset = LsdSdkAppend(pair, sizeof(pair));
            } else if (e.kind >= 7 && offset <= 0x200000 - 44) {
                uint32_t pair[22]; memcpy(pair, p.receiver_words, 44);
                memcpy(pair + 11, MainRAM.data8 + offset, 44);
                e.buffer_address = address; e.buffer_bytes = 88; e.buffer_status = 6;
                e.buffer_offset = LsdSdkAppend(pair, sizeof(pair));
            } else e.buffer_status = 4;
        } else if (address) e.buffer_status = 4;
    }
    --lsd_sdk_depth;
}
static void LsdSdkPush(const LsdSdkTarget& target, pscpu_timestamp_t timestamp, uint64_t sequence) {
    ++lsd_sdk_entries;
    if (lsd_sdk_depth == 64) { ++lsd_sdk_overflow; return; }
    LsdSdkPending& p = lsd_sdk_pending[lsd_sdk_depth]; memset(&p, 0, sizeof(p));
    LsdSdkReadEvent& e = p.e;
    e.entry_id = lsd_sdk_entries;
    e.parent_id = lsd_sdk_depth ? lsd_sdk_pending[lsd_sdk_depth - 1].e.entry_id : 0;
    e.kind = target.kind; e.entry_pc = target.pc; e.entry_frame = lsd_dispatch_frame; e.entry_timestamp = timestamp;
    e.entry_sp = CPU->GetRegister(29, NULL, 0); e.entry_ra = CPU->GetRegister(31, NULL, 0);
    e.a0 = CPU->GetRegister(4, NULL, 0); e.a1 = CPU->GetRegister(5, NULL, 0);
    e.a2 = CPU->GetRegister(6, NULL, 0); e.a3 = CPU->GetRegister(7, NULL, 0);
    e.entry_sr = CPU->GetRegister(PS_CPU::GSREG_SR, NULL, 0);
    const uint32_t receiver = e.a0 & 0x1FFFFFFF;
    if (!(e.entry_sr & 0x10000)) {
        if (e.kind == 6 && e.a0 && receiver >= 4 && receiver <= 0x200000 - 12)
            memcpy(p.receiver_words, MainRAM.data8 + receiver - 4, 16);
        else if (e.kind >= 7 && e.a0 && receiver <= 0x200000 - 44)
            memcpy(p.receiver_words, MainRAM.data8 + receiver, 44);
    }
    e.entry_sequence_low = (uint32_t)sequence; e.entry_sequence_high = (uint32_t)(sequence >> 32);
    e.entry_jump = lsd_sdk_before_previous; e.entry_delay = lsd_sdk_previous;
    const uint32_t offset = e.a1 & 0x1FFFFFFF;
    if (!(e.entry_sr & 0x10000) && offset <= 0x200000 - 16) {
        e.arg_readable = 1; memcpy(e.arg_words, MainRAM.data8 + offset, 16);
    }
    LsdSdkWords(e.entry_sdk_words, e.entry_cd_words);
    e.code_bytes = target.bytes; memcpy(p.code, MainRAM.data8 + (target.pc & 0x1FFFFFFF), target.bytes);
    ++lsd_sdk_depth;
    if (lsd_sdk_depth > lsd_sdk_max_depth) lsd_sdk_max_depth = lsd_sdk_depth;
}
static void LsdSdkReadHook(const pscpu_timestamp_t timestamp, uint32_t pc) {
    const uint64_t sequence = lsd_flow_sequence;
    const uint32_t sp = CPU->GetRegister(29, NULL, 0);
    if (lsd_sdk_depth) {
        const LsdSdkReadEvent& e = lsd_sdk_pending[lsd_sdk_depth - 1].e;
        if (pc == e.entry_ra && sp == e.entry_sp) LsdSdkFinish(pc, timestamp, sequence);
    }
    for (unsigned i = 0; i < lsd_sdk_target_count; ++i)
        if (pc == lsd_sdk_targets[i].pc) { LsdSdkPush(lsd_sdk_targets[i], timestamp, sequence); break; }
    LsdDispatchReturnHook(timestamp, pc);
    LsdReturnContext current = {}; current.pc = pc;
    if (!(pc & 3) && pc >= 0x80010000 && pc < 0x80200000 &&
        (lsd_sdk_depth || lsd_sdk_windows[(pc - 0x80000000) >> 2])) {
        current.ram = LsdDispatchRead(pc); current.fetch = current.ram; current.flags = 1;
        if (CPU->PeekCheckICache(pc, &current.fetch)) current.flags |= 2;
        current.rs = CPU->GetRegister((current.fetch >> 21) & 31, NULL, 0); current.sp = sp;
        current.sr = CPU->GetRegister(PS_CPU::GSREG_SR, NULL, 0);
    }
    lsd_sdk_before_previous = lsd_sdk_previous; lsd_sdk_previous = current;
}
ECL_EXPORT int LsdResetSdkReads() {
    lsd_sdk_target_count = lsd_sdk_count = lsd_sdk_total = lsd_sdk_entries = 0;
    lsd_sdk_depth = lsd_sdk_max_depth = lsd_sdk_overflow = lsd_sdk_mismatches = lsd_sdk_data_bytes = 0;
    lsd_sdk_transfer = lsd_sdk_destination = lsd_sdk_sectors = lsd_sdk_mode = 0;
    lsd_sdk_completions = lsd_sdk_failures = lsd_sdk_unassociated = lsd_sdk_overlaps = 0;
    lsd_sdk_previous = {}; lsd_sdk_before_previous = {};
    memset(lsd_sdk_windows, 0, sizeof(lsd_sdk_windows)); return 1;
}
ECL_EXPORT int LsdAddSdkReadTarget(uint32_t pc, uint32_t bytes, uint32_t kind) {
    if (lsd_sdk_target_count == 16 || (pc & 3) || pc < 0x80010000 || pc >= 0x80200000 ||
        !bytes || (bytes & 3) || bytes > 4096 || bytes > 0x80200000 - pc || kind < 1 || kind > 10) return 0;
    for (unsigned i = 0; i < lsd_sdk_target_count; ++i) if (pc == lsd_sdk_targets[i].pc) return 0;
    lsd_sdk_targets[lsd_sdk_target_count++] = {pc, bytes, kind};
    for (uint32_t at = pc; at < pc + bytes; at += 4) lsd_sdk_windows[(at - 0x80000000) >> 2] = 1;
    // Retain actual preceding JAL/delay contexts for every static caller in RAM.
    // This scan does not execute guest instructions or populate its instruction cache.
    for (uint32_t at = 0x80010000; at < 0x801FFFFC; at += 4) {
        uint32_t instruction = LsdDispatchRead(at);
        const uint32_t op = instruction >> 26;
        const bool indirect = !op && ((instruction & 63) == 8 || (instruction & 63) == 9);
        if (indirect || ((op == 2 || op == 3) && ((instruction & 0x03FFFFFF) << 2 | 0x80000000) == pc)) {
            lsd_sdk_windows[(at - 0x80000000) >> 2] = 1;
            lsd_sdk_windows[(at + 4 - 0x80000000) >> 2] = 1;
        }
    }
    return 1;
}
ECL_EXPORT int LsdStartSdkReads() {
    if (!CPU || !lsd_sdk_target_count || !lsd_return_request_pc) return 0;
    CPU->SetCPUHook(LsdSdkReadHook, NULL); return 1;
}
ECL_EXPORT void LsdBeginSdkReadFrame() { lsd_sdk_count = lsd_sdk_data_bytes = 0; }
ECL_EXPORT uint32_t LsdGetSdkReadCount() { return lsd_sdk_count; }
ECL_EXPORT uint32_t LsdGetSdkReadTotal() { return lsd_sdk_total; }
ECL_EXPORT uint32_t LsdGetSdkReadEntries() { return lsd_sdk_entries; }
ECL_EXPORT uint32_t LsdGetSdkReadOverflow() { return lsd_sdk_overflow; }
ECL_EXPORT uint32_t LsdGetSdkReadPending() { return lsd_sdk_depth; }
ECL_EXPORT uint32_t LsdGetSdkReadMaxDepth() { return lsd_sdk_max_depth; }
ECL_EXPORT uint32_t LsdGetSdkReadTransfer() { return lsd_sdk_transfer; }
ECL_EXPORT uint32_t LsdGetSdkReadCompletions() { return lsd_sdk_completions; }
ECL_EXPORT uint32_t LsdGetSdkReadFailures() { return lsd_sdk_failures; }
ECL_EXPORT uint32_t LsdGetSdkReadUnassociated() { return lsd_sdk_unassociated; }
ECL_EXPORT uint32_t LsdGetSdkReadOverlaps() { return lsd_sdk_overlaps; }
ECL_EXPORT const LsdSdkReadEvent* LsdGetSdkReadEvents() { return lsd_sdk_events; }
ECL_EXPORT const uint8_t* LsdGetSdkReadData() { return lsd_sdk_data; }
ECL_EXPORT uint32_t LsdGetSdkReadDataBytes() { return lsd_sdk_data_bytes; }
#endif
