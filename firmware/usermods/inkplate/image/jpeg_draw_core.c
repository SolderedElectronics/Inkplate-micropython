#include "jpeg_draw_core.h"

#include "../display/gfx.h"
#include "dither.h"

// Row-band scratch buffers, shared by the grayscale path below and the palette path
// further down -- see jpeg_draw_core.h's band-buffer comment and jpeg_draw.c for why a
// band (not a whole-image buffer) is enough for JPEG's raster-order MCU tiles. Static
// singletons: only one draw operation is ever in flight at a time (same assumption the
// pre-split jpeg_draw.c made implicitly).
static uint8_t jpeg_draw_band_luma[JPEG_DRAW_CORE_BAND_MAX_W * JPEG_DRAW_CORE_MCU_MAX_H];
static uint16_t jpeg_palette_band_rgb[JPEG_DRAW_CORE_BAND_MAX_W * JPEG_DRAW_CORE_MCU_MAX_H];

void jpeg_draw_core_init(jpeg_draw_core_ctx_t *ctx, uint8_t *fb, int phys_w, int phys_h,
                         int rotation, int display_mode, int x0, int y0, int invert, int dither,
                         int kernel_type)
{
    ctx->fb = fb;
    ctx->phys_w = phys_w;
    ctx->phys_h = phys_h;
    ctx->rotation = rotation;
    ctx->display_mode = display_mode;
    ctx->x0 = x0;
    ctx->y0 = y0;
    ctx->invert = invert;
    ctx->dither = dither;
    ctx->kernel_type = kernel_type;
    ctx->band_y0 = -1;
    ctx->band_h = 0;
    ctx->band_w = 0;
    ctx->have_dctx = -1;
}

static void jpeg_draw_core_tile_immediate(jpeg_draw_core_ctx_t *ctx, uint32_t tile_x,
                                          uint32_t tile_y, uint32_t tile_w, uint32_t tile_h,
                                          const uint8_t *rgb)
{
    int inv_mask = ctx->display_mode == 0 ? 1 : 7;
    for (uint32_t ty = 0; ty < tile_h; ty++) {
        for (uint32_t tx = 0; tx < tile_w; tx++) {
            const uint8_t *px = rgb + (ty * tile_w + tx) * 3;
            // ITU-R BT.601 luma, integer approximation.
            int luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            int recon;
            int level = dither_quantize(luma, ctx->display_mode, &recon);
            if (ctx->invert) {
                level ^= inv_mask;
            }
            gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, ctx->display_mode,
                          ctx->x0 + (int)(tile_x + tx), ctx->y0 + (int)(tile_y + ty), level);
        }
    }
}

void jpeg_draw_core_flush(jpeg_draw_core_ctx_t *ctx, int draw_height)
{
    if (ctx->band_y0 < 0) {
        return;
    }
    if (ctx->have_dctx < 0) {
        ctx->have_dctx = dither_ctx_init(&ctx->dctx, ctx->band_w, ctx->kernel_type) == 0;
    }
    int inv_mask = ctx->display_mode == 0 ? 1 : 7;

    for (int ty = 0; ty < ctx->band_h; ty++) {
        int y = ctx->band_y0 + ty;
        for (int x = 0; x < ctx->band_w; x++) {
            int gray = jpeg_draw_band_luma[ty * JPEG_DRAW_CORE_BAND_MAX_W + x];
            int level, recon;
            if (ctx->have_dctx) {
                gray = dither_apply_error(&ctx->dctx, x, gray);
                level = dither_quantize(gray, ctx->display_mode, &recon);
                dither_diffuse_error(&ctx->dctx, x, y, ctx->band_w, draw_height, gray - recon);
            } else {
                level = dither_quantize(gray, ctx->display_mode, &recon);
            }
            if (ctx->invert) {
                level ^= inv_mask;
            }
            gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, ctx->display_mode,
                          ctx->x0 + x, ctx->y0 + y, level);
        }
        if (ctx->have_dctx) {
            dither_row_advance(&ctx->dctx);
        }
    }
    ctx->band_y0 = -1;
}

void jpeg_draw_core_finish(jpeg_draw_core_ctx_t *ctx)
{
    if (ctx->have_dctx == 1) {
        dither_ctx_free(&ctx->dctx);
    }
}

void jpeg_draw_core_tile(jpeg_draw_core_ctx_t *ctx, uint32_t tile_x, uint32_t tile_y,
                         uint32_t tile_w, uint32_t tile_h, const uint8_t *rgb)
{
    if (!ctx->dither) {
        jpeg_draw_core_tile_immediate(ctx, tile_x, tile_y, tile_w, tile_h, rgb);
        return;
    }

    if (ctx->band_y0 >= 0 && tile_y != (uint32_t)ctx->band_y0) {
        // New row-band started: every tile for the previous band (full image width) has
        // already arrived -- tjpgd's raster tile order guarantees this -- so it's safe to
        // dither+flush it now, before this tile's data overwrites it.
        jpeg_draw_core_flush(ctx, INT32_MAX);
    }
    if (ctx->band_y0 < 0) {
        ctx->band_y0 = (int)tile_y;
        ctx->band_h = (int)tile_h;
        ctx->band_w = 0;
    }

    for (uint32_t ty = 0; ty < tile_h; ty++) {
        for (uint32_t tx = 0; tx < tile_w; tx++) {
            const uint8_t *px = rgb + (ty * tile_w + tx) * 3;
            uint32_t luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            size_t off = (size_t)ty * JPEG_DRAW_CORE_BAND_MAX_W + (tile_x + tx);
            jpeg_draw_band_luma[off] = (uint8_t)luma;
        }
    }
    int band_right = (int)(tile_x + tile_w);
    if (band_right > ctx->band_w) {
        ctx->band_w = band_right;
    }
}

