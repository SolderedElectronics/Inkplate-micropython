#include "png_draw_core.h"

#include "../display/gfx.h"
#include "dither.h"

static int rgba_to_luma(const uint8_t rgba[4])
{
    // ITU-R BT.601 luma, integer approximation.
    return (299 * rgba[0] + 587 * rgba[1] + 114 * rgba[2]) / 1000;
}

void png_draw_core_init(png_draw_core_ctx_t *ctx, uint8_t *fb, int phys_w, int phys_h,
                        int rotation, int display_mode, int x0, int y0, int invert, int dither,
                        int kernel_type, uint8_t *luma)
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
    ctx->luma = luma;
    ctx->oversized = 0;
}

void png_draw_core_pixel(png_draw_core_ctx_t *ctx, uint32_t x, uint32_t y, const uint8_t rgba[4])
{
    int luma = rgba_to_luma(rgba);

    if (!ctx->dither) {
        int inv_mask = ctx->display_mode == 0 ? 1 : 7;
        int recon;
        int level = dither_quantize(luma, ctx->display_mode, &recon);
        if (ctx->invert) {
            level ^= inv_mask;
        }
        gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, ctx->display_mode,
                      ctx->x0 + (int)x, ctx->y0 + (int)y, level);
        return;
    }

    if (x >= PNG_DRAW_CORE_MAX_WIDTH || y >= PNG_DRAW_CORE_MAX_HEIGHT) {
        ctx->oversized = 1;
        return;
    }
    ctx->luma[y * PNG_DRAW_CORE_MAX_WIDTH + x] = (uint8_t)luma;
}

void png_draw_core_dither_pass(png_draw_core_ctx_t *ctx, uint32_t w, uint32_t h)
{
    if (!ctx->dither) {
        return;
    }
    int inv_mask = ctx->display_mode == 0 ? 1 : 7;
    dither_ctx_t dctx;
    int have_dctx = dither_ctx_init(&dctx, (int)w, ctx->kernel_type) == 0;

    for (uint32_t y = 0; y < h; y++) {
        for (uint32_t x = 0; x < w; x++) {
            int gray = ctx->luma[y * PNG_DRAW_CORE_MAX_WIDTH + x];
            int level, recon;
            if (have_dctx) {
                gray = dither_apply_error(&dctx, (int)x, gray);
                level = dither_quantize(gray, ctx->display_mode, &recon);
                dither_diffuse_error(&dctx, (int)x, (int)y, (int)w, (int)h, gray - recon);
            } else {
                level = dither_quantize(gray, ctx->display_mode, &recon);
            }
            if (ctx->invert) {
                level ^= inv_mask;
            }
            gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, ctx->display_mode,
                          ctx->x0 + (int)x, ctx->y0 + (int)y, level);
        }
        if (have_dctx) {
            dither_row_advance(&dctx);
        }
    }
    if (have_dctx) {
        dither_ctx_free(&dctx);
    }
}

void png_draw_core_stream_init(png_draw_core_stream_ctx_t *ctx, uint8_t *fb, int phys_w,
                               int phys_h, int rotation, int display_mode, int x0, int y0,
                               int invert, uint32_t width, uint32_t height, int kernel_type)
{
    ctx->fb = fb;
    ctx->phys_w = phys_w;
    ctx->phys_h = phys_h;
    ctx->rotation = rotation;
    ctx->display_mode = display_mode;
    ctx->x0 = x0;
    ctx->y0 = y0;
    ctx->invert = invert;
    ctx->width = width;
    ctx->height = height;
    ctx->cur_row = -1;
    ctx->oversized = 0;
    // Falls back to plain (non-diffused) quantization if allocation fails -- same
    // degrade-not-fail behavior as png_draw_core_dither_pass's have_dctx handling.
    ctx->have_dctx = dither_ctx_init(&ctx->dctx, (int)width, kernel_type) == 0;
}

