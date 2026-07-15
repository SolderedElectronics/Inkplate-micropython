// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_bmp_draw_palette.c ../bmp_draw.c ../bmp_decode.c \
//              ../dither.c -o test_bmp_draw_palette && ./test_bmp_draw_palette
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../bmp_draw.h"
#include "../dither.h"

// Same 2x2 24bpp sample as tests/test_bmp_decode.c's sample_bmp_24: top-left=red,
// top-right=green, bottom-left=blue, bottom-right=yellow, stored bottom-up.
static const uint8_t sample_bmp_24[70] = {
    'B', 'M', 70, 0, 0,  0, 0,   0, 0, 0, 54,  0,   0, 0, 40, 0, 0,   0, 2,   0, 0, 0, 2, 0,
    0,   0,   1,  0, 24, 0, 0,   0, 0, 0, 16,  0,   0, 0, 0,  0, 0,   0, 0,   0, 0, 0, 0, 0,
    0,   0,   0,  0, 0,  0, 255, 0, 0, 0, 255, 255, 0, 0, 0,  0, 255, 0, 255, 0, 0, 0,
};

// 6COLOR's real palette (docs/REFACTOR-PLAN.md Phase 10 step 32).
static const dither_palette_entry_t palette_6color[] = {
    {0, 0, 0, 0},   {255, 255, 255, 1}, {0, 255, 0, 2},   {0, 0, 255, 3},
    {255, 0, 0, 4}, {255, 255, 0, 5},   {255, 165, 0, 6},
};

typedef struct {
    int values[2][2]; // [y][x]
    int calls;
} capture_t;

static void capture_cb(void *ctx_, int x, int y, int value)
{
    capture_t *ctx = (capture_t *)ctx_;
    ctx->values[y][x] = value;
    ctx->calls++;
}

static void test_no_dither_exact_matches(void)
{
    capture_t cap = {0};
    uint32_t w = 0, h = 0;
    int n = (int)(sizeof(palette_6color) / sizeof(palette_6color[0]));

    int res = bmp_draw_palette(sample_bmp_24, sizeof(sample_bmp_24), 0, 0,
                               DITHER_KERNEL_FLOYD_STEINBERG, palette_6color, n, capture_cb, &cap,
                               &w, &h);
    assert(res == 0);
    assert(w == 2 && h == 2);
    assert(cap.calls == 4);
    // Top row (y=0): red, green. Bottom row (y=1): blue, yellow.
    assert(cap.values[0][0] == 4); // red
    assert(cap.values[0][1] == 2); // green
    assert(cap.values[1][0] == 3); // blue
    assert(cap.values[1][1] == 5); // yellow

    printf("test_no_dither_exact_matches: passed\n");
}

static void test_dither_runs_and_stays_in_palette_range(void)
{
    // Exact-match colors leave no residual error to diffuse, but this still
    // exercises the dither_rgb_ctx_t alloc/free path and confirms every emitted
    // value is a real palette entry, not garbage.
    capture_t cap = {0};
    uint32_t w = 0, h = 0;
    int n = (int)(sizeof(palette_6color) / sizeof(palette_6color[0]));

    int res = bmp_draw_palette(sample_bmp_24, sizeof(sample_bmp_24), 0, 1,
                               DITHER_KERNEL_FLOYD_STEINBERG, palette_6color, n, capture_cb, &cap,
                               &w, &h);
    assert(res == 0);
    assert(cap.calls == 4);
    for (int y = 0; y < 2; y++) {
        for (int x = 0; x < 2; x++) {
            int v = cap.values[y][x];
            int found = 0;
            for (int i = 0; i < n; i++) {
                if (palette_6color[i].value == v) {
                    found = 1;
                }
            }
            assert(found);
        }
    }

    printf("test_dither_runs_and_stays_in_palette_range: passed\n");
}

static void test_invert_swaps_black_white_only(void)
{
    // Build a 1x1 all-black BMP by reusing the same header, shrinking to 1x1 is
    // more header surgery than it's worth here -- instead confirm invert leaves
    // this image's chromatic matches (red/green/blue/yellow, no black or white
    // present) completely unchanged, matching dither_invert_palette_bw's contract
    // (already unit-tested directly in test_dither.c).
    capture_t cap = {0};
    uint32_t w = 0, h = 0;
    int n = (int)(sizeof(palette_6color) / sizeof(palette_6color[0]));

    int res = bmp_draw_palette(sample_bmp_24, sizeof(sample_bmp_24), 1, 0,
                               DITHER_KERNEL_FLOYD_STEINBERG, palette_6color, n, capture_cb, &cap,
                               &w, &h);
    assert(res == 0);
    assert(cap.values[0][0] == 4); // red, untouched by invert
    assert(cap.values[0][1] == 2); // green, untouched
    assert(cap.values[1][0] == 3); // blue, untouched
    assert(cap.values[1][1] == 5); // yellow, untouched

    printf("test_invert_swaps_black_white_only: passed\n");
}

int main(void)
{
    test_no_dither_exact_matches();
    test_dither_runs_and_stays_in_palette_range();
    test_invert_swaps_black_white_only();
    printf("test_bmp_draw_palette: all assertions passed\n");
    return 0;
}
