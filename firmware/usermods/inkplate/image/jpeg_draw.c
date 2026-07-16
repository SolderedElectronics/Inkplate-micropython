#include "jpeg_draw.h"

#include <stdlib.h>

#include "esp_heap_caps.h"

#include "dither.h"
#include "../display/gfx.h"
#include "jpeg_decode.h"

// Row-band scratch buffers, shared by the grayscale path below and the palette path
// further down. tjpgd (jpeg_decode.c) delivers MCU tiles in strict row-band raster
// order -- jpeg_decode.h's own contract ("invoked once per decoded MCU tile, in
// raster order") means every tile spanning the full image width for a given MCU
// row-band arrives before the next band down starts. Unlike PNG's Adam7 interlacing
// (png_draw.c), which sweeps the whole image in up to 7 non-monotonic passes and
// genuinely needs a whole-image buffer, JPEG only ever needs one band's worth of
// pixels buffered at a time. JPEG_DRAW_BAND_MAX_W matches this codebase's existing
// "typical photo" width floor; JPEG_DRAW_MCU_MAX_H is the largest MCU height tjpgd
// can produce (msy <= 2 blocks of 8px per rom/tjpgd.h -- standard JPEG subsampling
// never exceeds a 2x2-block MCU). Static buffers this small (~19KB luma, ~38KB
// RGB565) need no allocation at all, so they can never hit the PSRAM fragmentation a
// whole-image buffer did on real Inkplate6COLOR hardware (docs/REFACTOR-PLAN.md
// Phase 10 step 32's followup) -- there's nothing here to fail. Height is unbounded
// (bands are processed and discarded as decode progresses); only width is capped, by
// jpeg_draw_pre_cb/jpeg_draw_palette_pre_cb rejecting before any MCU decode starts.
#define JPEG_DRAW_BAND_MAX_W 1200
#define JPEG_DRAW_MCU_MAX_H 16
static uint8_t jpeg_draw_band_luma[JPEG_DRAW_BAND_MAX_W * JPEG_DRAW_MCU_MAX_H];

typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    int dither;
    int kernel_type;
    // Row-band dithering state -- see jpeg_draw_band_luma above.
    int band_y0; // image row where the buffered band starts, -1 if nothing buffered
    int band_h;  // valid rows in the band buffer (this band's MCU tile height)
    int band_w;  // widest x+w seen so far this band -- equals the real image width
                 // once a band's tiles have all arrived
    dither_ctx_t dctx;
    // -1: not yet attempted (band_w, needed to size dctx, isn't known until the
    // first band completes); 0: attempted and failed (degrade to non-diffused
    // quantization); 1: ready.
    int have_dctx;
} jpeg_draw_ctx_t;

static void jpeg_draw_tile_immediate(jpeg_draw_ctx_t *ctx, const jpeg_tile_t *tile)
{
    int inv_mask = ctx->display_mode == 0 ? 1 : 7;
    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            // ITU-R BT.601 luma, integer approximation.
            int luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            int recon;
            int level = dither_quantize(luma, ctx->display_mode, &recon);
            if (ctx->invert) {
                level ^= inv_mask;
            }
            gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, ctx->display_mode,
                          ctx->x0 + (int)(tile->x + tx), ctx->y0 + (int)(tile->y + ty), level);
        }
    }
}

// Checked right after the JPEG header is parsed, before any MCU decoding starts --
// see jpeg_draw_gs4's call site. Width can only ever grow past JPEG_DRAW_BAND_MAX_W
// between here and the first tile, never shrink, so catching it this early (instead
// of waiting for a tile to overflow the band buffer) means an oversized image costs
// nothing beyond header parsing.
static int jpeg_draw_pre_cb(void *ctx_, uint32_t width, uint32_t height)
{
    (void)height;
    jpeg_draw_ctx_t *ctx = (jpeg_draw_ctx_t *)ctx_;
    return !ctx->dither || width <= JPEG_DRAW_BAND_MAX_W;
}

