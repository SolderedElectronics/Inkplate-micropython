// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_dither.c ../dither.c -o test_dither && ./test_dither
#include <assert.h>
#include <stdio.h>

#include "../image/dither.h"

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

// 6COLOR's real 7-entry palette, used below to exercise
// dither_quantize_palette/dither_invert_palette_bw against real data instead of a
// synthetic table.
static const dither_palette_entry_t test_palette_6color[] = {
    {0, 0, 0, 0},   {255, 255, 255, 1}, {0, 255, 0, 2},   {0, 0, 255, 3},
    {255, 0, 0, 4}, {255, 255, 0, 5},   {255, 165, 0, 6},
};

static void test_quantize_palette(void)
{
    int rr, rg, rb;
    int n = (int)(sizeof(test_palette_6color) / sizeof(test_palette_6color[0]));

    // Exact hits.
    assert(dither_quantize_palette(0, 0, 0, test_palette_6color, n, &rr, &rg, &rb) == 0);
    assert(rr == 0 && rg == 0 && rb == 0);
    assert(dither_quantize_palette(255, 165, 0, test_palette_6color, n, &rr, &rg, &rb) == 6);
    assert(rr == 255 && rg == 165 && rb == 0);

    // Nearest match: (200, 20, 20) is closer to red (255,0,0) than black or any
    // other entry.
    assert(dither_quantize_palette(200, 20, 20, test_palette_6color, n, &rr, &rg, &rb) == 4);
    assert(rr == 255 && rg == 0 && rb == 0);

    printf("test_quantize_palette: passed\n");
}

static void test_invert_palette_bw(void)
{
    int n = (int)(sizeof(test_palette_6color) / sizeof(test_palette_6color[0]));
    int black_value, white_value;
    dither_find_bw_values(test_palette_6color, n, &black_value, &white_value);
    assert(black_value == 0 && white_value == 1);

    // Black <-> white swap.
    assert(dither_invert_palette_bw(0, black_value, white_value) == 1);
    assert(dither_invert_palette_bw(1, black_value, white_value) == 0);
    // Chromatic entries (e.g. red=4) are left untouched.
    assert(dither_invert_palette_bw(4, black_value, white_value) == 4);
    assert(dither_invert_palette_bw(6, black_value, white_value) == 6);

    printf("test_invert_palette_bw: passed\n");
}

static void test_rgb_diffusion_and_apply_error(void)
{
    // Same shape/inputs as test_floyd_steinberg_diffusion (x=1,y=0, 4-wide/2-tall
    // draw region), but all 3 channels at once with distinct per-channel deltas to
    // confirm they don't cross-contaminate. FS taps: (dx=1,dy=0,wt=7) -> nx=2
    // (error_current); (dx=-1,dy=1,wt=3) -> nx=0, (dx=0,dy=1,wt=5) -> nx=1,
    // (dx=1,dy=1,wt=1) -> nx=2 (all three in error_next), divisor 16.
    dither_rgb_ctx_t ctx;
    assert(dither_rgb_ctx_init(&ctx, 4, DITHER_KERNEL_FLOYD_STEINBERG) == 0);

    dither_diffuse_error_rgb(&ctx, 1, 0, 4, 2, 160, 80, 32);
    assert(ctx.error_current[2 * 3 + 0] == 70); // r: 160*7/16
    assert(ctx.error_current[2 * 3 + 1] == 35); // g: 80*7/16
    assert(ctx.error_current[2 * 3 + 2] == 14); // b: 32*7/16
    assert(ctx.error_next[0 * 3 + 0] == 30);    // r: 160*3/16
    assert(ctx.error_next[0 * 3 + 1] == 15);    // g: 80*3/16
    assert(ctx.error_next[0 * 3 + 2] == 6);     // b: 32*3/16
    assert(ctx.error_next[1 * 3 + 0] == 50);    // r: 160*5/16
    assert(ctx.error_next[1 * 3 + 1] == 25);    // g: 80*5/16
    assert(ctx.error_next[2 * 3 + 0] == 10);    // r: 160*1/16
    assert(ctx.error_next[2 * 3 + 2] == 2);     // b: 32*1/16

    int r = 250, g = 250, b = 250;
    dither_apply_error_rgb(&ctx, 1, &r, &g, &b); // column 1's error_current is untouched (0s)
    assert(r == 250 && g == 250 && b == 250);

    // Clamp check: column 2's error_current carries this diffusion's r=70; force it
    // higher to confirm apply_error_rgb saturates at 255, same as the mono clamp test.
    ctx.error_current[2 * 3 + 0] = 300;
    r = 250;
    g = 0;
    b = 0;
    dither_apply_error_rgb(&ctx, 2, &r, &g, &b);
    assert(r == 255); // 250+300 clamped

    dither_row_advance_rgb(&ctx);
    assert(ctx.error_current[0 * 3 + 0] == 30);
    assert(ctx.error_current[0 * 3 + 1] == 15);
    assert(ctx.error_next[0 * 3 + 0] == 0);

    dither_rgb_ctx_free(&ctx);
    printf("test_rgb_diffusion_and_apply_error: passed\n");
}

static void test_rgb565_round_trip(void)
{
    int r, g, b;

    // Pure black/white round-trip exactly (0 and 0x1F/0x3F expand back to 0/255).
    dither_unpack_rgb565(dither_pack_rgb565(0, 0, 0), &r, &g, &b);
    assert(r == 0 && g == 0 && b == 0);
    dither_unpack_rgb565(dither_pack_rgb565(255, 255, 255), &r, &g, &b);
    assert(r == 255 && g == 255 && b == 255);

    // Primary colors round-trip exactly (only the top bits of each channel are
    // ever set, so quantization loses nothing).
    dither_unpack_rgb565(dither_pack_rgb565(255, 0, 0), &r, &g, &b);
    assert(r == 255 && g == 0 && b == 0);
    dither_unpack_rgb565(dither_pack_rgb565(0, 255, 0), &r, &g, &b);
    assert(r == 0 && g == 255 && b == 0);
    dither_unpack_rgb565(dither_pack_rgb565(0, 0, 255), &r, &g, &b);
    assert(r == 0 && g == 0 && b == 255);

    // Mid-grey: lossy (5/6-bit quantization), but must stay within one
    // quantization step of the original value, not drift arbitrarily.
    dither_unpack_rgb565(dither_pack_rgb565(128, 128, 128), &r, &g, &b);
    assert(r >= 120 && r <= 136);
    assert(g >= 124 && g <= 132);
    assert(b >= 120 && b <= 136);

    printf("test_rgb565_round_trip: passed\n");
}

int main(void)
{
    test_quantize_mono();
    test_quantize_gs3();
    test_apply_error_clamps();
    test_floyd_steinberg_diffusion();
    test_diffusion_dropped_at_last_row();
    test_diffusion_clips_at_column_edges();
    test_quantize_palette();
    test_invert_palette_bw();
    test_rgb_diffusion_and_apply_error();
    test_rgb565_round_trip();
    printf("test_dither: all assertions passed\n");
    return 0;
}
