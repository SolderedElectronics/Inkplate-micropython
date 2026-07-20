/**
 * @file epd_partial_lut.h
 * @brief Pure-logic LUT generation for mono partial updates over I2S.
 *
 * No ESP-IDF/hardware headers -- host-compiled unit test target, same tier as
 * waveform.c.
 */
#ifndef INKPLATE_EPD_PARTIAL_LUT_H
#define INKPLATE_EPD_PARTIAL_LUT_H

#include <stdint.h>

// Builds the 256-entry old-nibble/new-nibble -> 2bpp wire-code byte LUT partial updates
// use: index (old_nibble << 4 | new_nibble) -> a byte encoding 4 pixels' worth of 2-bit
// wire codes (0=discharge,1=black,2=white,3=skip).
//
// Diffing logic: diffw = old & ~new (a pixel that WAS black and IS NOW white), diffb =
// ~old & new (a pixel that WAS white and IS NOW black); the combined code is
// `LUTW[diffw_nibble] & LUTB[diffb_nibble]`, where LUTW/LUTB are the display controller's
// own 16-entry lookup tables. Unchanged pixels get skip(3) from both tables (bit=0 in both
// diffw and diffb), changed pixels get pushed toward the color they're becoming (diffw=1
// -> white-push(2), diffb=1 -> black-push(1)).
//
// The underlying driver code's own framebuffer variables are misleadingly named: the one
// named as if it holds the new frame is only updated at the *end* of its update routine,
// so at diff time it still holds the *previous* frame, while the one named as if it holds
// the old frame actually holds the *current* one -- the names are swapped from their
// actual roles. This LUT's `old`/`new` parameter naming below reflects the corrected,
// actual roles, not that swapped naming.
/**
 * @brief Build the 256-entry old/new-nibble diff lookup table for mono partial updates.
 * @param out 256-byte buffer to fill; indexed by (old_nibble << 4 | new_nibble).
 */
void inkplate_gen_partial_diff_lut(uint8_t out[256]);

#endif // INKPLATE_EPD_PARTIAL_LUT_H
