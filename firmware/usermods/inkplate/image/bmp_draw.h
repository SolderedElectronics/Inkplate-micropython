/**
 * @file bmp_draw.h
 * @brief BMP decode-and-draw, with optional scalar error-diffusion dithering.
 *
 * BMP decodes strictly row-major already, so this dithers inline, one row at a time --
 * no full-image buffering needed, unlike jpeg_draw.c/png_draw.c.
 */
#ifndef INKPLATE_BMP_DRAW_H
#define INKPLATE_BMP_DRAW_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

/**
 * @brief Decodes a BMP and blits it into a mono/GS4 framebuffer.
 * @param fb Destination framebuffer, phys_w x phys_h, laid out per display_mode.
 * @param phys_w Framebuffer width in pixels.
 * @param phys_h Framebuffer height in pixels.
 * @param rotation Rotation remap, same convention as gfx_set_pixel.
 * @param display_mode 0 for mono, non-zero for 3-bit GS (GS4_HMSB), per gfx_set_pixel.
 * @param x0 Logical x position to draw the BMP's top-left corner at.
 * @param y0 Logical y position to draw the BMP's top-left corner at.
 * @param buf BMP file buffer.
 * @param len Length of buf in bytes.
 * @param invert Invert quantized pixel levels.
 * @param dither Enable scalar error-diffusion dithering (0 = off).
 * @param kernel_type Dither kernel selection (dither.h); ignored when dither is 0.
 * @param out_width Receives the BMP's own pixel width on success.
 * @param out_height Receives the BMP's own pixel height on success.
 * @return 0 on success, -1 on parse/decode error (including a width wider than
 *         this module's internal row-scratch buffer) or dither error-buffer
 *         allocation failure.
 */
int bmp_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height);

// N-color RGB palette counterpart of bmp_draw_gs4. Unlike that function, this one
// has no fb/phys_w/phys_h/rotation/x0/y0 params of its own -- placement, rotation,
// and pixel packing are entirely the caller-supplied `write_pixel` callback's job,
// since the SPI color boards' packing/rotation conventions differ per board and
// don't fit one shared layout the way mono/GS4 do.
typedef void (*bmp_draw_palette_cb)(void *cb_ctx, int x, int y, int value);

/**
 * @brief Decodes a BMP and delivers pixels through a palette-matching callback.
 * @param buf BMP file buffer.
 * @param len Length of buf in bytes.
 * @param invert Invert black/white matching when quantizing against palette.
 * @param dither Enable scalar error-diffusion dithering against palette (0 = off).
 * @param kernel_type Dither kernel selection (dither.h); ignored when dither is 0.
 * @param palette Target palette entries to quantize/dither against.
 * @param palette_n Number of entries in palette.
 * @param write_pixel Callback invoked once per pixel, with image-local (x, y) --
 *        0..width-1 / 0..height-1, in file row order after any vertical flip --
 *        and the matched palette entry's value.
 * @param cb_ctx Opaque context pointer passed through to write_pixel.
 * @param out_width Receives the BMP's own pixel width on success.
 * @param out_height Receives the BMP's own pixel height on success.
 * @return 0 on success, -1 on parse/decode error or dither error-buffer allocation
 *         failure, -2 if the image is wider than this module's per-row scratch
 *         buffer can draw (this cap applies regardless of dither, unlike jpeg/png's
 *         palette draw, since that scratch buffer serves both paths here).
 */
int bmp_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     bmp_draw_palette_cb write_pixel, void *cb_ctx, uint32_t *out_width,
                     uint32_t *out_height);

#endif // INKPLATE_BMP_DRAW_H
