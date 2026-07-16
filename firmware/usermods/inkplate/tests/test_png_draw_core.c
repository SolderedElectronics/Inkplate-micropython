// Host-compiled unit test, no ESP-IDF/hardware dependency. png_draw_core.c is the pure
// pixel-in/pixels-out logic extracted from png_draw.c so it can be tested without the real
// pngle/ROM-miniz decoder (see png_draw_core.h's header comment). This is the only test
// coverage this logic gets on host -- the real png_decode()/png_draw_gs4/png_draw_palette
// path stays HIL-only.
// Build/run: gcc -I.. test_png_draw_core.c ../image/png_draw_core.c ../image/dither.c \
//              ../display/gfx.c -o test_png_draw_core && ./test_png_draw_core
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../image/png_draw_core.h"

static int get_mono_pixel(const uint8_t *fb, int w, int x, int y)
{
    int idx = (y * w + x) >> 3;
    int shift = x & 7;
    return (fb[idx] >> shift) & 1;
}

static int get_gs4_pixel(const uint8_t *fb, int w, int x, int y)
{
    int byte_index = y * (w / 2) + (x >> 1);
    int shift = (x & 1) ? 4 : 0; // default nibble convention: even x -> low nibble
    return (fb[byte_index] >> shift) & 0x0F;
}

static void rgba(uint8_t out[4], uint8_t r, uint8_t g, uint8_t b)
{
    out[0] = r;
    out[1] = g;
    out[2] = b;
    out[3] = 255;
}

// --- mono/GS4, streamed path (the common non-interlaced case) ---

static void test_stream_mono_no_diffusion_needed(void)
{
    // Solid rows of pure white/black leave no residual error to diffuse (same
    // "exact match" reasoning as test_bmp_draw_palette.c), so output is deterministic
    // regardless of the diffusion machinery actually running.
    uint8_t fb[2] = {0}; // phys_w=8, phys_h=2
    uint8_t white[4], black[4];
    rgba(white, 255, 255, 255);
    rgba(black, 0, 0, 0);

    png_draw_core_stream_ctx_t ctx;
    png_draw_core_stream_init(&ctx, fb, 8, 2, 0, 0, 0, 0, /*invert=*/0, 8, 2,
                              DITHER_KERNEL_FLOYD_STEINBERG);
    for (uint32_t x = 0; x < 8; x++) {
        png_draw_core_pixel_stream(&ctx, x, 0, white);
        png_draw_core_pixel_stream(&ctx, x, 1, black);
    }
    png_draw_core_stream_finish(&ctx);

    for (int x = 0; x < 8; x++) {
        assert(get_mono_pixel(fb, 8, x, 0) == 0); // white -> light
        assert(get_mono_pixel(fb, 8, x, 1) == 1); // black -> dark
    }
    assert(!ctx.oversized);
    printf("test_stream_mono_no_diffusion_needed: passed\n");
}

static void test_stream_mono_row_advance_on_y_change(void)
{
    // Feeding pixels out of raster order within a row, then moving to the next row,
    // exercises the have_dctx row-advance-on-y-change branch (dither_row_advance is
    // only called when y actually changes, not per pixel).
    uint8_t fb[2] = {0}; // phys_w=8, phys_h=2
    uint8_t white[4];
    rgba(white, 255, 255, 255);

    png_draw_core_stream_ctx_t ctx;
    png_draw_core_stream_init(&ctx, fb, 8, 2, 0, 0, 0, 0, /*invert=*/0, 8, 2,
                              DITHER_KERNEL_FLOYD_STEINBERG);
    assert(ctx.have_dctx); // width=8 is a trivial allocation, should always succeed here
    for (uint32_t x = 0; x < 8; x++) {
        png_draw_core_pixel_stream(&ctx, x, 0, white);
    }
    for (uint32_t x = 0; x < 8; x++) {
        png_draw_core_pixel_stream(&ctx, x, 1, white);
    }
    png_draw_core_stream_finish(&ctx);

    for (int y = 0; y < 2; y++) {
        for (int x = 0; x < 8; x++) {
            assert(get_mono_pixel(fb, 8, x, y) == 0);
        }
    }
    printf("test_stream_mono_row_advance_on_y_change: passed\n");
}

