#include "png_draw.h"

#include <stdlib.h>

#include "esp_heap_caps.h"

#include "dither.h"
#include "gfx.h"
#include "png_decode.h"

// Whole-image buffered path -- only reachable for Adam7-interlaced PNGs (see
// png_draw.h and the interlace check in png_draw_gs4 below); the streamed path
// used for the common non-interlaced case has no cap. Matches Inkplate10's
// physical resolution -- the only board this repo supports today (Phase 8 hasn't
// landed). Unlike bmp_draw.c's row-only scratch buffer, this is a full W*H image
// buffer, so headroom for boards not yet in this repo (e.g. Inkplate5v2's wider
// 1280px) would nearly double the allocation -- confirmed via HIL
// (docs/REFACTOR-PLAN.md Phase 7 step 21) that PSRAM is already tight enough for this
// exact size to matter (a 1600x1200 buffer failed to allocate alongside the framebuffer
// + MicroPython's own PSRAM-backed heap + the decoded file's Python-side buffer).
// Revisit this cap (and where it should live) when Phase 8 adds bigger boards. Only
// allocated when dithering is requested for an interlaced source.
#define PNG_DRAW_MAX_WIDTH 1200
#define PNG_DRAW_MAX_HEIGHT 825

typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    int dither;
    int kernel_type;
    uint8_t *luma; // [y * PNG_DRAW_MAX_WIDTH + x], only allocated when dither is set
    int oversized; // set if a pixel ever falls outside the PNG_DRAW_MAX_* cap
} png_draw_ctx_t;

static int rgba_to_luma(const uint8_t rgba[4])
{
    // ITU-R BT.601 luma, integer approximation.
    return (299 * rgba[0] + 587 * rgba[1] + 114 * rgba[2]) / 1000;
}

static void png_draw_pixel_cb(void *ctx_, uint32_t x, uint32_t y, const uint8_t rgba[4])
{
    png_draw_ctx_t *ctx = (png_draw_ctx_t *)ctx_;
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

    if (x >= PNG_DRAW_MAX_WIDTH || y >= PNG_DRAW_MAX_HEIGHT) {
        ctx->oversized = 1;
        return;
    }
    ctx->luma[y * PNG_DRAW_MAX_WIDTH + x] = (uint8_t)luma;
}

