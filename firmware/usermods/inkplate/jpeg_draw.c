#include "jpeg_draw.h"

#include "gfx.h"
#include "jpeg_decode.h"

typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation;
    int x0, y0;
} jpeg_draw_ctx_t;

static int jpeg_draw_tile_cb(void *ctx_, const jpeg_tile_t *tile)
{
    jpeg_draw_ctx_t *ctx = (jpeg_draw_ctx_t *)ctx_;
    for (uint32_t ty = 0; ty < tile->h; ty++) {
        for (uint32_t tx = 0; tx < tile->w; tx++) {
            const uint8_t *px = tile->rgb + (ty * tile->w + tx) * 3;
            // ITU-R BT.601 luma, integer approximation.
            uint32_t luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            // Nearest of 8 levels (0-7) -- no error diffusion, that's step 21's job.
            int level = (int)((luma * 7 + 127) / 255);
            gfx_set_pixel(ctx->fb, ctx->phys_w, ctx->phys_h, ctx->rotation, 1,
                          ctx->x0 + (int)(tile->x + tx), ctx->y0 + (int)(tile->y + ty), level);
        }
    }
    return 1;
}

int jpeg_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int x0, int y0,
                  const uint8_t *buf, size_t len, uint32_t *out_width, uint32_t *out_height)
{
    jpeg_draw_ctx_t ctx = {
        .fb = fb, .phys_w = phys_w, .phys_h = phys_h, .rotation = rotation, .x0 = x0, .y0 = y0};
    return jpeg_decode(buf, len, jpeg_draw_tile_cb, &ctx, out_width, out_height);
}