// Dithers+writes the currently-buffered band (a no-op if nothing is buffered).
// `draw_height` bounds bottom-edge error diffusion (dither_diffuse_error) -- the real
// image height isn't known until decode completes, so every mid-decode flush
// (triggered by the next band's first tile arriving) passes a large sentinel: this
// is never actually the image's last row, so an overly generous bound only ever
// avoids an incorrect early cutoff. The final flush (jpeg_draw_gs4, after decode
// completes) passes the real height for a correct bottom edge. Same shape as
// jpeg_draw_palette_flush_band below, scalar luma instead of RGB565.
static void jpeg_draw_flush_band(jpeg_draw_ctx_t *ctx, int draw_height)
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
            int gray = jpeg_draw_band_luma[ty * JPEG_DRAW_BAND_MAX_W + x];
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

static int jpeg_draw_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_ctx_t *ctx = (jpeg_draw_ctx_t *)ctx_;

    if (!ctx->dither) {
        jpeg_draw_tile_immediate(ctx, tile);
        return 1;
    }

    if (ctx->band_y0 >= 0 && tile->y != (uint32_t)ctx->band_y0) {
        // New row-band started: every tile for the previous band (full image width)
        // has already arrived -- tjpgd's raster tile order guarantees this -- so
        // it's safe to dither+flush it now, before this tile's data overwrites it.
        jpeg_draw_flush_band(ctx, INT32_MAX);
    }
    if (ctx->band_y0 < 0) {
        ctx->band_y0 = (int)tile->y;
        ctx->band_h = (int)tile->h;
        ctx->band_w = 0;
    }

    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            uint32_t luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            size_t off = (size_t)ty * JPEG_DRAW_BAND_MAX_W + (tile->x + tx);
            jpeg_draw_band_luma[off] = (uint8_t)luma;
        }
    }
    int band_right = (int)(tile->x + tile->w);
    if (band_right > ctx->band_w) {
        ctx->band_w = band_right;
    }
    return 1;
}

int jpeg_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                  int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                  uint32_t *out_width, uint32_t *out_height)
{
    jpeg_draw_ctx_t ctx = {.fb = fb,
                           .phys_w = phys_w,
                           .phys_h = phys_h,
                           .rotation = rotation,
                           .display_mode = display_mode,
                           .x0 = x0,
                           .y0 = y0,
                           .invert = invert,
                           .dither = dither,
                           .kernel_type = kernel_type,
                           .band_y0 = -1,
                           .band_h = 0,
                           .band_w = 0,
                           .have_dctx = -1};

    uint32_t width = 0, height = 0;
    int res = jpeg_decode(buf, len, jpeg_draw_pre_cb, jpeg_draw_tile_cb, &ctx, &width, &height);

    if (res == -2) {
        return -2; // too wide to dither -- caught before any MCU decode work happened
    }
    if (res != 0) {
        return -1;
    }

    if (dither) {
        jpeg_draw_flush_band(&ctx, (int)height);
        if (ctx.have_dctx == 1) {
            dither_ctx_free(&ctx.dctx);
        }
    }

    *out_width = width;
    *out_height = height;
    return 0;
}

static uint16_t jpeg_palette_band_rgb[JPEG_DRAW_BAND_MAX_W * JPEG_DRAW_MCU_MAX_H];

typedef struct {
    int invert;
    int dither;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    jpeg_draw_palette_cb write_pixel;
    void *cb_ctx;
    // Row-band dithering state -- see jpeg_palette_band_rgb above.
    int band_y0; // image row where the buffered band starts, -1 if nothing buffered
    int band_h;  // valid rows in the band buffer (this band's MCU tile height)
    int band_w;  // widest x+w seen so far this band -- equals the real image width
                 // once a band's tiles have all arrived
    dither_rgb_ctx_t dctx;
    // -1: not yet attempted (band_w, needed to size dctx, isn't known until the
    // first band completes); 0: attempted and failed (degrade to non-diffused
    // quantization, same fallback philosophy as the grayscale path's luma buffer);
    // 1: ready.
    int have_dctx;
} jpeg_draw_palette_ctx_t;

