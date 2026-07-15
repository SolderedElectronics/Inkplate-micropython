#include "jpeg_draw.h"

#include <stdlib.h>

#include "esp_heap_caps.h"

#include "dither.h"
#include "gfx.h"
#include "jpeg_decode.h"

// Matches Inkplate10's physical resolution -- the only board this repo supports today
// (Phase 8 hasn't landed). Unlike bmp_draw.c's row-only scratch buffer, this is a full
// W*H image buffer, so headroom for boards not yet in this repo (e.g. Inkplate5v2's
// wider 1280px) would nearly double the allocation -- confirmed via HIL
// (docs/REFACTOR-PLAN.md Phase 7 step 21) that PSRAM is already tight enough for this
// exact size to matter (a 1600x1200 buffer failed to allocate alongside the framebuffer
// + MicroPython's own PSRAM-backed heap + the decoded file's Python-side buffer).
// Revisit this cap (and where it should live) when Phase 8 adds bigger boards. Only
// allocated when dithering is requested.
#define JPEG_DRAW_MAX_WIDTH 1200
#define JPEG_DRAW_MAX_HEIGHT 825

typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    int dither;
    int kernel_type;
    // Only allocated when dither is set: one byte of luma per pixel, indexed
    // [y * JPEG_DRAW_MAX_WIDTH + x] regardless of the image's real width, since
    // jpeg_decode() doesn't report the final width/height until decode completes --
    // tiles arrive (and need buffering) before that.
    uint8_t *luma;
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

static int jpeg_draw_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_ctx_t *ctx = (jpeg_draw_ctx_t *)ctx_;

    if (!ctx->dither) {
        jpeg_draw_tile_immediate(ctx, tile);
        return 1;
    }

    if (tile->x + tile->w > JPEG_DRAW_MAX_WIDTH || tile->y + tile->h > JPEG_DRAW_MAX_HEIGHT) {
        return 0; // abort decode, image too large to buffer for dithering
    }

    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            uint32_t luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            ctx->luma[(tile->y + ty) * JPEG_DRAW_MAX_WIDTH + (tile->x + tx)] = (uint8_t)luma;
        }
    }
    return 1;
}

