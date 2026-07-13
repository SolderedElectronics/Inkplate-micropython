// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_dither.c ../dither.c -o test_dither && ./test_dither
#include <assert.h>
#include <stdio.h>

#include "../dither.h"

static void test_quantize_mono(void)
{
    int recon;
    // Threshold at 127, matching boards/inkplate10/inkplate10.py's pre-port
    // `val = 0 if gray > 127 else 1`.
    assert(dither_quantize(200, 0, &recon) == 0);
    assert(recon == 255);
    assert(dither_quantize(127, 0, &recon) == 1);
    assert(recon == 0);
    assert(dither_quantize(128, 0, &recon) == 0);
    assert(recon == 255);
    assert(dither_quantize(0, 0, &recon) == 1);
    assert(recon == 0);

    printf("test_quantize_mono: passed\n");
}

static void test_quantize_gs3(void)
{
    int recon;
    // (gray*7+127)/255, matching the already-shipped non-dither placeholders in
    // jpeg_draw.c/png_draw.c/bmp_draw.c.
    assert(dither_quantize(0, 1, &recon) == 0);
    assert(recon == 0);
    assert(dither_quantize(255, 1, &recon) == 7);
    assert(recon == 255);
    assert(dither_quantize(128, 1, &recon) == 4);
    assert(recon == 145); // 4*255/7 truncated

    printf("test_quantize_gs3: passed\n");
}

static void test_apply_error_clamps(void)
{
    dither_ctx_t ctx;
    assert(dither_ctx_init(&ctx, 4, DITHER_KERNEL_FLOYD_STEINBERG) == 0);
    ctx.error_current[2] = 10;
    assert(dither_apply_error(&ctx, 2, 250) == 255); // 260 clamped
    ctx.error_current[1] = -300;
    assert(dither_apply_error(&ctx, 1, 100) == 0); // -200 clamped
    assert(dither_apply_error(&ctx, 0, 50) == 50); // untouched column, no-op

    dither_ctx_free(&ctx);
    printf("test_apply_error_clamps: passed\n");
}

static void test_floyd_steinberg_diffusion(void)
{
    // Hand-computed: FS taps are (dx=1,dy=0,wt=7),(dx=-1,dy=1,wt=3),(dx=0,dy=1,wt=5),
    // (dx=1,dy=1,wt=1), divisor 16. Pixel at x=1,y=0 in a 4-wide/2-tall draw region,
    // delta=160 (chosen so 160*wt/16 divides evenly for every tap).
    dither_ctx_t ctx;
    assert(dither_ctx_init(&ctx, 4, DITHER_KERNEL_FLOYD_STEINBERG) == 0);

    dither_diffuse_error(&ctx, 1, 0, 4, 2, 160);
    // dy=0 tap lands in error_current (same row, future column) -- available to the
    // same row's later columns without waiting for dither_row_advance.
    assert(ctx.error_current[0] == 0);
    assert(ctx.error_current[1] == 0);
    assert(ctx.error_current[2] == 70); // 160*7/16
    assert(ctx.error_current[3] == 0);
    // dy=1 taps land in error_next.
    assert(ctx.error_next[0] == 30); // 160*3/16
    assert(ctx.error_next[1] == 50); // 160*5/16
    assert(ctx.error_next[2] == 10); // 160*1/16
    assert(ctx.error_next[3] == 0);

    dither_row_advance(&ctx);
    assert(ctx.error_current[0] == 30);
    assert(ctx.error_current[1] == 50);
    assert(ctx.error_current[2] == 10);
    assert(ctx.error_current[3] == 0);
    assert(ctx.error_next[0] == 0);
    assert(ctx.error_next[1] == 0);
    assert(ctx.error_next[2] == 0);
    assert(ctx.error_next[3] == 0);

    dither_ctx_free(&ctx);
    printf("test_floyd_steinberg_diffusion: passed\n");
}

static void test_diffusion_dropped_at_last_row(void)
{
    // y+1 >= draw_height must drop dy=1 taps entirely (matching the old code's
    // "if y+1 < draw_height" guards) -- otherwise the last row's error would leak
    // into a nonexistent row instead of being dropped.
    dither_ctx_t ctx;
    assert(dither_ctx_init(&ctx, 4, DITHER_KERNEL_FLOYD_STEINBERG) == 0);

    dither_diffuse_error(&ctx, 1, 1, 4, 2, 160); // y=1 is the last row (draw_height=2)
    assert(ctx.error_current[2] == 70);          // dy=0 tap still applies
    assert(ctx.error_next[0] == 0);
    assert(ctx.error_next[1] == 0);
    assert(ctx.error_next[2] == 0);

    dither_ctx_free(&ctx);
    printf("test_diffusion_dropped_at_last_row: passed\n");
}

static void test_diffusion_clips_at_column_edges(void)
{
    dither_ctx_t ctx;
    assert(dither_ctx_init(&ctx, 4, DITHER_KERNEL_FLOYD_STEINBERG) == 0);

    // x=0: the dx=-1,dy=1 tap (nx=-1) must be dropped, not wrap/underflow.
    dither_diffuse_error(&ctx, 0, 0, 4, 2, 160);
    assert(ctx.error_current[0] == 0);
    assert(ctx.error_current[1] == 70); // dx=1,dy=0
    assert(ctx.error_next[0] == 50);    // dx=0,dy=1
    assert(ctx.error_next[1] == 10);    // dx=1,dy=1

    dither_ctx_free(&ctx);

    // x=3 (last column, width=4): the dx=1 taps (nx=4) must be dropped.
    assert(dither_ctx_init(&ctx, 4, DITHER_KERNEL_FLOYD_STEINBERG) == 0);
    dither_diffuse_error(&ctx, 3, 0, 4, 2, 160);
    assert(ctx.error_current[3] == 0); // dx=1,dy=0 dropped (nx=4 out of range)
    assert(ctx.error_next[2] == 30);   // dx=-1,dy=1
    assert(ctx.error_next[3] == 50);   // dx=0,dy=1

    dither_ctx_free(&ctx);
    printf("test_diffusion_clips_at_column_edges: passed\n");
}

int main(void)
{
    test_quantize_mono();
    test_quantize_gs3();
    test_apply_error_clamps();
    test_floyd_steinberg_diffusion();
    test_diffusion_dropped_at_last_row();
    test_diffusion_clips_at_column_edges();
    printf("test_dither: all assertions passed\n");
    return 0;
}
