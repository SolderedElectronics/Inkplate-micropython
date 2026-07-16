// Decodes+draws a JPEG (via jpeg_decode.c, ROM tjpgd) into `fb`, quantizing to mono
// (display_mode == 0) or 3-bit GS (display_mode != 0, GS4_HMSB), matching
// gfx_set_pixel's convention. docs/REFACTOR-PLAN.md step 21: `dither`/`kernel_type`
// select scalar Floyd-Steinberg/JJN/Stucki/Burkes error diffusion (dither.h).
// ESP-IDF-only, HIL-verify only (see jpeg_decode.h).
//
// ROM-tjpgd delivers MCU tiles in tile-raster order, not full-scanline raster order --
// a single tile can span multiple pixel rows, all delivered before the next tile over
// (to the right, same rows) is decoded. That breaks the row-by-row error-diffusion
// bmp_draw_gs4 uses directly, but tjpgd's tiles still arrive in strict row-band order
// (every tile for one MCU row-band arrives before the next band down starts), so when
// dither is requested this buffers one row-band at a time (a small static buffer, see
// JPEG_DRAW_CORE_BAND_MAX_W/JPEG_DRAW_CORE_MCU_MAX_H in jpeg_draw_core.h) instead of the whole image,
// dithering+flushing each band as the next one starts arriving.
#ifndef INKPLATE_JPEG_DRAW_H
#define INKPLATE_JPEG_DRAW_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Draws the JPEG at buf/len into `fb` (a phys_w x phys_h framebuffer, layout per
// display_mode) at logical position (x0, y0), through the same rotation remap
// gfx_set_pixel uses. `out_width`/`out_height` receive the JPEG's own pixel
// dimensions on success. Needs no allocation (see jpeg_draw_palette's identical
// comment on JPEG_DRAW_CORE_BAND_MAX_W/JPEG_DRAW_CORE_MCU_MAX_H) -- if the image is wider than
// that band buffer, dithering isn't possible: this returns -2 (checked via
// jpeg_decode's pre_cb hook, right after header parse, before any MCU decoding) so
// the caller can raise a clear "image too wide to dither" error instead of silently
// drawing without dithering. Image height is unbounded either way. Returns 0 on
// success, -1 on decode error, -2 if the image is too wide to dither.
int jpeg_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                  uint32_t *out_width, uint32_t *out_height);

// docs/REFACTOR-PLAN.md Phase 10 step 32: N-color RGB palette counterpart of
// jpeg_draw_gs4 -- see bmp_draw.h's bmp_draw_palette_cb comment for why placement/
// rotation/packing live entirely in the caller-supplied callback instead of fb/
// phys_w/phys_h/rotation/x0/y0 params here.
typedef void (*jpeg_draw_palette_cb)(void *cb_ctx, int x, int y, int value);

// Decodes the JPEG at buf/len, dithers (if `dither`) against `palette` (palette_n
// entries), and calls `write_pixel(cb_ctx, x, y, value)` once per pixel with
// image-local (x, y) and the matched palette entry's `value`. When `dither` is set,
// buffers one MCU row-band at a time into a small static buffer (see
// JPEG_DRAW_CORE_BAND_MAX_W/JPEG_DRAW_CORE_MCU_MAX_H in jpeg_draw_core.h) rather than the
// whole image -- tjpgd delivers tiles in strict row-band raster order, so only one
// band's rows are ever live at once (unlike png_draw_palette's PNG path, which
// genuinely needs a whole-image buffer for Adam7-interlaced sources). This needs no
// allocation at all (docs/REFACTOR-PLAN.md Phase 10 step 32's followup: the old
// whole-image buffer, whether heap_caps_malloc'd or a caller-supplied bytearray,
// could still fail to fit real Inkplate6COLOR PSRAM once other allocations had
// fragmented it -- a band this small never can). If the image is wider than
// JPEG_DRAW_CORE_BAND_MAX_W, dithering isn't possible at this width: rather than
// silently falling back to a non-dithered draw (surprising, since the caller asked
// for dithering), this returns -2 so the caller can raise a clear "image too wide,
// try scaling it down" error instead. That check happens right after the JPEG
// header is parsed (jpeg_decode's pre_cb hook), before any MCU entropy decoding --
// an oversized image costs no more than a header parse to reject, not a full
// decode. Image height is unbounded either way (bands are processed and discarded
// as decode progresses). Returns 0 on success, -1 on decode error, -2 if the image
// is too wide to dither.
int jpeg_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                      const dither_palette_entry_t *palette, int palette_n,
                      jpeg_draw_palette_cb write_pixel, void *cb_ctx, uint32_t *out_width,
                      uint32_t *out_height);

#endif // INKPLATE_JPEG_DRAW_H
