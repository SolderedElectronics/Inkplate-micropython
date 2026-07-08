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

static void test_3bit_wave_parity(void)
{
    // Reference values cross-checked against the real Arduino reference driver's
    // waveform1[color][phase] (Inkplate10Driver.cpp / waveforms.h WAVEFORM3BIT), transposed
    // to [phase][color] via a python3 one-liner (not hand-derived) -- see board_config.c's
    // wave_3b_inkplate10 for the same transpose. bpp=4 (one pixel per nibble) makes
    // inkplate_gen_nibble_lut a direct pass-through: out[nibble] == op[nibble] for
    // nibble 0-15, so the generated LUT's first 8 entries equal the table row verbatim and
    // entries 8-15 are the zero-padding inkplate_gen_wave_3bit fills unused nibbles with.
    const board_config_t *cfg = &board_config_inkplate10;
    assert(cfg->waveform->levels == 8);
    assert(cfg->waveform->phases == 9);

    uint8_t wave[9][16];
    inkplate_gen_wave_3bit(&cfg->waveform->table[0][0], MAX_WAVE_LEVELS, cfg->waveform->phases,
                           wave);

    static const uint8_t expected_phase1[8] = {0, 0, 0, 1, 0, 2, 0, 0};
    static const uint8_t expected_phase7[8] = {1, 1, 1, 1, 1, 1, 2, 2};
    static const uint8_t expected_pad[8] = {0, 0, 0, 0, 0, 0, 0, 0};

    assert(memcmp(wave[1], expected_phase1, 8) == 0);
    assert(memcmp(wave[1] + 8, expected_pad, 8) == 0);
    assert(memcmp(wave[7], expected_phase7, 8) == 0);
    assert(memcmp(wave[7] + 8, expected_pad, 8) == 0);

    printf("test_3bit_wave_parity: passed\n");
}

static void test_mono_wave_parity(void)
{
    // Reference lut_blk/lut_bw from running boards/inkplate10/inkplateMono.py's original
    // _gen_luts() formula verbatim in python3, not hand-derived, so this catches drift
    // between the C port and the real (now-removed) Python LUT generation.
    static const uint8_t expected_blk[16] = {255, 253, 247, 245, 223, 221, 215, 213,
                                             127, 125, 119, 117, 95,  93,  87,  85};
    static const uint8_t expected_bw[16] = {170, 169, 166, 165, 154, 153, 150, 149,
                                            106, 105, 102, 101, 90,  89,  86,  85};

    uint8_t wave[INKPLATE_MONO_WAVE_PHASES][16];
    inkplate_gen_mono_wave(wave);

    for (int phase = 0; phase < INKPLATE_MONO_WAVE_PHASES - 1; phase++) {
        assert(memcmp(wave[phase], expected_blk, 16) == 0);
    }
    assert(memcmp(wave[INKPLATE_MONO_WAVE_PHASES - 1], expected_bw, 16) == 0);

    printf("test_mono_wave_parity: passed\n");
}

int main(void)
{
    test_synthetic_nibble_lut();
    test_3bit_wave_parity();
    test_mono_wave_parity();
    printf("test_waveform: all assertions passed\n");
    return 0;
}
