/**
 * @file jpeg_draw.h
 * @brief Decodes and draws a JPEG into `fb`, quantizing to mono (display_mode == 0) or
 *        3-bit GS (display_mode != 0, GS4_HMSB), matching gfx_set_pixel's convention.
 *
 * `dither`/`kernel_type` select scalar Floyd-Steinberg/JJN/Stucki/Burkes error diffusion
 * (dither.h). ESP-IDF-only (see jpeg_decode.h).
 *
 * ROM tjpgd delivers MCU tiles in tile-raster order, not full-scanline raster order -- a
 * single tile can span multiple pixel rows, all delivered before the next tile over (to
 * the right, same rows) is decoded. That breaks the row-by-row error-diffusion
 * bmp_draw_gs4 uses directly, but tjpgd's tiles still arrive in strict row-band order
 * (every tile for one MCU row-band arrives before the next band down starts), so when
 * dither is requested this buffers one row-band at a time (a small static buffer, see
 * JPEG_DRAW_CORE_BAND_MAX_W/JPEG_DRAW_CORE_MCU_MAX_H in jpeg_draw_core.h) instead of the
 * whole image, dithering and flushing each band as the next one starts arriving.
 */
#ifndef INKPLATE_JPEG_DRAW_H
#define INKPLATE_JPEG_DRAW_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Needs no allocation: if the image is wider than the band buffer (JPEG_DRAW_CORE_BAND_MAX_W/
// JPEG_DRAW_CORE_MCU_MAX_H in jpeg_draw_core.h), dithering isn't possible, so this returns -2
// (checked via jpeg_decode's pre_cb hook, right after header parse, before any MCU decoding) so
// the caller can raise a clear "image too wide to dither" error instead of silently drawing
// without dithering. Image height is unbounded either way.
/**
 * @brief Decodes and draws a JPEG into a mono/grayscale framebuffer, with optional dithering.
 * @param fb Framebuffer, phys_w x phys_h, laid out per display_mode.
 * @param phys_w Framebuffer width in pixels.
 * @param phys_h Framebuffer height in pixels.
 * @param rotation Rotation applied through the same remap gfx_set_pixel uses.
 * @param display_mode 0 for mono, non-zero for 3-bit GS4_HMSB.
 * @param x0 Logical x position to draw at.
 * @param y0 Logical y position to draw at.
 * @param buf JPEG file data.
 * @param len Length of buf in bytes.
 * @param invert Non-zero to invert pixel values.
 * @param dither Non-zero to apply error diffusion dithering.
 * @param kernel_type Selects the error-diffusion kernel (dither.h).
 * @param out_width Receives the JPEG's own pixel width on success.
 * @param out_height Receives the JPEG's own pixel height on success.
 * @return 0 on success, -1 on decode error, -2 if the image is too wide to dither.
 */
int jpeg_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                  uint32_t *out_width, uint32_t *out_height);

// RGB palette counterpart of jpeg_draw_gs4 -- placement/rotation/packing live entirely in the
// caller-supplied callback instead of fb/phys_w/phys_h/rotation/x0/y0 params here (see
// bmp_draw_palette_cb in bmp_draw.h).
typedef void (*jpeg_draw_palette_cb)(void *cb_ctx, int x, int y, int value);

// When dither is set, buffers one MCU row-band at a time (small static buffer, see
// JPEG_DRAW_CORE_BAND_MAX_W/JPEG_DRAW_CORE_MCU_MAX_H in jpeg_draw_core.h) rather than the whole
// image -- tjpgd delivers tiles in strict row-band raster order, so only one band's rows are
// ever live at once (unlike png_draw_palette's PNG path, which needs a whole-image buffer for
// Adam7-interlaced sources). This needs no allocation. If the image is wider than
// JPEG_DRAW_CORE_BAND_MAX_W, dithering isn't possible: rather than silently falling back to a
// non-dithered draw, this returns -2 so the caller can raise a clear error instead. That check
// happens right after the JPEG header is parsed (jpeg_decode's pre_cb hook), before any MCU
// entropy decoding. Image height is unbounded either way (bands are processed and discarded as
// decode progresses).
/**
 * @brief Decodes a JPEG and calls write_pixel once per pixel, matched against a palette.
 * @param buf JPEG file data.
 * @param len Length of buf in bytes.
 * @param invert Non-zero to invert pixel values before matching.
 * @param dither Non-zero to apply error diffusion dithering against the palette.
 * @param kernel_type Selects the error-diffusion kernel (dither.h).
 * @param palette Palette entries to match/dither against.
 * @param palette_n Number of entries in palette.
 * @param write_pixel Callback invoked as write_pixel(cb_ctx, x, y, value) per pixel.
 * @param cb_ctx Opaque context passed through to write_pixel.
 * @param out_width Receives the JPEG's own pixel width on success.
 * @param out_height Receives the JPEG's own pixel height on success.
 * @return 0 on success, -1 on decode error, -2 if the image is too wide to dither.
 */
int jpeg_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                      const dither_palette_entry_t *palette, int palette_n,
                      jpeg_draw_palette_cb write_pixel, void *cb_ctx, uint32_t *out_width,
                      uint32_t *out_height);

#endif // INKPLATE_JPEG_DRAW_H
