#include "waveform.h"

void inkplate_gen_nibble_lut(const uint8_t *op, int bpp, uint8_t out[16])
{
    int pixels_per_nibble = 4 / bpp;
    uint8_t pixel_mask = (uint8_t)((1 << bpp) - 1);

    for (int nibble = 0; nibble < 16; nibble++) {
        uint8_t code_byte = 0;
        for (int p = 0; p < pixels_per_nibble; p++) {
            uint8_t pixel_val = (uint8_t)((nibble >> (p * bpp)) & pixel_mask);
            code_byte |= (uint8_t)(op[pixel_val] << (2 * p));
        }
        out[nibble] = code_byte;
    }
}

void inkplate_gen_wave_2bit(const uint8_t *table, int row_stride, uint8_t phases,
                            uint8_t out[][16])
{
    for (uint8_t phase = 0; phase < phases; phase++) {
        inkplate_gen_nibble_lut(&table[phase * row_stride], 2, out[phase]);
    }
}
