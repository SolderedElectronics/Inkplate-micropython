/**
 * @file epd_partial_lut.c
 * @brief Mono partial-update diff LUT generation.
 */
#include "epd_partial_lut.h"

// Transcribed from the display controller's own lookup tables.
static const uint8_t LUTW[16] = {0xFF, 0xFE, 0xFB, 0xFA, 0xEF, 0xEE, 0xEB, 0xEA,
                                 0xBF, 0xBE, 0xBB, 0xBA, 0xAF, 0xAE, 0xAB, 0xAA};
static const uint8_t LUTB[16] = {0xFF, 0xFD, 0xF7, 0xF5, 0xDF, 0xDD, 0xD7, 0xD5,
                                 0x7F, 0x7D, 0x77, 0x75, 0x5F, 0x5D, 0x57, 0x55};

void inkplate_gen_partial_diff_lut(uint8_t out[256])
{
    for (int old_n = 0; old_n < 16; old_n++) {
        for (int new_n = 0; new_n < 16; new_n++) {
            uint8_t diffw = (uint8_t)(old_n & ~new_n & 0xF);
            uint8_t diffb = (uint8_t)(~old_n & new_n & 0xF);
            out[(old_n << 4) | new_n] = LUTW[diffw] & LUTB[diffb];
        }
    }
}