void png_draw_core_pixel_stream(png_draw_core_stream_ctx_t *ctx, uint32_t x, uint32_t y,
                                const uint8_t rgba[4])
{
    if (x >= ctx->width || y >= ctx->height) {
        ctx->oversized = 1;
        return;
    }

    if (ctx->have_dctx && (int)y != ctx->cur_row) {
        if (ctx->cur_row >= 0) {
            dither_row_advance(&ctx->dctx);
        }
        ctx->cur_row = (int)y;
    }

    int inv_mask = ctx->display_mode == 0 ? 1 : 7;
    int gray = rgba_to_luma(rgba);
    int level, recon;
    if (ctx->have_dctx) {
        gray = dither_apply_error(&ctx->dctx, (int)x, gray);
        level = dither_quantize(gray, ctx->display_mode, &recon);
        dither_diffuse_error(&ctx->dctx, (int)x, (int)y, (int)ctx->width, (int)ctx->height,
                             gray - recon);
    } else {
        level = dither_quantize(gray, ctx->display_mode, &recon);
    }
    if (ctx->invert) {
        level ^= inv_mask;
    }
    gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, ctx->display_mode,
                  ctx->x0 + (int)x, ctx->y0 + (int)y, level);
}

void png_draw_core_stream_finish(png_draw_core_stream_ctx_t *ctx)
{
    if (ctx->have_dctx) {
        dither_ctx_free(&ctx->dctx);
    }
}

void png_draw_core_palette_init(png_draw_core_palette_ctx_t *ctx, int invert, int dither,
                                int kernel_type, const dither_palette_entry_t *palette,
                                int palette_n, png_draw_core_palette_write_cb write_pixel,
                                void *cb_ctx, int max_width, int max_height, uint16_t *rgb)
{
    ctx->invert = invert;
    ctx->dither = dither;
    ctx->kernel_type = kernel_type;
    ctx->palette = palette;
    ctx->palette_n = palette_n;
    ctx->write_pixel = write_pixel;
    ctx->cb_ctx = cb_ctx;
    ctx->max_width = max_width;
    ctx->max_height = max_height;
    ctx->rgb = rgb;
}

void png_draw_core_palette_pixel(png_draw_core_palette_ctx_t *ctx, uint32_t x, uint32_t y,
                                 const uint8_t rgba[4])
{
    if (!ctx->dither) {
        int recon_r, recon_g, recon_b;
        int value = dither_quantize_palette(rgba[0], rgba[1], rgba[2], ctx->palette,
                                            ctx->palette_n, &recon_r, &recon_g, &recon_b);
        if (ctx->invert) {
            value = dither_invert_palette_bw(value, ctx->palette, ctx->palette_n);
        }
        ctx->write_pixel(ctx->cb_ctx, (int)x, (int)y, value);
        return;
    }

    // png_draw_palette already rejected (via png_peek_dimensions) any image bigger than
    // max_width/max_height before decode started, but that peek reads IHDR by hand rather
    // than through pngle itself -- this bounds check is the real safety net against the
    // two ever disagreeing (out-of-bounds ctx->rgb write), not just a defensive copy.
    if (x >= (uint32_t)ctx->max_width || y >= (uint32_t)ctx->max_height) {
        return;
    }
    size_t off = (size_t)y * (uint32_t)ctx->max_width + x;
    ctx->rgb[off] = dither_pack_rgb565(rgba[0], rgba[1], rgba[2]);
}

