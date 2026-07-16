// Pixel-callback-free port of shared/gfx.py's GFX class (Inkplate10 scope, see
// docs/REFACTOR-PLAN.md Phase 7 step 17). Every primitive writes straight into a raw
// framebuf pointer using the same physical/rotation remap and display-mode packing as
// boards/inkplate10/inkplate10.py's write_pixel_viper -- gfx_set_pixel below IS that
// logic, consolidated into one place instead of being duplicated per caller.
//
// display_mode: 0 = 1bpp mono (INKPLATE_1BIT), non-zero = 4bpp GS4_HMSB raw 0-7 gray level
// (INKPLATE_2BIT -- named for the old 2bpp/4-level scheme, buffer format is 4bpp since
// docs/REFACTOR-PLAN.md Phase 5 step 14).
// rotation: 0=0 deg, 1=90 deg CW, 2=180 deg, 3=270 deg CCW (logical-to-physical, matches
// Inkplate.setRotation).
// phys_w/phys_h: physical (unrotated) framebuffer dimensions in pixels.
//
// Pure logic, no MicroPython/ESP-IDF dependency -- host-compilable, see tests/test_gfx.c.
#ifndef INKPLATE_GFX_H
#define INKPLATE_GFX_H

#include <stdint.h>

// gfx_set_mirror_x flips every primitive's physical column (px = phys_w - 1 - px, after
// the rotation remap) -- for boards whose panel scans columns opposite to Inkplate6/10's
// (confirmed on Inkplate5V2, see boards/inkplate5v2/inkplate5v2.py's write_pixel_viper,
// which needs the same flip). This is deliberately a one-time session-constant switch
// (set once at board init, like inkplatemodule.c's active_board), not a per-call param
// threaded through every gfx_* signature -- unlike rotation/display_mode, this never
// varies call to call once a board is selected. Defaults to 0 (off); Inkplate6/10 never
// call this, so their behavior is unchanged.
void gfx_set_mirror_x(int enable);

// gfx_set_gs4_nibble_swap flips which nibble each pixel writes in GS4_HMSB packing (even x ->
// high nibble, odd x -> low nibble, the opposite of gfx_set_pixel's default). Inkplate4TEMPERA's
// own write_pixel_viper uses this opposite convention (confirmed from its pasted
// writePixelInternal, docs/refactor_plan.md Phase 8 step 26) -- every other wired board uses the
// default. Same one-time session-constant shape as gfx_set_mirror_x, not a per-call param.
void gfx_set_gs4_nibble_swap(int enable);

void gfx_set_pixel(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x,
                   int y, int color);

// Fills the whole framebuffer with one raw byte value -- e.g. 0x00 for mono-black or
// 0x77 (both GS4_HMSB nibbles = raw level 7) for GS-white. Rotation/display_mode-agnostic:
// a full clear touches every byte regardless, so there's no per-pixel remap/packing to do,
// unlike every other gfx_* primitive here. Replaces every board's identical
// `@micropython.viper` byte-fill loop (docs/refactor_plan.md Phase 12) with a real
// `memset()`, which can move more than one byte per instruction where the viper loop
// couldn't.
void gfx_buf_fill(uint8_t *fb, int len, uint8_t value);

// Blits a 1bpp source bitmap (row_bytes = ceil(bmp_w/8) bytes/row, MSB-first per row) at
// (x0,y0): draws `color` wherever the source bit is set, leaves the destination pixel
// untouched otherwise (transparent background, matching every board's current Python
// draw_bitmap loop). Replaces that per-set-bit write_pixel Python loop with one C call.
void gfx_draw_bitmap(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                     int y0, const uint8_t *bitmap, int bmp_w, int bmp_h, int color);

void gfx_hline(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
               int y0, int width, int color);
void gfx_vline(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
               int y0, int height, int color);

void gfx_line(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0, int y0,
              int x1, int y1, int color);
void gfx_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0, int y0,
              int width, int height, int color);
void gfx_fill_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                   int y0, int width, int height, int color);
void gfx_circle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                int y0, int radius, int color);
void gfx_fill_circle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                     int y0, int radius, int color);
void gfx_triangle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, int x1, int y1, int x2, int y2, int color);
void gfx_fill_triangle(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode,
                       int x0, int y0, int x1, int y1, int x2, int y2, int color);
void gfx_round_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                    int y0, int width, int height, int radius, int color);
void gfx_fill_round_rect(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode,
                         int x0, int y0, int width, int height, int radius, int color);

// Blits one already-decoded glyph bitmap (char_data: char_h rows of ceil(char_w/8) bytes
// each, MSB-first per row -- the format shared/gfx_standard_font_01.py-style font modules'
// get_ch() returns) at `size`x scale. Replaces gfx.py's _draw_char_1bpp/_draw_char_2bpp:
// those two were split by a caller-supplied `bpp` kwarg that had drifted out of sync with
// the real framebuf storage (text kept assuming 2bpp/0-3 after Phase 5 step 14 switched GS
// storage to 4bpp/0-7) -- this version takes display_mode instead, like every other
// primitive here, so there is one packing decision instead of two that can disagree.
void gfx_draw_char(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                   int y0, const uint8_t *char_data, int char_w, int char_h, int size, int color);

#endif
