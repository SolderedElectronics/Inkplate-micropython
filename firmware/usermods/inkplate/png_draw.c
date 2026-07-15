#include "png_draw.h"

#include <stdlib.h>

#include "esp_heap_caps.h"

#include "dither.h"
#include "gfx.h"
#include "png_decode.h"

// Matches Inkplate10's physical resolution -- the only board this repo supports today
// (Phase 8 hasn't landed). Unlike bmp_draw.c's row-only scratch buffer, this is a full
// W*H image buffer, so headroom for boards not yet in this repo (e.g. Inkplate5v2's
// wider 1280px) would nearly double the allocation -- confirmed via HIL
// (docs/REFACTOR-PLAN.md Phase 7 step 21) that PSRAM is already tight enough for this
// exact size to matter (a 1600x1200 buffer failed to allocate alongside the framebuffer
// + MicroPython's own PSRAM-backed heap + the decoded file's Python-side buffer).
// Revisit this cap (and where it should live) when Phase 8 adds bigger boards. Only
// allocated when dithering is requested.
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

int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height)
{
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
    int oversized; // set if a pixel ever falls outside the max_width/max_height cap
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

    if (x >= (uint32_t)ctx->max_width || y >= (uint32_t)ctx->max_height) {
        ctx->oversized = 1;
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

int png_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     png_draw_palette_cb write_pixel, void *cb_ctx, int max_width, int max_height,
                     uint32_t *out_width, uint32_t *out_height)
{
    png_draw_palette_ctx_t ctx = {.invert = invert,
                                  .dither = dither,
                                  .kernel_type = kernel_type,
                                  .palette = palette,
                                  .palette_n = palette_n,
                                  .write_pixel = write_pixel,
                                  .cb_ctx = cb_ctx,
                                  .max_width = max_width,
                                  .max_height = max_height,
                                  .rgb = NULL,
                                  .oversized = 0};

    if (dither) {
        ctx.rgb = heap_caps_malloc((size_t)max_width * (size_t)max_height * sizeof(uint16_t),
                                   MALLOC_CAP_SPIRAM);
        if (ctx.rgb == NULL) {
            // Same graceful degrade as jpeg_draw_palette -- see its identical comment
            // for the HIL-confirmed PSRAM-fragmentation reasoning.
            dither = 0;
            ctx.dither = 0;
        }
    }

    uint32_t width = 0, height = 0;
    int res = png_decode(buf, len, png_draw_palette_pixel_cb, &ctx, &width, &height);

    if (res == 0 && ctx.oversized && dither) {
        // Source image is bigger than max_width/max_height (typically the panel's
        // own physical size -- see inkplatemodule.c's caller), so the dither buffer
        // never held the whole image. Retry the whole decode from scratch with
        // dithering off instead of failing outright -- png_decode has no state that
        // survives across calls, so this is a clean full redo, not a half-drawn
        // image (same reasoning as jpeg_draw_palette's identical retry).
        heap_caps_free(ctx.rgb);
        ctx.rgb = NULL;
        dither = 0;
        ctx.dither = 0;
        ctx.oversized = 0;
        width = 0;
        height = 0;
        res = png_decode(buf, len, png_draw_palette_pixel_cb, &ctx, &width, &height);
    }

    if (res == 0 && dither) {
        png_palette_dither_pass(&ctx, width, height);
    }
    if (dither) {
        heap_caps_free(ctx.rgb);
    }
    if (res != 0) {
        return -1;
    }

    *out_width = width;
    *out_height = height;
    return 0;
}
