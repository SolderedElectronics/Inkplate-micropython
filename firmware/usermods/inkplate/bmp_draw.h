// Decodes a BMP (via bmp_decode.c) and blits it into `fb`, quantizing to mono
// (display_mode == 0) or 3-bit GS (display_mode != 0, GS4_HMSB), matching
// gfx_set_pixel's convention. docs/REFACTOR-PLAN.md step 21: `dither`/`kernel_type`
// select scalar Floyd-Steinberg/JJN/Stucki/Burkes error diffusion (dither.h);
// kernel_type is ignored when dither is 0. BMP decodes strictly row-major already
// (bmp_decode.c), so this dithers inline, one row at a time -- no full-image buffering
// needed, unlike jpeg_draw.c/png_draw.c.
#ifndef INKPLATE_BMP_DRAW_H
#define INKPLATE_BMP_DRAW_H

#include <stddef.h>
#include <stdint.h>

// Draws the BMP at buf/len into `fb` (a phys_w x phys_h framebuffer, layout per
// display_mode) at logical position (x0, y0), through the same rotation remap
// gfx_set_pixel uses. `out_width`/`out_height` receive the BMP's own pixel dimensions
// on success. Returns 0 on success, -1 on parse/decode error (including a width wider
// than this module's internal row-scratch buffer) or dither error-buffer allocation
// failure.
int bmp_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height);

#endif // INKPLATE_BMP_DRAW_H