static void jpeg_draw_palette_tile_immediate(jpeg_draw_palette_ctx_t *ctx,
                                             const jpeg_tile_t *tile)
{
    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            int recon_r, recon_g, recon_b;
            int value = dither_quantize_palette(px[0], px[1], px[2], ctx->palette, ctx->palette_n,
                                                &recon_r, &recon_g, &recon_b);
            if (ctx->invert) {
                value = dither_invert_palette_bw(value, ctx->palette, ctx->palette_n);
            }
            ctx->write_pixel(ctx->cb_ctx, (int)(tile->x + tx), (int)(tile->y + ty), value);
        }
    }
}

// Dithers+writes the currently-buffered band (a no-op if nothing is buffered).
// `draw_height` bounds bottom-edge error diffusion (dither_diffuse_error_rgb) -- the
// real image height isn't known until decode completes, so every mid-decode flush
// (triggered by the next band's first tile arriving) passes a large sentinel: this
// is never actually the image's last row, so an overly generous bound only ever
// avoids an incorrect early cutoff. The final flush (jpeg_draw_palette, after decode
// completes) passes the real height for a correct bottom edge.
static void jpeg_draw_palette_flush_band(jpeg_draw_palette_ctx_t *ctx, int draw_height)
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
            dither_unpack_rgb565(jpeg_palette_band_rgb[ty * JPEG_DRAW_BAND_MAX_W + x], &r, &g,
                                 &b);
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

// Checked right after the JPEG header is parsed, before any MCU decoding starts --
// see jpeg_draw_palette's call site. Width can only ever grow past
// JPEG_DRAW_BAND_MAX_W between here and the first tile, never shrink, so
// catching it this early (instead of waiting for a tile to overflow the band
// buffer) means an oversized image costs nothing beyond header parsing.
static int jpeg_draw_palette_pre_cb(void *ctx_, uint32_t width, uint32_t height)
{
    (void)height;
    jpeg_draw_palette_ctx_t *ctx = (jpeg_draw_palette_ctx_t *)ctx_;
    return !ctx->dither || width <= JPEG_DRAW_BAND_MAX_W;
}

static int jpeg_draw_palette_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_palette_ctx_t *ctx = (jpeg_draw_palette_ctx_t *)ctx_;

    if (!ctx->dither) {
        jpeg_draw_palette_tile_immediate(ctx, tile);
        return 1;
    }

    if (ctx->band_y0 >= 0 && tile->y != (uint32_t)ctx->band_y0) {
        // New row-band started: every tile for the previous band (full image width)
        // has already arrived -- tjpgd's raster tile order guarantees this -- so
        // it's safe to dither+flush it now, before this tile's data overwrites it.
        jpeg_draw_palette_flush_band(ctx, INT32_MAX);
    }
    if (ctx->band_y0 < 0) {
        ctx->band_y0 = (int)tile->y;
        ctx->band_h = (int)tile->h;
        ctx->band_w = 0;
    }

    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            size_t off = (size_t)ty * JPEG_DRAW_BAND_MAX_W + (tile->x + tx);
            jpeg_palette_band_rgb[off] = dither_pack_rgb565(px[0], px[1], px[2]);
        }
    }
    int band_right = (int)(tile->x + tile->w);
    if (band_right > ctx->band_w) {
        ctx->band_w = band_right;
    }
    return 1;
}

int jpeg_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                      const dither_palette_entry_t *palette, int palette_n,
                      jpeg_draw_palette_cb write_pixel, void *cb_ctx, uint32_t *out_width,
                      uint32_t *out_height)
{
    jpeg_draw_palette_ctx_t ctx = {.invert = invert,
                                   .dither = dither,
                                   .kernel_type = kernel_type,
                                   .palette = palette,
                                   .palette_n = palette_n,
                                   .write_pixel = write_pixel,
                                   .cb_ctx = cb_ctx,
                                   .band_y0 = -1,
                                   .band_h = 0,
                                   .band_w = 0,
                                   .have_dctx = -1};

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
        jpeg_draw_palette_flush_band(&ctx, (int)height);
        if (ctx.have_dctx == 1) {
            dither_rgb_ctx_free(&ctx.dctx);
        }
    }

    *out_width = width;
    *out_height = height;
    return 0;
}
