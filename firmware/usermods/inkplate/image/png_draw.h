/**
 * @file png_draw.h
 * @brief Decodes+draws a PNG (via png_decode.c's pngle wrapper) into `fb`, quantizing
 *        to mono (display_mode == 0) or 3-bit GS (display_mode != 0, GS4_HMSB),
 *        matching gfx_set_pixel's convention.
 *
 * Alpha is ignored (treated as fully opaque). `dither`/`kernel_type` select scalar
 * Floyd-Steinberg/JJN/Stucki/Burkes error diffusion (dither.h).
 *
 * pngle's per-pixel callback is only raster-order within a single Adam7 interlace pass,
 * not across the whole decode (each pass re-sweeps the image), so a single inline
 * row-by-row dithering pass (like bmp_draw_gs4's) can't be trusted for interlaced PNGs
 * -- those still buffer the whole image's luma (capped at PNG_DRAW_CORE_MAX_WIDTH x
 * PNG_DRAW_CORE_MAX_HEIGHT, see png_draw_core.h) and dither it in one guaranteed
 * row-major pass after decode completes. Adam7 is opt-in at PNG encode time and rare in
 * practice (most encoders default to off); png_decode.h's png_peek_interlace reads that
 * flag straight out of IHDR before any decode work starts, and when it's off, pngle is
 * strictly raster order over the whole image (a single non-interlaced sweep), same as
 * bmp_draw_gs4/tjpgd's MCU bands -- so that (common) case dithers inline, per pixel,
 * with no whole-image buffer and no PNG_DRAW_CORE_MAX_* cap at all.
 */
#ifndef INKPLATE_PNG_DRAW_H
#define INKPLATE_PNG_DRAW_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

/**
 * @brief Decodes and draws a PNG into a framebuffer, quantizing to mono or 3-bit grayscale.
 * @param fb Destination framebuffer, phys_w x phys_h, layout per display_mode.
 * @param phys_w Framebuffer physical width.
 * @param phys_h Framebuffer physical height.
 * @param rotation Rotation remap applied, same convention as gfx_set_pixel.
 * @param display_mode 0 for mono, non-zero for 3-bit GS4_HMSB.
 * @param x0 Logical x position to draw at.
 * @param y0 Logical y position to draw at.
 * @param buf PNG-encoded source buffer.
 * @param len Length of buf in bytes.
 * @param invert Non-zero to invert pixel values after quantization.
 * @param dither Non-zero to apply error-diffusion dithering.
 * @param kernel_type Selects the dither kernel (Floyd-Steinberg/JJN/Stucki/Burkes).
 * @param out_width Receives the PNG's own pixel width on success.
 * @param out_height Receives the PNG's own pixel height on success.
 * @return 0 on success, -1 on decode error or allocation failure, or (Adam7-interlaced
 *         sources only, via the buffered fallback path) if the image exceeds
 *         PNG_DRAW_CORE_MAX_WIDTH/HEIGHT.
 */
int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height);

// N-color RGB palette counterpart of png_draw_gs4 -- see bmp_draw.h's
// bmp_draw_palette_cb comment for why placement/rotation/packing live entirely in
// the caller-supplied callback instead of fb/phys_w/phys_h/rotation/x0/y0 params
// here. Alpha is ignored (treated as fully opaque), same as png_draw_gs4.
/**
 * @brief Callback invoked once per decoded pixel to write a matched palette entry.
 * @param cb_ctx Caller-supplied context pointer, passed through unchanged.
 * @param x Image-local pixel x coordinate.
 * @param y Image-local pixel y coordinate.
 * @param value Matched palette entry's value.
 */
typedef void (*png_draw_palette_cb)(void *cb_ctx, int x, int y, int value);

// Same streamed-vs-buffered split as png_draw_gs4 above: a non-interlaced source
// (the common case, checked via png_peek_interlace before any decode work starts)
// dithers inline per pixel with no whole-image buffer at all --
// `max_width`/`max_height`/`scratch_rgb`/`scratch_cap` are unused for this path.
// Only an Adam7-interlaced source (or a peek that couldn't even determine that)
// falls back to buffering the full decoded RGB image into the caller-supplied
// `scratch_rgb` (capped at max_width x max_height, caller's choice, not a fixed
// constant here -- see jpeg_draw.h's identical param for the full reasoning).
// `scratch_rgb` must hold at least max_width*max_height uint16_t entries
// (`scratch_cap` is the actual capacity provided) -- caller-owned, not
// heap_caps_malloc'd in here (see jpeg_draw_palette's identical comment for the
// PSRAM-fragmentation reasoning). If an interlaced source is bigger than
// max_width/max_height, or `scratch_rgb` is NULL/too small, dithering isn't
// possible: rather than silently degrading to a non-dithered draw (surprising,
// since the caller asked for dithering), this returns -2 so the caller can raise a
// clear "image too wide to dither" error instead (same reasoning as
// jpeg_draw_palette's identical -2).
/**
 * @brief Decodes a PNG and writes each pixel's matched palette entry via callback.
 * @param buf PNG-encoded source buffer.
 * @param len Length of buf in bytes.
 * @param invert Non-zero to invert pixel values before palette matching.
 * @param dither Non-zero to apply error-diffusion dithering against palette.
 * @param kernel_type Selects the dither kernel (Floyd-Steinberg/JJN/Stucki/Burkes).
 * @param palette Palette entries to match/dither against.
 * @param palette_n Number of entries in palette.
 * @param write_pixel Callback invoked once per pixel with the matched palette value.
 * @param cb_ctx Context pointer passed through unchanged to write_pixel.
 * @param max_width Maximum image width the buffered (interlaced) path can handle.
 * @param max_height Maximum image height the buffered (interlaced) path can handle.
 * @param scratch_rgb Caller-owned scratch buffer for the buffered path, unused otherwise.
 * @param scratch_cap Capacity of scratch_rgb in uint16_t entries.
 * @param out_width Receives the PNG's own pixel width on success.
 * @param out_height Receives the PNG's own pixel height on success.
 * @return 0 on success, -1 on decode error, -2 if the (interlaced) image can't be
 *         dithered at this size.
 */
int png_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     png_draw_palette_cb write_pixel, void *cb_ctx, int max_width, int max_height,
                     uint16_t *scratch_rgb, size_t scratch_cap, uint32_t *out_width,
                     uint32_t *out_height);

#endif // INKPLATE_PNG_DRAW_H
