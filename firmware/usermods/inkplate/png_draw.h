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
// interlaced PNGs. When dither is requested this instead buffers the whole image's
// luma (capped at PNG_DRAW_MAX_WIDTH x PNG_DRAW_MAX_HEIGHT, see png_draw.c), then
// dithers it in one guaranteed row-major pass after decode completes.
#ifndef INKPLATE_PNG_DRAW_H
#define INKPLATE_PNG_DRAW_H

#include <stddef.h>
#include <stdint.h>

// Draws the PNG at buf/len into `fb` (a phys_w x phys_h framebuffer, layout per
// display_mode) at logical position (x0, y0), through the same rotation remap
// gfx_set_pixel uses. `out_width`/`out_height` receive the PNG's own pixel
// dimensions on success. Returns 0 on success, -1 on decode error, a size over the
// dither buffer's cap, or an allocation failure.
int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height);

#endif // INKPLATE_PNG_DRAW_H
