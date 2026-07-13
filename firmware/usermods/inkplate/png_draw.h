// Decodes a PNG (via png_decode.c's pngle wrapper) straight into a GS4_HMSB
// framebuffer, quantizing each pixel's luminance to the nearest of the 8 gray
// levels. Alpha is ignored (treated fully opaque) -- placeholder ahead of
// docs/REFACTOR-PLAN.md step 21's real dithering/compositing, same scope as
// jpeg_draw.h. ESP-IDF-only, HIL-verify only (see png_decode.h).
#ifndef INKPLATE_PNG_DRAW_H
#define INKPLATE_PNG_DRAW_H

#include <stddef.h>
#include <stdint.h>

// Draws the PNG at buf/len into `fb` (a phys_w x phys_h GS4_HMSB framebuffer,
// same layout as gfx.h's display_mode=1) at logical position (x0, y0), through
// the same rotation remap gfx_set_pixel uses. `out_width`/`out_height` receive
// the PNG's own pixel dimensions on success. Returns 0 on success, -1 on decode
// error.
int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int x0, int y0,
                 const uint8_t *buf, size_t len, uint32_t *out_width, uint32_t *out_height);

#endif // INKPLATE_PNG_DRAW_H
