#include "png_draw.h"

#include "gfx.h"
#include "png_decode.h"

typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation;
    int x0, y0;
} png_draw_ctx_t;

static void png_draw_pixel_cb(void *ctx_, uint32_t x, uint32_t y, const uint8_t rgba[4])
{
    png_draw_ctx_t *ctx = (png_draw_ctx_t *)ctx_;
    // ITU-R BT.601 luma, integer approximation. Alpha (rgba[3]) is ignored --
    // real compositing is step 21's job.
    uint32_t luma = (299 * rgba[0] + 587 * rgba[1] + 114 * rgba[2]) / 1000;
    // Nearest of 8 levels (0-7) -- no error diffusion, that's step 21's job.
    int level = (int)((luma * 7 + 127) / 255);
    gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, 1, ctx->x0 + (int)x,
                  ctx->y0 + (int)y, level);
}

int png_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int x0, int y0,
                 const uint8_t *buf, size_t len, uint32_t *out_width, uint32_t *out_height)
{
    png_draw_ctx_t ctx = {
        .fb = fb, .phys_w = phys_w, .phys_h = phys_h, .rotation = rotation, .x0 = x0, .y0 = y0};
    return png_decode(buf, len, png_draw_pixel_cb, &ctx, out_width, out_height);
}