// Runs after decode completes: dithers the buffered luma in one guaranteed row-major
// pass and writes the result into fb. Falls back to plain (non-diffused) quantization
// if the error-diffusion context can't be allocated, so a transient OOM degrades to a
// banded image instead of a blank one.
static void jpeg_dither_pass(jpeg_draw_ctx_t *ctx, uint32_t w, uint32_t h)
{
    int inv_mask = ctx->display_mode == 0 ? 1 : 7;
    dither_ctx_t dctx;
    int have_dctx = dither_ctx_init(&dctx, (int)w, ctx->kernel_type) == 0;

    for (uint32_t y = 0; y < h; y++) {
        for (uint32_t x = 0; x < w; x++) {
            int gray = ctx->luma[y * JPEG_DRAW_MAX_WIDTH + x];
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
                           .luma = NULL};

    if (dither) {
        // Plain malloc() draws from ESP32's small internal-DRAM pool and fails outright
        // for a buffer this size -- this scratch buffer needs PSRAM explicitly, same as
        // the project's framebuffers (docs/REFACTOR-PLAN.md Phase 0 step 4).
        ctx.luma = heap_caps_malloc((size_t)JPEG_DRAW_MAX_WIDTH * JPEG_DRAW_MAX_HEIGHT,
                                    MALLOC_CAP_SPIRAM);
        if (ctx.luma == NULL) {
            return -1;
        }
    }

    uint32_t width = 0, height = 0;
    int res = jpeg_decode(buf, len, jpeg_draw_tile_cb, &ctx, &width, &height);

    if (res == 0 && dither) {
        jpeg_dither_pass(&ctx, width, height);
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
// see inkplatemodule.c's `inkplate_jpeg_draw_palette` for the actual per-call
// policy and its HIL-informed history (a fixed one-size-fits-all cap, and then a
// too-small panel-only cap, both turned out wrong on real Inkplate6COLOR hardware
// before landing here). Stored as RGB565 (2 bytes/pixel, dither_pack_rgb565/
// dither_unpack_rgb565 in dither.h) rather than RGB888 (3 bytes/pixel) -- matches
// what the pre-refactor Python driver decoded to before dithering, and cuts this
// buffer's PSRAM footprint by a third, which is what actually let real photos fit
// again on Inkplate6COLOR's fragmented PSRAM (confirmed via HIL) rather than
// relying on the fallbacks below. Same memory-budget reasoning jpeg_draw_ctx_t's
// luma buffer above already needed once (docs/REFACTOR-PLAN.md Phase 7 step 21),
// just parameterized and RGB565-packed this time, since this path serves 3 boards
// with very different panel sizes through the same compiled function.
typedef struct {
    int invert;
    int dither;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    jpeg_draw_palette_cb write_pixel;
    void *cb_ctx;
    int max_width;
    int max_height;
    // Only allocated when dither is set: full decoded image as RGB565, indexed
    // [y * max_width + x] regardless of the image's real width, same reasoning as
    // jpeg_draw_ctx_t's luma buffer above.
    uint16_t *rgb;
    // Set when a tile lands outside max_width/max_height -- signals
    // jpeg_draw_palette to retry the whole decode with dithering off, rather than
    // just failing (see jpeg_draw_palette_tile_cb).
    int oversized_for_dither;
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

static int jpeg_draw_palette_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_palette_ctx_t *ctx = (jpeg_draw_palette_ctx_t *)ctx_;

    if (!ctx->dither) {
        jpeg_draw_palette_tile_immediate(ctx, tile);
        return 1;
    }

    if (tile->x + tile->w > (uint32_t)ctx->max_width ||
        tile->y + tile->h > (uint32_t)ctx->max_height) {
        // Abort this buffered attempt -- jpeg_draw_palette retries the whole decode
        // with dithering off (jpeg_decode is stateless/re-entrant across calls, so
        // this is a clean full redo, not a half-drawn image).
        ctx->oversized_for_dither = 1;
        return 0;
    }

    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            size_t off = (size_t)(tile->y + ty) * (uint32_t)ctx->max_width + (tile->x + tx);
            ctx->rgb[off] = dither_pack_rgb565(px[0], px[1], px[2]);
        }
    }
    return 1;
}

static void jpeg_palette_dither_pass(jpeg_draw_palette_ctx_t *ctx, uint32_t w, uint32_t h)
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

int jpeg_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                      const dither_palette_entry_t *palette, int palette_n,
                      jpeg_draw_palette_cb write_pixel, void *cb_ctx, int max_width,
                      int max_height, uint32_t *out_width, uint32_t *out_height)
{
    jpeg_draw_palette_ctx_t ctx = {.invert = invert,
                                   .dither = dither,
                                   .kernel_type = kernel_type,
                                   .palette = palette,
                                   .palette_n = palette_n,
                                   .write_pixel = write_pixel,
                                   .cb_ctx = cb_ctx,
                                   .max_width = max_width,
                                   .max_height = max_height,
                                   .rgb = NULL,
                                   .oversized_for_dither = 0};

    if (dither) {
        ctx.rgb = heap_caps_malloc((size_t)max_width * (size_t)max_height * sizeof(uint16_t),
                                   MALLOC_CAP_SPIRAM);
        if (ctx.rgb == NULL) {
            // A single contiguous block this size isn't available right now (PSRAM
            // fragmentation -- this is now the RGB565-sized request, half again
            // smaller than the RGB888 size that originally hit this on real
            // Inkplate6COLOR hardware, so this fallback should be rare in practice).
            // Degrade to a non-dithered draw instead of hard-failing the whole call,
            // same transient-OOM-degrades-gracefully philosophy as
            // jpeg_palette_dither_pass's own dither_rgb_ctx_t fallback below.
            dither = 0;
            ctx.dither = 0;
        }
    }

    uint32_t width = 0, height = 0;
    int res = jpeg_decode(buf, len, jpeg_draw_palette_tile_cb, &ctx, &width, &height);

    if (res != 0 && ctx.oversized_for_dither) {
        // Source image is bigger than max_width/max_height (typically the panel's
        // own physical size -- see inkplatemodule.c's caller), so the dither buffer
        // was never going to hold it. Retry the whole decode from scratch with
        // dithering off instead of failing outright -- jpeg_decode has no state
        // that survives across calls, so this is a clean full redo, not a
        // half-drawn image.
        if (ctx.rgb != NULL) {
            heap_caps_free(ctx.rgb);
            ctx.rgb = NULL;
        }
        dither = 0;
        ctx.dither = 0;
        width = 0;
        height = 0;
        res = jpeg_decode(buf, len, jpeg_draw_palette_tile_cb, &ctx, &width, &height);
    }

    if (res == 0 && dither) {
        jpeg_palette_dither_pass(&ctx, width, height);
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
