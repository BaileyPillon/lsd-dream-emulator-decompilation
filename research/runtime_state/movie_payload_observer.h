// Optional movie analysis. No guest RAM, instructions or CPU source is written.
#ifndef LSD_MOVIE_PAYLOAD_OBSERVER_H
#define LSD_MOVIE_PAYLOAD_OBSERVER_H
#include "dispatch_entry_observer.h"

struct LsdMoviePayloadEvent {
    uint32_t frame, ordinal, kind, pc, timestamp, sp, ra;
    uint32_t entry_frame, entry_timestamp, entry_sp, entry_ra;
    uint32_t a0, a1, a2, a3;
    uint32_t transfer_pc, delay_pc, transfer_word, delay_word;
    uint32_t return_jump_pc, return_delay_pc, return_jump_word, return_delay_word;
    uint32_t source_address, source_bytes, data_offset, command_word;
    uint32_t input_address, output_address, frame_id, header_address, header_words[8];
    uint32_t status, active_movie, v0, v1;
};
static_assert(sizeof(LsdMoviePayloadEvent) == 172, "Movie payload event layout");
static LsdMoviePayloadEvent lsd_movie_events[16], lsd_movie_callback, lsd_movie_vlc, lsd_movie_buffers[2];
static uint8_t lsd_movie_data[1024 * 1024];
static uint32_t lsd_movie_count, lsd_movie_total, lsd_movie_data_bytes, lsd_movie_errors, lsd_movie_overflow;
static uint32_t lsd_movie_callbacks, lsd_movie_kind_counts[3], lsd_movie_return_seen;
static bool lsd_movie_callback_pending, lsd_movie_vlc_pending, lsd_movie_buffer_pending[2];

