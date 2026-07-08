// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_waveform.c ../waveform.c ../board_config.c -o test_waveform &&
// ./test_waveform
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../board_config.h"
#include "../waveform.h"

// Reference values below were cross-checked by running the actual genlut()/WAVE_2B from
// boards/inkplate10/inkplateGS.py in Python, not hand-derived, so this catches drift between
// the C port and the real driver, not just internal self-consistency.

static void test_synthetic_nibble_lut(void)
{
    // Hand-computed: op[v] = v (identity), bpp = 2 -> out[n] = op[n&3] | op[(n>>2)&3]<<2
    // reduces to out[n] == n for every nibble.
    uint8_t identity_op[4] = {0, 1, 2, 3};
    uint8_t out[16];
    inkplate_gen_nibble_lut(identity_op, 2, out);
    for (int n = 0; n < 16; n++) {
        assert(out[n] == n);
    }

    // Hand-computed: op = {3, 2, 1, 0} (reversed), bpp = 2.
    // out[n] = op[n&3] | op[(n>>2)&3]<<2 = (3-(n&3)) | (3-(n>>2&3))<<2
    uint8_t reversed_op[4] = {3, 2, 1, 0};
    uint8_t expected_reversed[16] = {15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0};
    inkplate_gen_nibble_lut(reversed_op, 2, out);
    assert(memcmp(out, expected_reversed, 16) == 0);

    // bpp = 1, 4 pixels/nibble: op = {2, 3} matches inkplateMono.py's lut_wht scheme
    // (bit clear -> code 2/white, bit set -> code 3/skip). Hand-computed for nibble 0b1010
    // (bits, LSB-first p=0..3: 0,1,0,1): code = op[0]|op[1]<<2|op[0]<<4|op[1]<<6 = 2|3<<2|2<<4|3<<6.
    uint8_t wht_op[2] = {2, 3};
    inkplate_gen_nibble_lut(wht_op, 1, out);
    uint8_t expected_n10 = (uint8_t)(2 | 3 << 2 | 2 << 4 | 3 << 6);
    assert(out[0b1010] == expected_n10);

    printf("test_synthetic_nibble_lut: passed\n");
}

static void test_legacy_2bit_parity(void)
{
    // Reference _wave from `python3 -c` running the real genlut()/WAVE_2B in
    // boards/inkplate10/inkplateGS.py verbatim.
    static const uint8_t expected_wave[8][16] = {
        {0, 1, 0, 0, 4, 5, 4, 4, 0, 1, 0, 0, 0, 1, 0, 0},
        {0, 2, 0, 0, 8, 10, 8, 8, 0, 2, 0, 0, 0, 2, 0, 0},
        {0, 2, 0, 2, 8, 10, 8, 10, 0, 2, 0, 2, 8, 10, 8, 10},
        {0, 1, 2, 2, 4, 5, 6, 6, 8, 9, 10, 10, 8, 9, 10, 10},
        {0, 2, 1, 2, 8, 10, 9, 10, 4, 6, 5, 6, 8, 10, 9, 10},
        {0, 2, 1, 2, 8, 10, 9, 10, 4, 6, 5, 6, 8, 10, 9, 10},
        {5, 5, 6, 6, 5, 5, 6, 6, 9, 9, 10, 10, 9, 9, 10, 10},
        {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    };

    const board_config_t *cfg = &board_config_inkplate10;
    assert(cfg->waveform->phases == 8);

    uint8_t wave[8][16];
    inkplate_gen_wave_2bit(&cfg->waveform->table[0][0], MAX_WAVE_LEVELS, cfg->waveform->phases,
                           wave);

    assert(memcmp(wave, expected_wave, sizeof(wave)) == 0);

    printf("test_legacy_2bit_parity: passed\n");
}

int main(void)
{
    test_synthetic_nibble_lut();
    test_legacy_2bit_parity();
    printf("test_waveform: all assertions passed\n");
    return 0;
}