// Runs after decode completes: dithers the buffered luma in one guaranteed row-major
// pass and writes the result into fb. Falls back to plain (non-diffused) quantization
// if the error-diffusion context can't be allocated, so a transient OOM degrades to a
// banded image instead of a blank one.
static void png_dither_pass(png_draw_ctx_t *ctx, uint32_t w, uint32_t h)
{
    int inv_mask = ctx->display_mode == 0 ? 1 : 7;
    dither_ctx_t dctx;
    int have_dctx = dither_ctx_init(&dctx, (int)w, ctx->kernel_type) == 0;

    for (uint32_t y = 0; y < h; y++) {
        for (uint32_t x = 0; x < w; x++) {
            int gray = ctx->luma[y * PNG_DRAW_MAX_WIDTH + x];
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

// Streamed path for the common case (dither requested, source not Adam7-interlaced):
// pngle then delivers every pixel in one strictly raster-order sweep, so error
// diffusion can run inline per pixel exactly like bmp_draw_gs4 -- no whole-image (or
// even whole-row) buffer, and no PNG_DRAW_MAX_* cap. `width`/`height` come from
// png_peek_dimensions (read before decode starts, see png_draw_gs4) and size the
// diffusion error arrays + bound dither_diffuse_error's edge cutoff; the real
// png_decode() call below is still the authority on the image's actual dimensions --
// `oversized` catches the two ever disagreeing, same safety-net role as
// png_draw_palette_pixel_cb's identical check.
typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    uint32_t width, height;
    dither_ctx_t dctx;
    int have_dctx;
    int cur_row;   // -1 until the first pixel is seen
    int oversized; // set if a pixel ever falls outside width/height
} png_draw_stream_ctx_t;

static void png_draw_pixel_cb_stream(void *ctx_, uint32_t x, uint32_t y, const uint8_t rgba[4])
{
    png_draw_stream_ctx_t *ctx = (png_draw_stream_ctx_t *)ctx_;

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

int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height)
{
    if (dither) {
        uint32_t peek_w = 0, peek_h = 0;
        uint8_t peek_interlace = 0;
        // A failed peek (buf too short) or an interlaced source falls through to the
        // buffered path below, same "trust the real decode(), this is only a
        // fast-path peek" reasoning as png_peek_dimensions' own comment.
        if (png_peek_dimensions(buf, len, &peek_w, &peek_h) == 0 &&
            png_peek_interlace(buf, len, &peek_interlace) == 0 && peek_interlace == 0) {
            png_draw_stream_ctx_t ctx = {.fb = fb,
                                         .phys_w = phys_w,
                                         .phys_h = phys_h,
                                         .rotation = rotation,
                                         .display_mode = display_mode,
                                         .x0 = x0,
                                         .y0 = y0,
                                         .invert = invert,
                                         .width = peek_w,
                                         .height = peek_h,
                                         .have_dctx = 0,
                                         .cur_row = -1,
                                         .oversized = 0};
            // Falls back to plain (non-diffused) quantization if the error-diffusion
            // context can't be allocated -- same degrade-not-fail behavior as
            // png_dither_pass's have_dctx handling below.
            ctx.have_dctx = dither_ctx_init(&ctx.dctx, (int)peek_w, kernel_type) == 0;

            uint32_t width = 0, height = 0;
            int res = png_decode(buf, len, png_draw_pixel_cb_stream, &ctx, &width, &height);
            if (ctx.have_dctx) {
                dither_ctx_free(&ctx.dctx);
            }
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

    // Buffered path: dither==0 (order-independent, no diffusion state carried
    // between pixels, so this streams pixel-by-pixel below regardless of
    // interlacing), or dither==1 with an Adam7-interlaced source (or a peek that
    // couldn't even determine that).
    png_draw_ctx_t ctx = {.fb = fb,
                          .phys_w = phys_w,
                          .phys_h = phys_h,
                          .rotation = rotation,
                          .display_mode = display_mode,
                          .x0 = x0,
                          .y0 = y0,
                          .invert = invert,
                          .dither = dither,
                          .kernel_type = kernel_type,
                          .luma = NULL,
                          .oversized = 0};

    if (dither) {
        // Plain malloc() draws from ESP32's small internal-DRAM pool and fails outright
        // for a buffer this size -- this scratch buffer needs PSRAM explicitly, same as
        // the project's framebuffers (docs/REFACTOR-PLAN.md Phase 0 step 4).
        ctx.luma =
            heap_caps_malloc((size_t)PNG_DRAW_MAX_WIDTH * PNG_DRAW_MAX_HEIGHT, MALLOC_CAP_SPIRAM);
        if (ctx.luma == NULL) {
            return -1;
        }
    }

    uint32_t width = 0, height = 0;
    int res = png_decode(buf, len, png_draw_pixel_cb, &ctx, &width, &height);

    if (res == 0 && ctx.oversized) {
        res = -1;
    }
    if (res == 0 && dither) {
        png_dither_pass(&ctx, width, height);
    }
    if (dither) {
        heap_caps_free(ctx.luma);
    }
    if (res != 0) {
        return -1;
    }

    *out_width = width;
    *out_height = height;
    return 0;
}

// Buffer dims are the caller-supplied max_width/max_height, not a fixed constant --
// see jpeg_draw.c's identical param for the full HIL-informed history and why it's
// stored as RGB565 (dither_pack_rgb565/dither_unpack_rgb565) rather than RGB888.
typedef struct {
    int invert;
    int dither;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    png_draw_palette_cb write_pixel;
    void *cb_ctx;
    int max_width;
    int max_height;
    uint16_t *rgb; // [y * max_width + x], RGB565, only allocated when dither is set
} png_draw_palette_ctx_t;

static void png_draw_palette_pixel_cb(void *ctx_, uint32_t x, uint32_t y, const uint8_t rgba[4])
{
    png_draw_palette_ctx_t *ctx = (png_draw_palette_ctx_t *)ctx_;

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

    // png_draw_palette already rejected (via png_peek_dimensions) any image bigger
    // than max_width/max_height before decode started, but that peek reads IHDR by
    // hand rather than through pngle itself -- this bounds check is the real
    // safety net against the two ever disagreeing (out-of-bounds ctx->rgb write),
    // not just a defensive copy of the same check.
    if (x >= (uint32_t)ctx->max_width || y >= (uint32_t)ctx->max_height) {
        return;
    }
    size_t off = (size_t)y * (uint32_t)ctx->max_width + x;
    ctx->rgb[off] = dither_pack_rgb565(rgba[0], rgba[1], rgba[2]);
}

static void png_palette_dither_pass(png_draw_palette_ctx_t *ctx, uint32_t w, uint32_t h)
{
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

// Streamed path for the common case (dither requested, source not Adam7-interlaced) --
// same reasoning as png_draw_gs4's stream path above: pngle delivers every pixel in
// one strictly raster-order sweep when there's no interlacing, so RGB error diffusion
// can run inline per pixel -- no whole-image scratch buffer, and unlike the buffered
// path below, no max_width/max_height cap or caller-supplied scratch_rgb needed at
// all. `width`/`height` come from png_peek_dimensions (read before decode starts) and
// only size the diffusion error arrays + bound the edge cutoff; `oversized` is the
// same disagreement safety net as png_draw_palette_pixel_cb's identical check.
typedef struct {
    int invert;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    png_draw_palette_cb write_pixel;
    void *cb_ctx;
    uint32_t width, height;
    dither_rgb_ctx_t dctx;
    int have_dctx;
    int cur_row; // -1 until the first pixel is seen
    int oversized;
} png_draw_palette_stream_ctx_t;

static void png_draw_palette_pixel_cb_stream(void *ctx_, uint32_t x, uint32_t y,
                                             const uint8_t rgba[4])
{
    png_draw_palette_stream_ctx_t *ctx = (png_draw_palette_stream_ctx_t *)ctx_;

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

int png_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     png_draw_palette_cb write_pixel, void *cb_ctx, int max_width, int max_height,
                     uint16_t *scratch_rgb, size_t scratch_cap, uint32_t *out_width,
                     uint32_t *out_height)
{
    if (dither) {
        uint32_t peek_w = 0, peek_h = 0;
        uint8_t peek_interlace = 0;
        // A failed peek (buf too short) or an interlaced source falls through to the
        // buffered path below, same "trust the real decode(), this is only a
        // fast-path peek" reasoning as png_peek_dimensions' own comment.
        if (png_peek_dimensions(buf, len, &peek_w, &peek_h) == 0 &&
            png_peek_interlace(buf, len, &peek_interlace) == 0 && peek_interlace == 0) {
            png_draw_palette_stream_ctx_t ctx = {.invert = invert,
                                                 .kernel_type = kernel_type,
                                                 .palette = palette,
                                                 .palette_n = palette_n,
                                                 .write_pixel = write_pixel,
                                                 .cb_ctx = cb_ctx,
                                                 .width = peek_w,
                                                 .height = peek_h,
                                                 .have_dctx = 0,
                                                 .cur_row = -1,
                                                 .oversized = 0};
            // Falls back to plain (non-diffused) quantization if the error-diffusion
            // context can't be allocated -- same degrade-not-fail behavior as
            // png_palette_dither_pass's have_dctx handling below.
            ctx.have_dctx = dither_rgb_ctx_init(&ctx.dctx, (int)peek_w, kernel_type) == 0;

            uint32_t width = 0, height = 0;
            int res =
                png_decode(buf, len, png_draw_palette_pixel_cb_stream, &ctx, &width, &height);
            if (ctx.have_dctx) {
                dither_rgb_ctx_free(&ctx.dctx);
            }
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
    // png_draw_palette_pixel_cb regardless of interlacing), or dither==1 with an
    // Adam7-interlaced source (or a peek that couldn't even determine that) -- this
    // is the only case that still needs max_width/max_height and a caller-supplied
    // scratch_rgb buffer.
    png_draw_palette_ctx_t ctx = {.invert = invert,
                                  .dither = dither,
                                  .kernel_type = kernel_type,
                                  .palette = palette,
                                  .palette_n = palette_n,
                                  .write_pixel = write_pixel,
                                  .cb_ctx = cb_ctx,
                                  .max_width = max_width,
                                  .max_height = max_height,
                                  .rgb = NULL};

    if (dither) {
        // Reject an oversized image before paying for any decode work at all --
        // png_peek_dimensions reads IHDR directly (fixed byte offset every PNG
        // shares), without touching pngle. Source image bigger than
        // max_width/max_height (typically the panel's own physical size -- see
        // inkplatemodule.c's caller) can't be dithered: same distinct return code
        // as the missing-buffer case below, rather than silently redrawing without
        // dithering (docs/REFACTOR-PLAN.md Phase 10 step 32's followup: a silent
        // behavior change surprised users expecting dithered output, same
        // reasoning as jpeg_draw_palette's too-wide case). A failed peek (buf too
        // short) just falls through -- the real png_decode() call below reports
        // that as a decode error instead.
        uint32_t peek_w = 0, peek_h = 0;
        if (png_peek_dimensions(buf, len, &peek_w, &peek_h) == 0 &&
            (peek_w > (uint32_t)max_width || peek_h > (uint32_t)max_height)) {
            return -2;
        }

        // Caller-supplied buffer (docs/REFACTOR-PLAN.md Phase 10 step 32's followup)
        // -- see jpeg_draw_palette's identical comment for the HIL-confirmed
        // PSRAM-fragmentation reasoning for why this is no longer heap_caps_malloc'd
        // in here. Missing/undersized buffer can't dither either -- same distinct
        // return code as the oversized case above.
        if (scratch_rgb == NULL || scratch_cap < (size_t)max_width * (size_t)max_height) {
            return -2;
        }
        ctx.rgb = scratch_rgb;
    }

    uint32_t width = 0, height = 0;
    int res = png_decode(buf, len, png_draw_palette_pixel_cb, &ctx, &width, &height);

    if (res != 0) {
        return -1;
    }
    if (dither) {
        png_palette_dither_pass(&ctx, width, height);
    }

    *out_width = width;
    *out_height = height;
    return 0;
}