static void test_stream_mono_oversized_flag(void)
{
    uint8_t fb[1] = {0};
    uint8_t white[4];
    rgba(white, 255, 255, 255);

    png_draw_core_stream_ctx_t ctx;
    png_draw_core_stream_init(&ctx, fb, 8, 1, 0, 0, 0, 0, /*invert=*/0, 8, 1,
                              DITHER_KERNEL_FLOYD_STEINBERG);
    png_draw_core_pixel_stream(&ctx, 8, 0, white); // x == width -> out of bounds
    png_draw_core_stream_finish(&ctx);

    assert(ctx.oversized);
    printf("test_stream_mono_oversized_flag: passed\n");
}

static void test_gs4_no_dither_levels(void)
{
    uint8_t fb[1] = {0}; // phys_w=2, phys_h=1, GS4 -> 1 byte/row
    uint8_t white[4], black[4];
    rgba(white, 255, 255, 255);
    rgba(black, 0, 0, 0);

    png_draw_core_ctx_t ctx;
    png_draw_core_init(&ctx, fb, 2, 1, 0, /*display_mode=*/1, 0, 0, /*invert=*/0, /*dither=*/0,
                       DITHER_KERNEL_FLOYD_STEINBERG, NULL);
    png_draw_core_pixel(&ctx, 0, 0, white);
    png_draw_core_pixel(&ctx, 1, 0, black);

    assert(get_gs4_pixel(fb, 2, 0, 0) == 7); // lightest
    assert(get_gs4_pixel(fb, 2, 1, 0) == 0); // darkest
    printf("test_gs4_no_dither_levels: passed\n");
}

// --- mono/GS4, buffered path (Adam7 fallback) ---

static void test_buffered_mono_dither_pass(void)
{
    uint8_t fb[2] = {0}; // phys_w=8, phys_h=2
    uint8_t *luma = malloc((size_t)PNG_DRAW_CORE_MAX_WIDTH * PNG_DRAW_CORE_MAX_HEIGHT);
    uint8_t white[4], black[4];
    rgba(white, 255, 255, 255);
    rgba(black, 0, 0, 0);

    png_draw_core_ctx_t ctx;
    png_draw_core_init(&ctx, fb, 8, 2, 0, 0, 0, 0, /*invert=*/0, /*dither=*/1,
                       DITHER_KERNEL_FLOYD_STEINBERG, luma);
    for (uint32_t x = 0; x < 8; x++) {
        png_draw_core_pixel(&ctx, x, 0, white); // buffered, not blitted yet
        png_draw_core_pixel(&ctx, x, 1, black);
    }
    for (int x = 0; x < 8; x++) {
        assert(get_mono_pixel(fb, 8, x, 0) == 0);
        assert(get_mono_pixel(fb, 8, x, 1) == 0); // nothing blitted until the dither pass
    }
    png_draw_core_dither_pass(&ctx, 8, 2);

    for (int x = 0; x < 8; x++) {
        assert(get_mono_pixel(fb, 8, x, 0) == 0); // white -> light
        assert(get_mono_pixel(fb, 8, x, 1) == 1); // black -> dark, now blitted
    }
    assert(!ctx.oversized);
    free(luma);
    printf("test_buffered_mono_dither_pass: passed\n");
}

static void test_buffered_mono_oversized_flag(void)
{
    uint8_t fb[1] = {0};
    uint8_t *luma = malloc((size_t)PNG_DRAW_CORE_MAX_WIDTH * PNG_DRAW_CORE_MAX_HEIGHT);
    uint8_t white[4];
    rgba(white, 255, 255, 255);

    png_draw_core_ctx_t ctx;
    png_draw_core_init(&ctx, fb, 8, 1, 0, 0, 0, 0, /*invert=*/0, /*dither=*/1,
                       DITHER_KERNEL_FLOYD_STEINBERG, luma);
    png_draw_core_pixel(&ctx, PNG_DRAW_CORE_MAX_WIDTH, 0, white); // x == cap -> out of bounds

    assert(ctx.oversized);
    free(luma);
    printf("test_buffered_mono_oversized_flag: passed\n");
}

// --- palette, streamed + buffered ---