void jpeg_draw_core_palette_init(jpeg_draw_core_palette_ctx_t *ctx, int invert, int dither,
                                 int kernel_type, const dither_palette_entry_t *palette,
                                 int palette_n, jpeg_draw_core_palette_write_cb write_pixel,
                                 void *cb_ctx)
{
    ctx->invert = invert;
    ctx->dither = dither;
    ctx->kernel_type = kernel_type;
    ctx->palette = palette;
    ctx->palette_n = palette_n;
    ctx->write_pixel = write_pixel;
    ctx->cb_ctx = cb_ctx;
    ctx->band_y0 = -1;
    ctx->band_h = 0;
    ctx->band_w = 0;
    ctx->have_dctx = -1;
}

static void jpeg_draw_core_palette_tile_immediate(jpeg_draw_core_palette_ctx_t *ctx,
                                                  uint32_t tile_x, uint32_t tile_y,
                                                  uint32_t tile_w, uint32_t tile_h,
                                                  const uint8_t *rgb)
{
    for (uint32_t ty = 0; ty < tile_h; ty++) {
        for (uint32_t tx = 0; tx < tile_w; tx++) {
            const uint8_t *px = rgb + (ty * tile_w + tx) * 3;
            int recon_r, recon_g, recon_b;
            int value = dither_quantize_palette(px[0], px[1], px[2], ctx->palette, ctx->palette_n,
                                                &recon_r, &recon_g, &recon_b);
            if (ctx->invert) {
                value = dither_invert_palette_bw(value, ctx->palette, ctx->palette_n);
            }
            ctx->write_pixel(ctx->cb_ctx, (int)(tile_x + tx), (int)(tile_y + ty), value);
        }
    }
}

void jpeg_draw_core_palette_flush(jpeg_draw_core_palette_ctx_t *ctx, int draw_height)
{
    if (ctx->band_y0 < 0) {
        return;
    }
    if (ctx->have_dctx < 0) {
        ctx->have_dctx = dither_rgb_ctx_init(&ctx->dctx, ctx->band_w, ctx->kernel_type) == 0;
    }

    for (int ty = 0; ty < ctx->band_h; ty++) {
        int y = ctx->band_y0 + ty;
        for (int x = 0; x < ctx->band_w; x++) {
            int r, g, b;
            dither_unpack_rgb565(jpeg_palette_band_rgb[ty * JPEG_DRAW_CORE_BAND_MAX_W + x], &r,
                                 &g, &b);
            int value, recon_r, recon_g, recon_b;
            if (ctx->have_dctx) {
                dither_apply_error_rgb(&ctx->dctx, x, &r, &g, &b);
                value = dither_quantize_palette(r, g, b, ctx->palette, ctx->palette_n, &recon_r,
                                                &recon_g, &recon_b);
                dither_diffuse_error_rgb(&ctx->dctx, x, y, ctx->band_w, draw_height, r - recon_r,
                                         g - recon_g, b - recon_b);
            } else {
                value = dither_quantize_palette(r, g, b, ctx->palette, ctx->palette_n, &recon_r,
                                                &recon_g, &recon_b);
            }
            if (ctx->invert) {
                value = dither_invert_palette_bw(value, ctx->palette, ctx->palette_n);
            }
            ctx->write_pixel(ctx->cb_ctx, x, y, value);
        }
        if (ctx->have_dctx) {
            dither_row_advance_rgb(&ctx->dctx);
        }
    }
    ctx->band_y0 = -1;
}

void jpeg_draw_core_palette_finish(jpeg_draw_core_palette_ctx_t *ctx)
{
    if (ctx->have_dctx == 1) {
        dither_rgb_ctx_free(&ctx->dctx);
    }
}

void jpeg_draw_core_palette_tile(jpeg_draw_core_palette_ctx_t *ctx, uint32_t tile_x,
                                 uint32_t tile_y, uint32_t tile_w, uint32_t tile_h,
                                 const uint8_t *rgb)
{
    if (!ctx->dither) {
        jpeg_draw_core_palette_tile_immediate(ctx, tile_x, tile_y, tile_w, tile_h, rgb);
        return;
    }

    if (ctx->band_y0 >= 0 && tile_y != (uint32_t)ctx->band_y0) {
        // Same "previous band fully arrived" reasoning as jpeg_draw_core_tile above.
        jpeg_draw_core_palette_flush(ctx, INT32_MAX);
    }
    if (ctx->band_y0 < 0) {
        ctx->band_y0 = (int)tile_y;
        ctx->band_h = (int)tile_h;
        ctx->band_w = 0;
    }

    for (uint32_t ty = 0; ty < tile_h; ty++) {
        for (uint32_t tx = 0; tx < tile_w; tx++) {
            const uint8_t *px = rgb + (ty * tile_w + tx) * 3;
            size_t off = (size_t)ty * JPEG_DRAW_CORE_BAND_MAX_W + (tile_x + tx);
            jpeg_palette_band_rgb[off] = dither_pack_rgb565(px[0], px[1], px[2]);
        }
    }
    int band_right = (int)(tile_x + tile_w);
    if (band_right > ctx->band_w) {
        ctx->band_w = band_right;
    }
}
