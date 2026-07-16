// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_epd_partial_lut.c ../epd_partial_lut.c -o test_epd_partial_lut \
//              && ./test_epd_partial_lut
#include <assert.h>
#include <stdio.h>

#include "../display/epd_partial_lut.h"

// Independent transcription of the Arduino reference driver's GraphicsDefs.h tables (not
// a call into production code) plus the diffw/diffb formula, used to cross-check
// inkplate_gen_partial_diff_lut()'s output byte-for-byte.
static const uint8_t LUTW[16] = {0xFF, 0xFE, 0xFB, 0xFA, 0xEF, 0xEE, 0xEB, 0xEA,
                                 0xBF, 0xBE, 0xBB, 0xBA, 0xAF, 0xAE, 0xAB, 0xAA};
static const uint8_t LUTB[16] = {0xFF, 0xFD, 0xF7, 0xF5, 0xDF, 0xDD, 0xD7, 0xD5,
                                 0x7F, 0x7D, 0x77, 0x75, 0x5F, 0x5D, 0x57, 0x55};

static uint8_t expected_entry(int old_n, int new_n)
{
    uint8_t diffw = (uint8_t)(old_n & ~new_n & 0xF);
    uint8_t diffb = (uint8_t)(~old_n & new_n & 0xF);
    return (uint8_t)(LUTW[diffw] & LUTB[diffb]);
}

int main(void)
{
    uint8_t lut[256];
    inkplate_gen_partial_diff_lut(lut);

    for (int old_n = 0; old_n < 16; old_n++) {
        for (int new_n = 0; new_n < 16; new_n++) {
            assert(lut[(old_n << 4) | new_n] == expected_entry(old_n, new_n));
        }
    }

    // Hand-derived sanity cases (docs/REFACTOR-PLAN.md step 16 trace):
    // unchanged nibble (any value) -> all 4 pixels skip(3) = 0xFF, regardless of color.
    assert(lut[(0x0 << 4) | 0x0] == 0xFF);
    assert(lut[(0xF << 4) | 0xF] == 0xFF);
    assert(lut[(0x5 << 4) | 0x5] == 0xFF);
    // all-white -> all-black (old=0000, new=1111): every pixel pushed toward black(1).
    assert(lut[(0x0 << 4) | 0xF] == 0x55);
    // all-black -> all-white (old=1111, new=0000): every pixel pushed toward white(2).
    assert(lut[(0xF << 4) | 0x0] == 0xAA);

    printf("epd_partial_lut: all assertions passed\n");
    return 0;
}