static bool LsdMovieReadable(uint32_t address, uint32_t bytes) {
    return !(address & 3) && address >= 0x80010000 && address < 0x80200000 && bytes <= 0x80200000 - address;
}
static LsdMoviePayloadEvent LsdMovieContext(uint32_t pc, pscpu_timestamp_t timestamp) {
    LsdMoviePayloadEvent e = {};
    e.frame = e.entry_frame = lsd_dispatch_frame; e.pc = pc;
    e.timestamp = e.entry_timestamp = (uint32_t)timestamp;
    e.sp = e.entry_sp = CPU->GetRegister(29, NULL, 0);
    e.ra = e.entry_ra = CPU->GetRegister(31, NULL, 0);
    e.a0 = CPU->GetRegister(4, NULL, 0); e.a1 = CPU->GetRegister(5, NULL, 0);
    e.a2 = CPU->GetRegister(6, NULL, 0); e.a3 = CPU->GetRegister(7, NULL, 0);
    e.transfer_pc = lsd_dispatch_before_previous; e.delay_pc = lsd_dispatch_previous;
    e.transfer_word = LsdDispatchRead(e.transfer_pc); e.delay_word = LsdDispatchRead(e.delay_pc);
    e.active_movie = LsdDispatchRead(0x8008a940);
    e.v0 = CPU->GetRegister(2, NULL, 0); e.v1 = CPU->GetRegister(3, NULL, 0);
    return e;
}
static void LsdMoviePush(LsdMoviePayloadEvent e, uint32_t address, uint32_t bytes) {
    e.ordinal = ++lsd_movie_total; e.source_address = address; e.source_bytes = bytes;
    e.command_word = LsdDispatchRead(address); e.data_offset = lsd_movie_data_bytes;
    if (e.status || !bytes || bytes > 0x40000 || !LsdMovieReadable(address, bytes)) {
        if (!e.status) e.status = 1;
        ++lsd_movie_errors;
    } else if (bytes > sizeof(lsd_movie_data) - lsd_movie_data_bytes) {
        e.status = 2; ++lsd_movie_errors; ++lsd_movie_overflow;
    } else {
        e.status = 0;
        memcpy(lsd_movie_data + lsd_movie_data_bytes, MainRAM.data8 + (address & 0x1fffffff), bytes);
        lsd_movie_data_bytes += bytes;
    }
    if (e.kind >= 1 && e.kind <= 3) ++lsd_movie_kind_counts[e.kind - 1];
    if (lsd_movie_count == 16) { ++lsd_movie_overflow; return; }
    lsd_movie_events[lsd_movie_count++] = e;
}
static void LsdMovieHeader(LsdMoviePayloadEvent& e, const LsdMoviePayloadEvent& source) {
    e.input_address = source.input_address; e.output_address = source.output_address;
    e.frame_id = source.frame_id; e.header_address = source.header_address;
    memcpy(e.header_words, source.header_words, sizeof(e.header_words));
}
static void LsdMovieCallback(uint32_t pc, pscpu_timestamp_t timestamp) {
    LsdMoviePayloadEvent e = LsdMovieContext(pc, timestamp);
    if (lsd_movie_callback_pending) ++lsd_movie_errors;
    const uint32_t base = LsdDispatchRead(0x80090b8c), next = LsdDispatchRead(0x8009025c);
    const uint32_t data = LsdDispatchRead(0x80090c5c);
    const uint64_t header = (uint64_t)base + next * 32ULL;
    const uint64_t ring = (uint64_t)base + data * 32ULL + next * 2016ULL;
    e.frame_id = e.a2; e.input_address = e.a1; e.header_address = (uint32_t)header;
    if (next >= 1024 || header > 0xffffffff || ring > 0xffffffff ||
        !LsdMovieReadable(e.header_address, 32) || e.a1 != (uint32_t)ring) e.status = 3;
    else {
        for (unsigned i = 0; i < 8; ++i) e.header_words[i] = LsdDispatchRead(e.header_address + 4 * i);
        const uint32_t size = e.header_words[3];
        if (e.header_words[2] != e.frame_id || !e.frame_id || size < 8 || size > 0x12000 || (size & 3) ||
            !LsdMovieReadable(e.input_address, size)) e.status = 4;
    }
    lsd_movie_callback = e; lsd_movie_callback_pending = true; ++lsd_movie_callbacks;
}
static void LsdMovieVlcEntry(uint32_t pc, pscpu_timestamp_t timestamp) {
    LsdMoviePayloadEvent e = LsdMovieContext(pc, timestamp);
    e.kind = 1; LsdMovieHeader(e, lsd_movie_callback); e.output_address = e.a1;
    if (!lsd_movie_callback_pending || lsd_movie_vlc_pending || lsd_movie_callback.status ||
        e.a0 != e.input_address || e.a2 != e.frame_id) e.status = 5;
    lsd_movie_callback_pending = false; lsd_movie_vlc_pending = true; lsd_movie_return_seen = 0;
    lsd_movie_vlc = e; LsdMoviePush(e, e.input_address, e.header_words[3]);
}
static void LsdMovieVlcReturn(uint32_t pc, pscpu_timestamp_t timestamp) {
    LsdMoviePayloadEvent e = lsd_movie_vlc; e.kind = 2;
    e.frame = lsd_dispatch_frame; e.pc = pc; e.timestamp = (uint32_t)timestamp;
    e.sp = CPU->GetRegister(29, NULL, 0); e.ra = CPU->GetRegister(31, NULL, 0);
    e.v0 = CPU->GetRegister(2, NULL, 0); e.v1 = CPU->GetRegister(3, NULL, 0);
    if (lsd_movie_return_seen != 3) e.status = 6;
    const uint32_t word = LsdDispatchRead(e.output_address), bytes = 4 + (word & 0xffff) * 4;
    if ((word >> 16) != 0x3800 || word != e.header_words[5] || bytes <= 4) e.status = 7;
    LsdMoviePush(e, e.output_address, bytes);
    unsigned slot = 0;
    if (lsd_movie_buffers[0].output_address != e.output_address && lsd_movie_buffers[0].output_address) slot = 1;
    if ((lsd_movie_buffers[slot].output_address && lsd_movie_buffers[slot].output_address != e.output_address) ||
        lsd_movie_buffer_pending[slot]) ++lsd_movie_errors;
    lsd_movie_buffers[slot] = e; lsd_movie_buffer_pending[slot] = true; lsd_movie_vlc_pending = false;
}
static void LsdMovieMdecEntry(uint32_t pc, pscpu_timestamp_t timestamp) {
    LsdMoviePayloadEvent e = LsdMovieContext(pc, timestamp); e.kind = 3;
    unsigned slot = lsd_movie_buffers[0].output_address == e.a0 ? 0 : 1;
    LsdMovieHeader(e, lsd_movie_buffers[slot]);
    if (e.a1 != 2 || lsd_movie_buffers[slot].output_address != e.a0 || !lsd_movie_buffer_pending[slot]) e.status = 8;
    const uint32_t word = LsdDispatchRead(e.a0), bytes = 4 + (word & 0xffff) * 4;
    if ((word >> 16) != 0x3800 || word != e.header_words[5] || bytes <= 4) e.status = 9;
    LsdMoviePush(e, e.a0, bytes); lsd_movie_buffer_pending[slot] = false;
}
static void LsdMoviePayloadHook(const pscpu_timestamp_t timestamp, uint32_t pc) {
    if (lsd_movie_vlc_pending) {
        const uint32_t sp = CPU->GetRegister(29, NULL, 0), ra = CPU->GetRegister(31, NULL, 0);
        if (pc == 0x800465b0 && sp == lsd_movie_vlc.entry_sp && ra == lsd_movie_vlc.entry_ra) {
            lsd_movie_vlc.return_jump_pc = pc; lsd_movie_vlc.return_jump_word = LsdDispatchRead(pc);
            if (lsd_movie_vlc.return_jump_word == 0x03e00008) lsd_movie_return_seen |= 1;
        }
        if (pc == 0x800465b4 && (lsd_movie_return_seen & 1) && sp == lsd_movie_vlc.entry_sp && ra == lsd_movie_vlc.entry_ra) {
            lsd_movie_vlc.return_delay_pc = pc; lsd_movie_vlc.return_delay_word = LsdDispatchRead(pc);
            if (lsd_movie_vlc.return_delay_word == 0) lsd_movie_return_seen |= 2;
        }
        if (pc == lsd_movie_vlc.entry_ra && sp == lsd_movie_vlc.entry_sp) LsdMovieVlcReturn(pc, timestamp);
    }
    if (pc == 0x800477b0) LsdMovieCallback(pc, timestamp);
    else if (pc == 0x80046568) LsdMovieVlcEntry(pc, timestamp);
    else if (pc == 0x80045f84) LsdMovieMdecEntry(pc, timestamp);
    LsdDispatchCpuEntry(timestamp, pc);
}
ECL_EXPORT int LsdStartMoviePayloadTrace() {
    if (!CPU || lsd_dispatch_target_count != 3 || !lsd_dispatch_words_configured) return 0;
    lsd_movie_count = lsd_movie_total = lsd_movie_data_bytes = lsd_movie_errors = lsd_movie_overflow = 0;
    lsd_movie_callbacks = lsd_movie_return_seen = 0;
    memset(lsd_movie_kind_counts, 0, sizeof(lsd_movie_kind_counts));
    memset(lsd_movie_buffers, 0, sizeof(lsd_movie_buffers));
    memset(lsd_movie_buffer_pending, 0, sizeof(lsd_movie_buffer_pending));
    lsd_movie_callback_pending = lsd_movie_vlc_pending = false;
    CPU->SetCPUHook(LsdMoviePayloadHook, NULL); return 1;
}
ECL_EXPORT void LsdBeginMoviePayloadFrame(uint32_t frame) {
    LsdBeginDispatchFrame(frame); lsd_movie_count = lsd_movie_data_bytes = 0;
}
ECL_EXPORT uint32_t LsdGetMoviePayloadCount() { return lsd_movie_count; }
ECL_EXPORT uint32_t LsdGetMoviePayloadTotal() { return lsd_movie_total; }
ECL_EXPORT uint32_t LsdGetMoviePayloadErrors() { return lsd_movie_errors; }
ECL_EXPORT uint32_t LsdGetMoviePayloadOverflow() { return lsd_movie_overflow; }
ECL_EXPORT uint32_t LsdGetMoviePayloadDataBytes() { return lsd_movie_data_bytes; }
ECL_EXPORT const LsdMoviePayloadEvent* LsdGetMoviePayloadEvents() { return lsd_movie_events; }
ECL_EXPORT const uint8_t* LsdGetMoviePayloadData() { return lsd_movie_data; }
ECL_EXPORT uint32_t LsdGetMoviePayloadCallbacks() { return lsd_movie_callbacks; }
ECL_EXPORT uint32_t LsdGetMoviePayloadPendingVlc() { return lsd_movie_vlc_pending ? 1 : 0; }
ECL_EXPORT uint32_t LsdGetMoviePayloadPendingBuffers() {
    return (lsd_movie_buffer_pending[0] ? 1 : 0) + (lsd_movie_buffer_pending[1] ? 1 : 0);
}
#endif