typedef struct {
    int values[4][4]; // [y][x]
    int calls;
} capture_t;

static void capture_cb(void *ctx_, int x, int y, int value)
{
    capture_t *ctx = (capture_t *)ctx_;
    ctx->values[y][x] = value;
    ctx->calls++;
}

// 6COLOR's real palette (same table as tests/test_bmp_draw_palette.c).
static const dither_palette_entry_t palette_6color[] = {
    {0, 0, 0, 0},   {255, 255, 255, 1}, {0, 255, 0, 2},   {0, 0, 255, 3},
    {255, 0, 0, 4}, {255, 255, 0, 5},   {255, 165, 0, 6},
};
#define PALETTE_N ((int)(sizeof(palette_6color) / sizeof(palette_6color[0])))

static void test_stream_palette_exact_matches(void)
{
    capture_t cap = {0};
    uint8_t red[4], green[4];
    rgba(red, 255, 0, 0);
    rgba(green, 0, 255, 0);

    png_draw_core_palette_stream_ctx_t ctx;
    png_draw_core_palette_stream_init(&ctx, /*invert=*/0, DITHER_KERNEL_FLOYD_STEINBERG,
                                      palette_6color, PALETTE_N, capture_cb, &cap, 2, 1);
    png_draw_core_palette_pixel_stream(&ctx, 0, 0, red);
    png_draw_core_palette_pixel_stream(&ctx, 1, 0, green);
    png_draw_core_palette_stream_finish(&ctx);

    assert(cap.calls == 2);
    assert(cap.values[0][0] == 4); // red
    assert(cap.values[0][1] == 2); // green
    printf("test_stream_palette_exact_matches: passed\n");
}

static void test_buffered_palette_dither_pass(void)
{
    capture_t cap = {0};
    uint16_t rgb[4] = {0}; // max_width=2, max_height=2
    uint8_t blue[4], yellow[4];
    rgba(blue, 0, 0, 255);
    rgba(yellow, 255, 255, 0);

    png_draw_core_palette_ctx_t ctx;
    png_draw_core_palette_init(&ctx, /*invert=*/0, /*dither=*/1, DITHER_KERNEL_FLOYD_STEINBERG,
                               palette_6color, PALETTE_N, capture_cb, &cap, 2, 2, rgb);
    png_draw_core_palette_pixel(&ctx, 0, 0, blue);
    png_draw_core_palette_pixel(&ctx, 1, 0, blue);
    png_draw_core_palette_pixel(&ctx, 0, 1, yellow);
    png_draw_core_palette_pixel(&ctx, 1, 1, yellow);
    assert(cap.calls == 0); // buffered, not written until the dither pass

    png_draw_core_palette_dither_pass(&ctx, 2, 2);

    assert(cap.calls == 4);
    assert(cap.values[0][0] == 3 && cap.values[0][1] == 3); // blue
    assert(cap.values[1][0] == 5 && cap.values[1][1] == 5); // yellow
    printf("test_buffered_palette_dither_pass: passed\n");
}

static void test_palette_invert_swaps_black_white_only(void)
{
    capture_t cap = {0};
    uint8_t red[4];
    rgba(red, 255, 0, 0);

    png_draw_core_palette_ctx_t ctx;
    png_draw_core_palette_init(&ctx, /*invert=*/1, /*dither=*/0, DITHER_KERNEL_FLOYD_STEINBERG,
                               palette_6color, PALETTE_N, capture_cb, &cap, 2, 2, NULL);
    png_draw_core_palette_pixel(&ctx, 0, 0, red);

    assert(cap.values[0][0] == 4); // red untouched by invert (same contract as dither.h)
    printf("test_palette_invert_swaps_black_white_only: passed\n");
}

int main(void)
{
    test_stream_mono_no_diffusion_needed();
    test_stream_mono_row_advance_on_y_change();
    test_stream_mono_oversized_flag();
    test_gs4_no_dither_levels();
    test_buffered_mono_dither_pass();
    test_buffered_mono_oversized_flag();
    test_stream_palette_exact_matches();
    test_buffered_palette_dither_pass();
    test_palette_invert_swaps_black_white_only();
    printf("test_png_draw_core: all assertions passed\n");
    return 0;
}
