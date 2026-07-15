// Decodes+draws a JPEG (via jpeg_decode.c, ROM tjpgd) into `fb`, quantizing to mono
// (display_mode == 0) or 3-bit GS (display_mode != 0, GS4_HMSB), matching
// gfx_set_pixel's convention. docs/REFACTOR-PLAN.md step 21: `dither`/`kernel_type`
// select scalar Floyd-Steinberg/JJN/Stucki/Burkes error diffusion (dither.h).
// ESP-IDF-only, HIL-verify only (see jpeg_decode.h).
//
// ROM-tjpgd delivers MCU tiles in tile-raster order, not full-scanline raster order --
// a single tile can span multiple pixel rows, all delivered before the next tile over
// (to the right, same rows) is decoded. That breaks the row-by-row error-diffusion
// bmp_draw_gs4 uses, so when dither is requested this instead buffers the whole
// image's luma (capped at JPEG_DRAW_MAX_WIDTH x JPEG_DRAW_MAX_HEIGHT, see jpeg_draw.c)
// during decode, then dithers it in one guaranteed row-major pass afterward.
#ifndef INKPLATE_JPEG_DRAW_H
#define INKPLATE_JPEG_DRAW_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Draws the JPEG at buf/len into `fb` (a phys_w x phys_h framebuffer, layout per
// display_mode) at logical position (x0, y0), through the same rotation remap
// gfx_set_pixel uses. `out_width`/`out_height` receive the JPEG's own pixel
// dimensions on success. Returns 0 on success, -1 on decode error, a size over the
// dither buffer's cap, or an allocation failure.
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
// buffers the full decoded RGB image (capped at max_width x max_height, caller's
// choice -- not a fixed constant here, deliberately: see inkplatemodule.c's caller,
// which passes the panel's own physical size, not a generously-sized "typical
// photo" floor -- HIL on Inkplate6COLOR confirmed a fixed floor sized for the
// largest board in this family (Inkplate13SPECTRA, up to ~5.76MB of PSRAM at 3
// bytes/pixel) always requested that much regardless of the actual source image,
// which reliably lost to PSRAM fragmentation even for images that would have fit a
// panel-sized buffer easily). If the source image turns out bigger than
// max_width/max_height, this retries the whole decode with dithering off instead
// of failing -- draw's usual clip-to-panel behavior still applies to the
// non-dithered result, so an oversized source image degrades gracefully rather
// than being rejected. Also gracefully degrades to non-dithered if the buffer
// allocation itself fails (transient PSRAM fragmentation). Same buffering
// reasoning as jpeg_draw_gs4's luma buffer otherwise -- tiles can arrive out of row
// order. Returns 0 on success, -1 on decode error or allocation failure.
int jpeg_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                      const dither_palette_entry_t *palette, int palette_n,
                      jpeg_draw_palette_cb write_pixel, void *cb_ctx, int max_width,
                      int max_height, uint32_t *out_width, uint32_t *out_height);

#endif // INKPLATE_JPEG_DRAW_H
