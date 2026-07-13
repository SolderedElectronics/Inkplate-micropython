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
