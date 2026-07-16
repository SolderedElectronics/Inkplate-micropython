// Decodes+draws a PNG (via png_decode.c's pngle wrapper) into `fb`, quantizing to mono
// (display_mode == 0) or 3-bit GS (display_mode != 0, GS4_HMSB), matching
// gfx_set_pixel's convention. Alpha is still ignored (treated fully opaque) --
// compositing isn't in this step's scope. docs/REFACTOR-PLAN.md step 21:
// `dither`/`kernel_type` select scalar Floyd-Steinberg/JJN/Stucki/Burkes error
// diffusion (dither.h). ESP-IDF-only, HIL-verify only (see png_decode.h).
//
// pngle's per-pixel callback is only raster-order *within* a single Adam7 interlace
// pass, not across the whole decode (each pass re-sweeps the image), so a single
// inline row-by-row dithering pass (like bmp_draw_gs4's) can't be trusted for
// interlaced PNGs -- those still buffer the whole image's luma (capped at
// PNG_DRAW_CORE_MAX_WIDTH x PNG_DRAW_CORE_MAX_HEIGHT, see png_draw_core.h) and dither it in one
// guaranteed row-major pass after decode completes. But Adam7 is opt-in at PNG
// encode time and rare in practice (most encoders default to off); png_decode.h's
// png_peek_interlace reads that flag straight out of IHDR before any decode work
// starts, and when it's off, pngle *is* strictly raster order over the whole image
// (a single non-interlaced sweep), same as bmp_draw_gs4/tjpgd's MCU bands -- so
// that (common) case dithers inline, per pixel, with no whole-image buffer and no
// PNG_DRAW_CORE_MAX_* cap at all.
#ifndef INKPLATE_PNG_DRAW_H
#define INKPLATE_PNG_DRAW_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Draws the PNG at buf/len into `fb` (a phys_w x phys_h framebuffer, layout per
// display_mode) at logical position (x0, y0), through the same rotation remap
// gfx_set_pixel uses. `out_width`/`out_height` receive the PNG's own pixel
// dimensions on success. Returns 0 on success, -1 on decode error, an allocation
// failure, or (Adam7-interlaced sources only, via the buffered fallback path) a
// size over PNG_DRAW_CORE_MAX_WIDTH/HEIGHT.
int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height);

// docs/REFACTOR-PLAN.md Phase 10 step 32: N-color RGB palette counterpart of
// png_draw_gs4 -- see bmp_draw.h's bmp_draw_palette_cb comment for why placement/
// rotation/packing live entirely in the caller-supplied callback instead of fb/
// phys_w/phys_h/rotation/x0/y0 params here. Alpha is still ignored (treated fully
// opaque), same as png_draw_gs4.
typedef void (*png_draw_palette_cb)(void *cb_ctx, int x, int y, int value);

// Decodes the PNG at buf/len, dithers (if `dither`) against `palette` (palette_n
// entries), and calls `write_pixel(cb_ctx, x, y, value)` once per pixel with
// image-local (x, y) and the matched palette entry's `value`. Same streamed-vs-
// buffered split as png_draw_gs4 above: a non-interlaced source (the common case,
// checked via png_peek_interlace before any decode work starts) dithers inline per
// pixel with no whole-image buffer at all -- `max_width`/`max_height`/`scratch_rgb`/
// `scratch_cap` are unused for this path. Only an Adam7-interlaced source (or a
// peek that couldn't even determine that) falls back to buffering the full decoded
// RGB image into the caller-supplied `scratch_rgb` (capped at max_width x
// max_height, caller's choice, not a fixed constant here -- see jpeg_draw.h's
// identical param for the full reasoning). `scratch_rgb` must hold at least
// max_width*max_height uint16_t entries (`scratch_cap` is the actual capacity
// provided) -- caller-owned, not heap_caps_malloc'd in here (see
// jpeg_draw_palette's identical comment for the HIL-confirmed PSRAM-fragmentation
// reasoning). If an interlaced source is bigger than max_width/max_height, or
// `scratch_rgb` is NULL/too small, dithering isn't possible: rather than silently
// degrading to a non-dithered draw (surprising, since the caller asked for
// dithering), this returns -2 so the caller can raise a clear "image too wide to
// dither" error instead (same reasoning as jpeg_draw_palette's identical -2).
// Returns 0 on success, -1 on decode error, -2 if the (interlaced) image can't be
// dithered at this size.
int png_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     png_draw_palette_cb write_pixel, void *cb_ctx, int max_width, int max_height,
                     uint16_t *scratch_rgb, size_t scratch_cap, uint32_t *out_width,
                     uint32_t *out_height);

#endif // INKPLATE_PNG_DRAW_H
