#include <array>
#include <cstdio>
#include <cstring>
#include <new>
#include <string>
#include <utility>
#include <vector>

struct MediaType {
    std::string Name;
};

static_assert(sizeof(MediaType) == 24, "Require the observed 24-byte libc++ ABI");
static_assert(alignof(MediaType) <= 16, "Check object alignment inside the guards");

static void print_hex(const unsigned char *data, std::size_t bytes) {
    for (std::size_t index = 0; index < bytes; ++index) std::printf("%02x", data[index]);
}

int main() {
    const unsigned seeds[] = {0, 0x17, 0x5a, 0xa5, 0xff};
    for (unsigned mode = 0; mode < 3; ++mode) {
        for (unsigned seed : seeds) {
            alignas(MediaType) unsigned char guarded[16 + sizeof(MediaType) + 16];
            std::memset(guarded, seed, sizeof(guarded));
            auto *storage = guarded + 16;
            MediaType *value;
            if (mode == 0) {
                value = new (storage) MediaType{"CD"};
            } else {
                value = new (storage) MediaType{};
                if (mode == 2) value->Name.resize(value->Name.capacity(), '\0');
                value->Name = "CD";
            }
            std::array<unsigned char, sizeof(MediaType)> before;
            std::memcpy(before.data(), value, before.size());
            std::vector<MediaType> media;
            media.push_back(std::move(*value));
            std::array<unsigned char, sizeof(MediaType)> after;
            std::memcpy(after.data(), &media[0], after.size());
            bool guards_unchanged = true;
            for (std::size_t index = 0; index < 16; ++index) {
                guards_unchanged &= guarded[index] == seed;
                guards_unchanged &= guarded[16 + sizeof(MediaType) + index] == seed;
            }
            std::printf("{\"mode\":%u,\"seed\":%u,\"length\":%zu,\"capacity\":%zu,"
                        "\"logical_name_equal\":%s,\"guards_unchanged\":%s,\"before\":\"",
                        mode, seed, media[0].Name.size(), media[0].Name.capacity(),
                        media[0].Name == "CD" ? "true" : "false", guards_unchanged ? "true" : "false");
            print_hex(before.data(), before.size());
            std::printf("\",\"after\":\"");
            print_hex(after.data(), after.size());
            std::printf("\"}\n");
            value->~MediaType();
        }
    }
}
