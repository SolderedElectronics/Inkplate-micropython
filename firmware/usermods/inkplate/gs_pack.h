// Interim bridge for docs/REFACTOR-PLAN.md Phase 5 step 14: the Python-side grayscale
// framebuffer switched from GS2_HMSB (2 bits/pixel, 4 px/byte) to GS4_HMSB (4 bits/pixel,
// 2 px/byte, raw pixel values 0-7) to make room for the real 3-bit/8-level waveform table
// (step 15, blocked on per-board timing data). Until that table lands, epd_i2s.c's
// build_gs_row (HIL-verified against real hardware in step 13, including the I2S FIFO
// byte-order compensation) keeps consuming the old GS2_HMSB byte shape unchanged --
// inkplate_gs4_row_to_gs2 folds the new 8-level storage down to the old 4-level codes
// (raw >> 1) and repacks it into that exact shape, so no hardware-timing-sensitive code
// needs to be re-derived (and re-verified on real hardware) until step 15 actually wires
// the 8-level table in.
#ifndef INKPLATE_GS_PACK_H
#define INKPLATE_GS_PACK_H

#include <stdint.h>

// gs4_row: gs2_row_bytes*2 bytes, GS4_HMSB-packed (byte = pixel_even | pixel_odd << 4,
// each nibble a raw 0-7 level -- matches write_pixel_viper's packing in inkplate10.py).
// gs2_row: gs2_row_bytes bytes, receives the GS2_HMSB-shaped result (byte = p0 | p1<<2 |
// p2<<4 | p3<<6, each 2-bit field = the corresponding input raw level >> 1) that
// build_gs_row already expects.
void inkplate_gs4_row_to_gs2(const uint8_t *gs4_row, uint16_t gs2_row_bytes, uint8_t *gs2_row);

#endif // INKPLATE_GS_PACK_H
