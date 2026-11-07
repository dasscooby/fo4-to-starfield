// Python-compatible random numbers for the FOCCSim core: CPython's random.Random (MT19937) as seeded with an integer,
// and the three draws the simulation makes: random(), getrandbits(k <= 32) and choice() through _randbelow.
// docs/combined-core-cpp-port.md section 3 ("RNG"): std::mt19937 seeds differently, so the generator is our own.
//
// CPython (Modules/_randommodule.c): seed(n) takes |n| as little-endian 32-bit words, at least one, and runs
// init_by_array over them; random() = (a >> 5) * 67108864 + (b >> 6), over 2^53; getrandbits(k) for k <= 32 is
// genrand_uint32() >> (32 - k); _randbelow(n) draws getrandbits(n.bit_length()) until the result is below n.
#pragma once

#include <cstdint>
#include <stdexcept>
#include <vector>

namespace foccsim {

class PyRandom {
public:
    explicit PyRandom(std::uint64_t seed) {
        std::vector<std::uint32_t> key;
        key.push_back(static_cast<std::uint32_t>(seed & 0xffffffffu));
        if (seed >> 32) key.push_back(static_cast<std::uint32_t>(seed >> 32));
        init_by_array(key);
    }

    double random() {
        std::uint32_t a = next() >> 5, b = next() >> 6;
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    }

    std::uint32_t getrandbits(int k) {
        if (k <= 0) return 0;
        if (k > 32) throw std::logic_error("getrandbits over 32 bits is not used by the simulation");
        return next() >> (32 - k);
    }

    // random.Random._randbelow_with_getrandbits
    std::uint64_t randbelow(std::uint64_t n) {
        if (n == 0) throw std::logic_error("randbelow(0)");
        int k = 0;
        for (std::uint64_t m = n; m; m >>= 1) ++k;
        std::uint64_t r = getrandbits(k);
        while (r >= n) r = getrandbits(k);
        return r;
    }

private:
    static constexpr int N = 624, M = 397;
    std::uint32_t mt_[N];
    int mti_ = N + 1;

    void init_genrand(std::uint32_t s) {
        mt_[0] = s;
        for (mti_ = 1; mti_ < N; ++mti_)
            mt_[mti_] = 1812433253u * (mt_[mti_ - 1] ^ (mt_[mti_ - 1] >> 30)) + static_cast<std::uint32_t>(mti_);
    }

    void init_by_array(const std::vector<std::uint32_t>& key) {
        init_genrand(19650218u);
        std::size_t i = 1, j = 0, len = key.size();
        for (std::size_t k = (N > len ? N : len); k; --k) {
            mt_[i] = (mt_[i] ^ ((mt_[i - 1] ^ (mt_[i - 1] >> 30)) * 1664525u)) + key[j] + static_cast<std::uint32_t>(j);
            ++i;
            ++j;
            if (i >= N) { mt_[0] = mt_[N - 1]; i = 1; }
            if (j >= len) j = 0;
        }
        for (std::size_t k = N - 1; k; --k) {
            mt_[i] = (mt_[i] ^ ((mt_[i - 1] ^ (mt_[i - 1] >> 30)) * 1566083941u)) - static_cast<std::uint32_t>(i);
            ++i;
            if (i >= N) { mt_[0] = mt_[N - 1]; i = 1; }
        }
        mt_[0] = 0x80000000u;
    }

    std::uint32_t next() {
        static const std::uint32_t mag01[2] = {0u, 0x9908b0dfu};
        std::uint32_t y;
        if (mti_ >= N) {
            int kk = 0;
            for (; kk < N - M; ++kk) {
                y = (mt_[kk] & 0x80000000u) | (mt_[kk + 1] & 0x7fffffffu);
                mt_[kk] = mt_[kk + M] ^ (y >> 1) ^ mag01[y & 1u];
            }
            for (; kk < N - 1; ++kk) {
                y = (mt_[kk] & 0x80000000u) | (mt_[kk + 1] & 0x7fffffffu);
                mt_[kk] = mt_[kk + (M - N)] ^ (y >> 1) ^ mag01[y & 1u];
            }
            y = (mt_[N - 1] & 0x80000000u) | (mt_[0] & 0x7fffffffu);
            mt_[N - 1] = mt_[M - 1] ^ (y >> 1) ^ mag01[y & 1u];
            mti_ = 0;
        }
        y = mt_[mti_++];
        y ^= (y >> 11);
        y ^= (y << 7) & 0x9d2c5680u;
        y ^= (y << 15) & 0xefc60000u;
        y ^= (y >> 18);
        return y;
    }
};

}  // namespace foccsim
