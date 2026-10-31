// Synthetic transport checks. This mock does not execute or accept game code.
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using pscpu_timestamp_t = int32_t;
#define ECL_EXPORT
struct Ram { uint8_t data8[2 * 1024 * 1024]; } MainRAM;
struct MockCpu {
    uint32_t r[32] = {};
    uint32_t GetRegister(unsigned n, void*, int) { return r[n]; }
    void (*hook)(pscpu_timestamp_t, uint32_t) = nullptr;
    void SetCPUHook(void (*value)(pscpu_timestamp_t, uint32_t), void*) { hook = value; }
} cpu;
MockCpu* CPU = &cpu;
#include "research/runtime_state/movie_payload_observer.h"

constexpr uint32_t BASE = 0x800c0000, INPUT = BASE + 1024, OUTPUT = 0x800d0000;
constexpr uint32_t STACK = 0x801ff000, CALLER = 0x80045b5c, COMMAND = 0x38000020;
static void word(uint32_t address, uint32_t value) {
    std::memcpy(MainRAM.data8 + (address & 0x1fffffff), &value, 4);
}
static void tick(uint32_t pc) {
    std::vector<uint8_t> before(MainRAM.data8, MainRAM.data8 + sizeof(MainRAM.data8));
    uint32_t registers[32]; std::memcpy(registers, cpu.r, sizeof(registers));
    CPU->hook(123, pc);
    assert(!std::memcmp(before.data(), MainRAM.data8, before.size()));
    assert(!std::memcmp(registers, cpu.r, sizeof(registers)));
}
static void reset() {
    std::memset(MainRAM.data8, 0, sizeof(MainRAM.data8));
    std::memset(cpu.r, 0, sizeof(cpu.r)); cpu.r[29] = STACK;
    word(0x80090b8c, BASE); word(0x8009025c, 0); word(0x80090c5c, 32);
    word(0x8008a940, 0x800b0000);
    word(BASE, 4); word(BASE + 8, 1); word(BASE + 12, 16); word(BASE + 20, COMMAND);
    word(INPUT, COMMAND); word(INPUT + 4, 0x00020001); word(INPUT + 8, 0x11223344); word(INPUT + 12, 0x55667788);
    word(0x800465b0, 0x03e00008); word(0x800465b4, 0);
    assert(LsdResetDispatchTrace() == 1);
    assert(LsdAddDispatchTarget(0x800477b0, 96) == 1);
    assert(LsdAddDispatchTarget(0x80046568, 80) == 1);
    assert(LsdAddDispatchTarget(0x80045f84, 124) == 1);
    assert(LsdConfigureDispatchWords(0x8008a940, 0x8009025c, 0x80090b8c, 0x80090c5c) == 1);
    assert(LsdStartMoviePayloadTrace() == 1); LsdBeginMoviePayloadFrame(21884);
}
static void callback() {
    cpu.r[4] = 0x800b1000; cpu.r[5] = INPUT; cpu.r[6] = 1;
    cpu.r[31] = 0x8004778c; tick(0x80047784); tick(0x80047788); tick(0x800477b0);
}
static void vlc() {
    cpu.r[4] = INPUT; cpu.r[5] = OUTPUT; cpu.r[6] = 1; cpu.r[31] = CALLER;
    tick(0x80045b54); tick(0x80045b58); tick(0x80046568);
}
static void decoded() {
    for (unsigned n = 0; n < 132; ++n) MainRAM.data8[(OUTPUT & 0x1fffffff) + n] = (uint8_t)n;
    word(OUTPUT, COMMAND);
}
static void returned() {
    decoded(); cpu.r[29] = STACK; cpu.r[31] = CALLER;
    tick(0x800465b0); tick(0x800465b4); tick(CALLER);
}
static void mdec() {
    cpu.r[4] = OUTPUT; cpu.r[5] = 2; cpu.r[31] = 0x80045d78;
    tick(0x80045d70); tick(0x80045d74); tick(0x80045f84);
}

