/**
 * @file jpeg_draw.c
 * @brief JPEG decode-and-draw (with optional dithering) implementation.
 */
#include "jpeg_draw.h"

#include "jpeg_decode.h"
#include "jpeg_draw_core.h"

// Thin ESP-IDF-dependent wrapper: drives jpeg_decode() (rom/tjpgd.h, hardware-only) and forwards
// each decoded tile to jpeg_draw_core.c's pure dither/quantize/blit logic, which carries the
// actual test coverage (tests/test_jpeg_draw_core.c) since this file's own glue can't be
// host-compiled (jpeg_decode.h drags in the ROM decoder).

// Checked right after the JPEG header is parsed, before any MCU decoding starts. Width can
// only ever grow past JPEG_DRAW_CORE_BAND_MAX_W between here and the first tile, never
// shrink, so catching it this early (instead of waiting for a tile to overflow the band
// buffer) means an oversized image costs nothing beyond header parsing.
static int jpeg_draw_pre_cb(void *ctx_, uint32_t width, uint32_t height)
{
    (void)height;
    jpeg_draw_core_ctx_t *ctx = (jpeg_draw_core_ctx_t *)ctx_;
    return !ctx->dither || width <= JPEG_DRAW_CORE_BAND_MAX_W;
}

static int jpeg_draw_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_core_tile((jpeg_draw_core_ctx_t *)ctx_, tile->x, tile->y, tile->w, tile->h,
                        tile->rgb);
    return 1;
}

int jpeg_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                  uint32_t *out_width, uint32_t *out_height)
{
    jpeg_draw_core_ctx_t ctx;
    jpeg_draw_core_init(&ctx, fb, phys_w, phys_h, rotation, display_mode, x0, y0, invert, dither,
                        kernel_type);

    uint32_t width = 0, height = 0;
    int res = jpeg_decode(buf, len, jpeg_draw_pre_cb, jpeg_draw_tile_cb, &ctx, &width, &height);

    if (res == -2) {
        return -2; // too wide to dither -- caught before any MCU decode work happened
    }
    if (res != 0) {
        return -1;
    }

    if (dither) {
        jpeg_draw_core_flush(&ctx, (int)height);
        jpeg_draw_core_finish(&ctx);
    }

    *out_width = width;
    *out_height = height;
    return 0;
}

static int jpeg_draw_palette_pre_cb(void *ctx_, uint32_t width, uint32_t height)
{
    (void)height;
    jpeg_draw_core_palette_ctx_t *ctx = (jpeg_draw_core_palette_ctx_t *)ctx_;
    return !ctx->dither || width <= JPEG_DRAW_CORE_BAND_MAX_W;
}

static int jpeg_draw_palette_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_core_palette_tile((jpeg_draw_core_palette_ctx_t *)ctx_, tile->x, tile->y, tile->w,
                                tile->h, tile->rgb);
    return 1;
}

int jpeg_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                      const dither_palette_entry_t *palette, int palette_n,
                      jpeg_draw_palette_cb write_pixel, void *cb_ctx, uint32_t *out_width,
                      uint32_t *out_height)
{
    jpeg_draw_core_palette_ctx_t ctx;
    // jpeg_draw_palette_cb and jpeg_draw_core_palette_write_cb are structurally identical
    // function pointer types (void(*)(void*, int, int, int)) -- cast is safe, avoids the two
    // headers needing to share a typedef.
    jpeg_draw_core_palette_init(&ctx, invert, dither, kernel_type, palette, palette_n,
                                (jpeg_draw_core_palette_write_cb)write_pixel, cb_ctx);

    uint32_t width = 0, height = 0;
    int res = jpeg_decode(buf, len, jpeg_draw_palette_pre_cb, jpeg_draw_palette_tile_cb, &ctx,
                          &width, &height);

    if (res == -2) {
        return -2; // too wide to dither -- caught before any MCU decode work happened
    }
    if (res != 0) {
        return -1;
    }

    if (dither) {
        jpeg_draw_core_palette_flush(&ctx, (int)height);
        jpeg_draw_core_palette_finish(&ctx);
    }

    *out_width = width;
    *out_height = height;
    return 0;
}
