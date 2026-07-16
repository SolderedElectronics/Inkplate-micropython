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

// gen_wave_3bit: one 16-entry nibble LUT per phase row of an 8-level (bpp=4, one pixel per
// nibble) waveform table -- the real Inkplate10 3-bit engine (docs/REFACTOR-PLAN.md Phase 5
// step 15), superseding the interim 2-bit/4-level path. `table` holds `phases` rows of
// `row_stride` codes each (only the first 8 codes per row are real gray levels --
// board_config_t's waveform_table_t rows are padded to MAX_WAVE_LEVELS, this function
// doesn't need to know that, just the stride). Entries 8-15 of each generated LUT are
// unused padding (GS4_HMSB pixel values are always 0-7) -- inkplate_gen_nibble_lut(bpp=4)
// still needs a full 16-entry op array per phase, since it maps a full nibble, not a
// sub-nibble field. out must point to `phases` arrays of 16 bytes each (out[phases][16]).
void inkplate_gen_wave_3bit(const uint8_t *table, int row_stride, uint8_t phases,
                            uint8_t out[][16]);

// Mono (1bpp) display waveform: black_phases "push toward black" phases (white pixels
// skip, black pixels discharge) then 1 "final black/white" phase. The op-code math itself
// (lut_blk/lut_bw) is fixed, transcribed from boards/inkplate10/inkplateMono.py's
// _gen_luts, confirmed the same regardless of panel (docs/REFACTOR-PLAN.md step 11) --
// but black_phases is NOT: every wired board's Arduino reference driver uses 5 except
// Inkplate6FLICK's display1b(), which uses 4 (then does its own separate discharge pass,
// pushed from Python via i2s_push_frame(0)/clean(2,...) -- see docs/REFACTOR-PLAN.md
// Phase 8 step 24), and Inkplate4TEMPERA's, which uses 10 (its own GraphicsDefs.h
// LUTB/LUT2 confirmed byte-identical to the standard op_blk/op_bw scheme despite the
// unusually high count -- see docs/REFACTOR-PLAN.md Phase 8 step 26). out must have room
// for black_phases+1 rows of 16 bytes each.
#define INKPLATE_MONO_WAVE_MAX_PHASES 11
void inkplate_gen_mono_wave(uint8_t black_phases, uint8_t out[][16]);

// Mono (1bpp) display waveform, reversed-role variant: `repeat_phases` "push toward white"
// phases (white pixels pushed white, black pixels skip) then 1 final "push toward black"
// phase (black pixels pushed black, white pixels skip) -- the mirror image of
// inkplate_gen_mono_wave's phase roles. Required for Inkplate6PLUSV2: decoding its real
// Arduino reference driver's display1b() (LUTW/LUTB from its own GraphicsDefs.h, indexed
// via ~dram for the repeated loop and dram for the final loop) gives exactly this shape,
// not inkplate_gen_mono_wave's -- HIL-confirmed on real hardware (inkplate_gen_mono_wave
// produced a uniformly dark/washed panel: background only ever got one white push,
// regardless of black_phases count, since white pixels are skipped in every repeated
// phase under that scheme). out must have room for repeat_phases+1 rows of 16 bytes each.
void inkplate_gen_mono_wave_white_first(uint8_t repeat_phases, uint8_t out[][16]);

#endif // INKPLATE_WAVEFORM_H
