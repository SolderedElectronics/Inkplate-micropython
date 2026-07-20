/**
 * @file waveform.h
 * @brief Waveform LUT generation, generalized over pixel bit-depth (1/2/4 bpp).
 *
 * 3-bit grayscale is stored as 4bpp per the framebuffer-reuse scheme, so 4 is the real
 * ceiling, not 3. Unifies what were separate per-format LUT-generation code paths into
 * one bit-depth-agnostic path.
 */
#ifndef INKPLATE_WAVEFORM_H
#define INKPLATE_WAVEFORM_H

#include <stdint.h>

/**
 * @brief Packs a nibble's worth of pixels into one byte of 2-bit waveform codes, for every
 * possible nibble value (0x0-0xF).
 * @param op Per-pixel-value waveform op-code table (0=discharge, 1=black, 2=white, 3=skip);
 * must have 2^bpp entries.
 * @param bpp Bits per pixel; must be 1, 2, or 4 so 4 bits per nibble divides evenly.
 * @param out Receives, per nibble, the pixels packed 2-bits-per-pixel low-to-high; combine
 * with a sibling nibble's result and look up in byte2gpio (or, for bpp=4, look up directly
 * after combining with another nibble the same way).
 */
void inkplate_gen_nibble_lut(const uint8_t *op, int bpp, uint8_t out[16]);

/**
 * @brief Builds one 16-entry nibble LUT per phase row of an 8-level (bpp=4, one pixel per
 * nibble) grayscale waveform table.
 * @param table Waveform table; `phases` rows of `row_stride` codes each. Only the first 8
 * codes per row are real gray levels (rows are padded to MAX_WAVE_LEVELS).
 * @param row_stride Number of codes per row in `table`.
 * @param phases Number of phase rows to generate.
 * @param out Receives `phases` arrays of 16 bytes each; entries 8-15 of each are unused
 * padding since GS4_HMSB pixel values are always 0-7.
 */
void inkplate_gen_wave_3bit(const uint8_t *table, int row_stride, uint8_t phases,
                            uint8_t out[][16]);

#define INKPLATE_MONO_WAVE_MAX_PHASES 11 // Largest black_phases value used by any board.
/**
 * @brief Generates a mono (1bpp) waveform: black_phases "push toward black" phases followed
 * by one final black/white phase.
 * @param black_phases Number of push-toward-black phases (white pixels skip, black pixels
 * discharge); most boards use 5, Inkplate6FLICK uses 4 (it does its own separate discharge
 * pass), Inkplate4TEMPERA uses 10 (its LUT is byte-identical to the standard op_blk/op_bw
 * scheme despite the unusually high count).
 * @param out Receives black_phases+1 rows of 16 bytes each.
 */
void inkplate_gen_mono_wave(uint8_t black_phases, uint8_t out[][16]);

/**
 * @brief Generates a mono (1bpp) waveform with reversed phase roles: repeat_phases
 * push-toward-white phases followed by one final push-toward-black phase -- the mirror
 * image of inkplate_gen_mono_wave.
 * @param repeat_phases Number of push-toward-white phases (white pixels pushed white,
 * black pixels skip); required for Inkplate6PLUSV2, whose panel needs this shape -- using
 * inkplate_gen_mono_wave instead produces a uniformly dark/washed panel, since white pixels
 * only ever get one white push under that scheme.
 * @param out Receives repeat_phases+1 rows of 16 bytes each.
 */
void inkplate_gen_mono_wave_white_first(uint8_t repeat_phases, uint8_t out[][16]);

#endif // INKPLATE_WAVEFORM_H
