// Pure-logic LUT generation for mono partial updates over I2S (Phase 6,
// docs/REFACTOR-PLAN.md step 16). No ESP-IDF/hardware headers -- host-compiled unit test
// target, same tier as waveform.c.
#ifndef INKPLATE_EPD_PARTIAL_LUT_H
#define INKPLATE_EPD_PARTIAL_LUT_H

#include <stdint.h>

// Builds the 256-entry old-nibble/new-nibble -> 2bpp wire-code byte LUT partial updates
// use: index (old_nibble << 4 | new_nibble) -> a byte encoding 4 pixels' worth of 2-bit
// wire codes (0=discharge,1=black,2=white,3=skip).
//
// Ported from the real Arduino Inkplate6/6v2 reference driver's partialUpdate():
// diffw = old & ~new (a pixel that WAS black and IS NOW white), diffb = ~old & new (a
// pixel that WAS white and IS NOW black); the combined code is `LUTW[diffw_nibble] &
// LUTB[diffb_nibble]`, where LUTW/LUTB are the reference driver's own 16-entry tables
// (GraphicsDefs.h). Unchanged pixels get skip(3) from both tables (bit=0 in both diffw
// and diffb), changed pixels get pushed toward the color they're becoming (diffw=1 ->
// white-push(2), diffb=1 -> black-push(1)) -- physically sane once traced through
// correctly.
//
// NOTE on the reference driver's own variable names: partialUpdate() computes
// `diffw = DMemoryNew & ~_partial` and reads as if DMemoryNew is "new" and _partial is
// "old", but DMemoryNew is only memcpy'd from _partial at the *end* of the function --
// during the diff computation it still holds the *previous* display's content, while
// _partial holds the *current* one. So DMemoryNew is actually old, _partial is actually
// new, the reverse of what the names suggest. This LUT's `old`/`new` parameter naming
// here reflects the corrected (actual) roles, not the reference driver's misleading ones
// -- verified against LUT2 (bit=1 -> black(1), bit=0 -> white(2), consistent with
// clearDisplay() zeroing the buffer to a blank/white page) and cross-checked against the
// already-HIL-verified mono LUTB/lut_blk parity (waveform.c's inkplate_gen_mono_wave).
void inkplate_gen_partial_diff_lut(uint8_t out[256]);

#endif // INKPLATE_EPD_PARTIAL_LUT_H