int main(int argc, char** argv) {
    assert(argc == 2); std::string test = argv[1]; reset();
    if (test == "complete") {
        callback(); vlc(); returned(); mdec();
        assert(LsdGetMoviePayloadErrors() == 0 && LsdGetMoviePayloadTotal() == 3);
        assert(lsd_movie_events[0].source_bytes == 16 && lsd_movie_events[1].source_bytes == 132);
        assert(lsd_movie_events[2].source_bytes == 132 && lsd_movie_events[1].pc == CALLER);
        assert(lsd_movie_events[1].return_jump_pc == 0x800465b0 && lsd_movie_events[1].return_delay_word == 0);
        assert(!std::memcmp(lsd_movie_data + lsd_movie_events[0].data_offset, MainRAM.data8 + (INPUT & 0x1fffffff), 16));
        assert(!std::memcmp(lsd_movie_data + lsd_movie_events[1].data_offset, lsd_movie_data + lsd_movie_events[2].data_offset, 132));
        assert(LsdGetMoviePayloadPendingVlc() == 0 && LsdGetMoviePayloadPendingBuffers() == 0);
    } else if (test == "encoded_size") {
        word(BASE + 12, 0x12004); callback(); vlc();
        assert(LsdGetMoviePayloadErrors() > 0 && LsdGetMoviePayloadDataBytes() == 0);
    } else if (test == "header_identity") {
        word(BASE + 8, 2); callback(); vlc();
        assert(LsdGetMoviePayloadErrors() > 0 && lsd_movie_events[0].status != 0);
    } else if (test == "ring_address") {
        word(0x80090c5c, 33); callback(); vlc();
        assert(LsdGetMoviePayloadErrors() > 0 && LsdGetMoviePayloadDataBytes() == 0);
    } else if (test == "missing_callback") {
        vlc(); assert(LsdGetMoviePayloadErrors() > 0);
    } else if (test == "return_instructions") {
        callback(); vlc(); decoded(); tick(CALLER);
        assert(LsdGetMoviePayloadErrors() > 0 && lsd_movie_events[1].status == 6);
    } else if (test == "wrong_return_stack") {
        callback(); vlc(); decoded(); cpu.r[29] = STACK - 4;
        tick(0x800465b0); tick(0x800465b4); tick(CALLER);
        assert(LsdGetMoviePayloadPendingVlc() == 1 && LsdGetMoviePayloadTotal() == 1);
    } else if (test == "missing_decoded_buffer") {
        decoded(); mdec(); assert(LsdGetMoviePayloadErrors() > 0);
    } else if (test == "late_payload_difference") {
        callback(); vlc(); returned(); MainRAM.data8[(OUTPUT & 0x1fffffff) + 100] ^= 1; mdec();
        assert(LsdGetMoviePayloadErrors() == 0);
        const uint8_t* left = lsd_movie_data + lsd_movie_events[1].data_offset;
        const uint8_t* right = lsd_movie_data + lsd_movie_events[2].data_offset;
        assert(!std::memcmp(left, right, 44) && std::memcmp(left, right, 132));
    } else if (test == "cross_frame_return") {
        callback(); vlc(); LsdBeginMoviePayloadFrame(21885); returned();
        assert(LsdGetMoviePayloadErrors() == 0 && LsdGetMoviePayloadCount() == 1);
        assert(lsd_movie_events[0].entry_frame == 21884 && lsd_movie_events[0].frame == 21885);
        assert(LsdGetMoviePayloadPendingBuffers() == 1);
    } else if (test == "command_bounds") {
        callback(); vlc(); decoded(); word(OUTPUT, 0x38000000);
        tick(0x800465b0); tick(0x800465b4); tick(CALLER);
        assert(LsdGetMoviePayloadErrors() > 0 && lsd_movie_events[1].status == 7);
    } else if (test == "overflow") {
        for (unsigned n = 0; n < 20; ++n) { callback(); vlc(); returned(); mdec(); }
        assert(LsdGetMoviePayloadOverflow() > 0 && LsdGetMoviePayloadCount() == 16);
    } else return 2;
    std::cout << "passed " << test << "\n";
}
