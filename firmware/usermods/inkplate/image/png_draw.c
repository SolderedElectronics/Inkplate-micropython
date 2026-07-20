/**
 * @file png_draw.c
 * @brief PNG decode-and-draw (with optional dithering) implementation.
 */
#include "png_draw.h"

#include "esp_heap_caps.h"

#include "png_decode.h"
#include "png_draw_core.h"

// Thin ESP-IDF-dependent wrapper: drives the real png_decode()/png_peek_dimensions/
// png_peek_interlace (pngle + ROM miniz, hardware-only) and forwards decoded pixels to
// png_draw_core.c's pure dither/quantize/blit logic, which carries all the actual test
// coverage (tests/test_png_draw_core.c) since this file's own glue can't be host-compiled
// (png_decode.h drags in the ROM decoder).

int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height)
{
    if (dither) {
        uint32_t peek_w = 0, peek_h = 0;
        uint8_t peek_interlace = 0;
        // A failed peek (buf too short) or an interlaced source falls through to the
        // buffered path below, same "trust the real decode(), this is only a fast-path
        // peek" reasoning as png_peek_dimensions' own comment.
        if (png_peek_dimensions(buf, len, &peek_w, &peek_h) == 0 &&
            png_peek_interlace(buf, len, &peek_interlace) == 0 && peek_interlace == 0) {
            png_draw_core_stream_ctx_t ctx;
            png_draw_core_stream_init(&ctx, fb, phys_w, phys_h, rotation, display_mode, x0, y0,
                                      invert, peek_w, peek_h, kernel_type);

            uint32_t width = 0, height = 0;
            int res = png_decode(buf, len, (png_pixel_cb_t)png_draw_core_pixel_stream, &ctx,
                                 &width, &height);
            png_draw_core_stream_finish(&ctx);
            if (res == 0 && ctx.oversized) {
                res = -1;
            }
            if (res != 0) {
                return -1;
            }
            *out_width = width;
            *out_height = height;
            return 0;
        }
    }

    // Buffered path: dither==0 (order-independent, no diffusion state carried between
    // pixels, so this streams pixel-by-pixel below regardless of interlacing), or
    // dither==1 with an Adam7-interlaced source (or a peek that couldn't even determine
    // that).
    uint8_t *luma = NULL;
    if (dither) {
        // Plain malloc() draws from ESP32's small internal-DRAM pool and fails outright
        // for a buffer this size -- this scratch buffer needs PSRAM explicitly, same as
        // the project's framebuffers.
        luma = heap_caps_malloc((size_t)PNG_DRAW_CORE_MAX_WIDTH * PNG_DRAW_CORE_MAX_HEIGHT,
                                MALLOC_CAP_SPIRAM);
        if (luma == NULL) {
            return -1;
        }
    }

    png_draw_core_ctx_t ctx;
    png_draw_core_init(&ctx, fb, phys_w, phys_h, rotation, display_mode, x0, y0, invert, dither,
                       kernel_type, luma);

    uint32_t width = 0, height = 0;
    int res = png_decode(buf, len, (png_pixel_cb_t)png_draw_core_pixel, &ctx, &width, &height);

    if (res == 0 && ctx.oversized) {
        res = -1;
    }
    if (res == 0 && dither) {
        png_draw_core_dither_pass(&ctx, width, height);
    }
    if (dither) {
        heap_caps_free(luma);
    }
    if (res != 0) {
        return -1;
    }

    *out_width = width;
    *out_height = height;
    return 0;
}

int png_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     png_draw_palette_cb write_pixel, void *cb_ctx, int max_width, int max_height,
                     uint16_t *scratch_rgb, size_t scratch_cap, uint32_t *out_width,
                     uint32_t *out_height)
{
    // png_draw_palette_cb and png_draw_core_palette_write_cb are structurally identical
    // function pointer types (void(*)(void*, int, int, int)) -- cast is safe, avoids the
    // two headers needing to share a typedef.
    png_draw_core_palette_write_cb core_write_pixel = (png_draw_core_palette_write_cb)write_pixel;

    if (dither) {
        uint32_t peek_w = 0, peek_h = 0;
        uint8_t peek_interlace = 0;
        // Same "trust the real decode(), this is only a fast-path peek" reasoning as
        // png_draw_gs4 above.
        if (png_peek_dimensions(buf, len, &peek_w, &peek_h) == 0 &&
            png_peek_interlace(buf, len, &peek_interlace) == 0 && peek_interlace == 0) {
            png_draw_core_palette_stream_ctx_t ctx;
            png_draw_core_palette_stream_init(&ctx, invert, kernel_type, palette, palette_n,
                                              core_write_pixel, cb_ctx, peek_w, peek_h);

            uint32_t width = 0, height = 0;
            int res = png_decode(buf, len, (png_pixel_cb_t)png_draw_core_palette_pixel_stream,
                                 &ctx, &width, &height);
            png_draw_core_palette_stream_finish(&ctx);
            if (res == 0 && ctx.oversized) {
                res = -1;
            }
            if (res != 0) {
                return -1;
            }
            *out_width = width;
            *out_height = height;
            return 0;
        }
    }

    // Buffered path: dither==0 (order-independent, streams pixel-by-pixel below via
    // png_draw_core_palette_pixel regardless of interlacing), or dither==1 with an
    // Adam7-interlaced source (or a peek that couldn't even determine that) -- this is
    // the only case that still needs max_width/max_height and a caller-supplied
    // scratch_rgb buffer.
    uint16_t *rgb = NULL;
    if (dither) {
        // Reject an oversized image before paying for any decode work at all --
        // png_peek_dimensions reads IHDR directly (fixed byte offset every PNG shares),
        // without touching pngle. Source image bigger than max_width/max_height
        // (typically the panel's own physical size -- see inkplatemodule.c's caller)
        // can't be dithered: same distinct return code as the missing-buffer case
        // below, rather than silently redrawing without dithering. A failed peek (buf
        // too short) just falls through -- the real png_decode() call below reports
        // that as a decode error instead.
        uint32_t peek_w = 0, peek_h = 0;
        if (png_peek_dimensions(buf, len, &peek_w, &peek_h) == 0 &&
            (peek_w > (uint32_t)max_width || peek_h > (uint32_t)max_height)) {
            return -2;
        }

        // Caller-supplied buffer -- see jpeg_draw_palette's identical comment for the
        // PSRAM-fragmentation reasoning for why this isn't heap_caps_malloc'd in here.
        // Missing/undersized buffer can't dither either -- same distinct return code as
        // the oversized case above.
        if (scratch_rgb == NULL || scratch_cap < (size_t)max_width * (size_t)max_height) {
            return -2;
        }
        rgb = scratch_rgb;
    }

    png_draw_core_palette_ctx_t ctx;
    png_draw_core_palette_init(&ctx, invert, dither, kernel_type, palette, palette_n,
                               core_write_pixel, cb_ctx, max_width, max_height, rgb);

    uint32_t width = 0, height = 0;
    int res =
        png_decode(buf, len, (png_pixel_cb_t)png_draw_core_palette_pixel, &ctx, &width, &height);

    if (res != 0) {
        return -1;
    }
    if (dither) {
        png_draw_core_palette_dither_pass(&ctx, width, height);
    }

    *out_width = width;
    *out_height = height;
    return 0;
}