void png_draw_core_palette_dither_pass(png_draw_core_palette_ctx_t *ctx, uint32_t w, uint32_t h)
{
    if (!ctx->dither) {
        return;
    }
    dither_rgb_ctx_t dctx;
    int have_dctx = dither_rgb_ctx_init(&dctx, (int)w, ctx->kernel_type) == 0;

    for (uint32_t y = 0; y < h; y++) {
        for (uint32_t x = 0; x < w; x++) {
            size_t off = (size_t)y * (uint32_t)ctx->max_width + x;
            int r, g, b;
            dither_unpack_rgb565(ctx->rgb[off], &r, &g, &b);
            int value, recon_r, recon_g, recon_b;
            if (have_dctx) {
                dither_apply_error_rgb(&dctx, (int)x, &r, &g, &b);
                value = dither_quantize_palette(r, g, b, ctx->palette, ctx->palette_n, &recon_r,
                                                &recon_g, &recon_b);
                dither_diffuse_error_rgb(&dctx, (int)x, (int)y, (int)w, (int)h, r - recon_r,
                                         g - recon_g, b - recon_b);
            } else {
                value = dither_quantize_palette(r, g, b, ctx->palette, ctx->palette_n, &recon_r,
                                                &recon_g, &recon_b);
            }
            if (ctx->invert) {
                value = dither_invert_palette_bw(value, ctx->palette, ctx->palette_n);
            }
            ctx->write_pixel(ctx->cb_ctx, (int)x, (int)y, value);
        }
        if (have_dctx) {
            dither_row_advance_rgb(&dctx);
        }
    }
    if (have_dctx) {
        dither_rgb_ctx_free(&dctx);
    }
}

void png_draw_core_palette_stream_init(png_draw_core_palette_stream_ctx_t *ctx, int invert,
                                       int kernel_type, const dither_palette_entry_t *palette,
                                       int palette_n, png_draw_core_palette_write_cb write_pixel,
                                       void *cb_ctx, uint32_t width, uint32_t height)
{
    ctx->invert = invert;
    ctx->kernel_type = kernel_type;
    ctx->palette = palette;
    ctx->palette_n = palette_n;
    ctx->write_pixel = write_pixel;
    ctx->cb_ctx = cb_ctx;
    ctx->width = width;
    ctx->height = height;
    ctx->cur_row = -1;
    ctx->oversized = 0;
    // Same degrade-not-fail behavior as png_draw_core_palette_dither_pass's have_dctx
    // handling.
    ctx->have_dctx = dither_rgb_ctx_init(&ctx->dctx, (int)width, kernel_type) == 0;
}

void png_draw_core_palette_pixel_stream(png_draw_core_palette_stream_ctx_t *ctx, uint32_t x,
                                        uint32_t y, const uint8_t rgba[4])
{
    if (x >= ctx->width || y >= ctx->height) {
        ctx->oversized = 1;
        return;
    }

    if (ctx->have_dctx && (int)y != ctx->cur_row) {
        if (ctx->cur_row >= 0) {
            dither_row_advance_rgb(&ctx->dctx);
        }
        ctx->cur_row = (int)y;
    }

    int r = rgba[0], g = rgba[1], b = rgba[2];
    int value, recon_r, recon_g, recon_b;
    if (ctx->have_dctx) {
        dither_apply_error_rgb(&ctx->dctx, (int)x, &r, &g, &b);
        value = dither_quantize_palette(r, g, b, ctx->palette, ctx->palette_n, &recon_r, &recon_g,
                                        &recon_b);
        dither_diffuse_error_rgb(&ctx->dctx, (int)x, (int)y, (int)ctx->width, (int)ctx->height,
                                 r - recon_r, g - recon_g, b - recon_b);
    } else {
        value = dither_quantize_palette(r, g, b, ctx->palette, ctx->palette_n, &recon_r, &recon_g,
                                        &recon_b);
    }
    if (ctx->invert) {
        value = dither_invert_palette_bw(value, ctx->palette, ctx->palette_n);
    }
    ctx->write_pixel(ctx->cb_ctx, (int)x, (int)y, value);
}

void png_draw_core_palette_stream_finish(png_draw_core_palette_stream_ctx_t *ctx)
{
    if (ctx->have_dctx) {
        dither_rgb_ctx_free(&ctx->dctx);
    }
}
