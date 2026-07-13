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

// Draws the JPEG at buf/len into `fb` (a phys_w x phys_h framebuffer, layout per
// display_mode) at logical position (x0, y0), through the same rotation remap
// gfx_set_pixel uses. `out_width`/`out_height` receive the JPEG's own pixel
// dimensions on success. Returns 0 on success, -1 on decode error, a size over the
// dither buffer's cap, or an allocation failure.
int jpeg_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                  uint32_t *out_width, uint32_t *out_height);

#endif // INKPLATE_JPEG_DRAW_H
