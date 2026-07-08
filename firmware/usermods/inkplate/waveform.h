// Waveform LUT generation, generalized over pixel bit-depth (1/2/4 bpp -- 3-bit grayscale is
// stored as 4bpp per Phase 5's framebuf-reuse decision, so 4 is the real ceiling, not 3).
// Ports boards/inkplate10/inkplateGS.py's _gen_wave/genlut (and inkplateMono.py's _gen_luts,
// same underlying scheme) to one bit-depth-agnostic code path.
#ifndef INKPLATE_WAVEFORM_H
#define INKPLATE_WAVEFORM_H

#include <stdint.h>

// gen_nibble_lut packs a nibble's worth of pixels (4/bpp pixels) into one byte of 2-bit
// waveform codes, for every possible nibble value 0x0-0xF.
//
// op[pixel_value] -> 2-bit code (0=discharge,1=black,2=white,3=skip), op must have
// 2^bpp entries. bpp must be 1, 2, or 4 (4 bits per nibble must divide evenly by bpp).
//
// out[16] receives, per nibble, the pixels packed 2-bits-per-pixel low-to-high -- for bpp=2
// this is exactly genlut()'s `op[j] | op[i] << 2`; for bpp=1 it's the per-bit pack in
// inkplateMono.py's _gen_luts loop. out[nibble] can be combined with a sibling nibble's
// result (bpp<4) and looked up in byte2gpio, or (bpp=4, one pixel per nibble) looked up
// directly after combining with another nibble the same way.
void inkplate_gen_nibble_lut(const uint8_t *op, int bpp, uint8_t out[16]);

// gen_wave_2bit reproduces InkplateGS2._gen_wave: one 16-entry nibble LUT per phase row of a
// 4-level (bpp=2) waveform table. `table` holds `phases` rows of `row_stride` codes each (only
// the first 4 codes per row are used -- board_config_t's waveform_table_t rows are padded to
// MAX_WAVE_LEVELS, this function doesn't need to know that, just the stride). out must point
// to `phases` arrays of 16 bytes each (i.e. out[phases][16]).
void inkplate_gen_wave_2bit(const uint8_t *table, int row_stride, uint8_t phases,
                            uint8_t out[][16]);

// Mono (1bpp) display waveform: 5 "push toward black" phases (white pixels skip, black
// pixels discharge) then 1 "final black/white" phase. Board-independent -- unlike
// gen_wave_2bit's per-board WAVE_2B table, this is fixed op-code math transcribed from
// boards/inkplate10/inkplateMono.py's _gen_luts (lut_blk x5, lut_bw x1), confirmed the
// same regardless of panel (docs/REFACTOR-PLAN.md step 11).
#define INKPLATE_MONO_WAVE_PHASES 6
void inkplate_gen_mono_wave(uint8_t out[INKPLATE_MONO_WAVE_PHASES][16]);

#endif // INKPLATE_WAVEFORM_H
