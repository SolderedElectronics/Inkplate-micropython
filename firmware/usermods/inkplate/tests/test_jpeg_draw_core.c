// Host-compiled unit test, no ESP-IDF/hardware dependency. jpeg_draw_core.c is the pure
// tile-in/pixels-out logic extracted from jpeg_draw.c so it can be tested without the real
// ROM-tjpgd decoder (see jpeg_draw_core.h's header comment). This is the only test coverage
// this logic gets on host -- the real jpeg_decode()/jpeg_draw_gs4/jpeg_draw_palette path
// stays HIL-only.
// Build/run: gcc -I.. test_jpeg_draw_core.c ../image/jpeg_draw_core.c ../image/dither.c \
//              ../display/gfx.c -o test_jpeg_draw_core && ./test_jpeg_draw_core
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../image/jpeg_draw_core.h"

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

// Solid-color 2x2 RGB888 tile, all pixels equal to (r,g,b) -- leaves no residual error to
// diffuse, so dithered output is exactly as deterministic as the non-dithered path (same
// reasoning as test_bmp_draw_palette.c's "exact matches" case).
static void fill_tile_rgb(uint8_t *rgb, int w, int h, uint8_t r, uint8_t g, uint8_t b)
{
    for (int i = 0; i < w * h; i++) {
        rgb[i * 3 + 0] = r;
        rgb[i * 3 + 1] = g;
        rgb[i * 3 + 2] = b;
    }
}

static void test_mono_no_dither_immediate(void)
{
    uint8_t fb[2] = {0}; // phys_w=8, phys_h=2 -> 1 byte/row
    uint8_t white[2 * 2 * 3], black[2 * 2 * 3];
    fill_tile_rgb(white, 2, 2, 255, 255, 255);
    fill_tile_rgb(black, 2, 2, 0, 0, 0);

    jpeg_draw_core_ctx_t ctx;
    jpeg_draw_core_init(&ctx, fb, 8, 2, 0, 0, 0, 0, /*invert=*/0, /*dither=*/0,
                        DITHER_KERNEL_FLOYD_STEINBERG);
    jpeg_draw_core_tile(&ctx, 0, 0, 2, 2, white); // left half, both rows: white
    jpeg_draw_core_tile(&ctx, 2, 0, 2, 2, black); // right half, both rows: black

    for (int y = 0; y < 2; y++) {
        assert(get_mono_pixel(fb, 8, 0, y) == 0); // white -> light/background
        assert(get_mono_pixel(fb, 8, 1, y) == 0);
        assert(get_mono_pixel(fb, 8, 2, y) == 1); // black -> dark/foreground
        assert(get_mono_pixel(fb, 8, 3, y) == 1);
    }
    printf("test_mono_no_dither_immediate: passed\n");
}

static void test_mono_dither_band_flush_across_tiles(void)
{
    // Two 2x2 tiles side by side forming one row-band (both at tile_y=0), then an
    // explicit final flush -- exercises band_w growing across multiple tiles within a
    // band (jpeg_draw.c's real usage: tjpgd delivers a band's tiles left-to-right
    // before the next band starts).
    uint8_t fb[2] = {0}; // phys_w=8, phys_h=2
    uint8_t white[2 * 2 * 3], black[2 * 2 * 3];
    fill_tile_rgb(white, 2, 2, 255, 255, 255);
    fill_tile_rgb(black, 2, 2, 0, 0, 0);

    jpeg_draw_core_ctx_t ctx;
    jpeg_draw_core_init(&ctx, fb, 8, 2, 0, 0, 0, 0, /*invert=*/0, /*dither=*/1,
                        DITHER_KERNEL_FLOYD_STEINBERG);
    jpeg_draw_core_tile(&ctx, 0, 0, 2, 2, white);
    jpeg_draw_core_tile(&ctx, 2, 0, 2, 2, black);
    jpeg_draw_core_flush(&ctx, 2); // real image height = 2, final flush
    jpeg_draw_core_finish(&ctx);

    for (int y = 0; y < 2; y++) {
        assert(get_mono_pixel(fb, 8, 0, y) == 0);
        assert(get_mono_pixel(fb, 8, 1, y) == 0);
        assert(get_mono_pixel(fb, 8, 2, y) == 1);
        assert(get_mono_pixel(fb, 8, 3, y) == 1);
    }
    printf("test_mono_dither_band_flush_across_tiles: passed\n");
}

static void test_mono_dither_multi_band_auto_flush(void)
{
    // A tile at tile_y=2 starting while band_y0==0 must trigger an automatic flush of
    // the first band before the second band's data overwrites the shared static
    // buffer -- this is the one branch a single-band test can't reach.
    uint8_t fb[4] = {0};                        // phys_w=8, phys_h=4 -> 1 byte/row, 4 rows
    uint8_t white[8 * 2 * 3], black[8 * 2 * 3]; // full-width (8x2) tiles, one per band
    fill_tile_rgb(white, 8, 2, 255, 255, 255);
    fill_tile_rgb(black, 8, 2, 0, 0, 0);

    jpeg_draw_core_ctx_t ctx;
    jpeg_draw_core_init(&ctx, fb, 8, 4, 0, 0, 0, 0, /*invert=*/0, /*dither=*/1,
                        DITHER_KERNEL_FLOYD_STEINBERG);
    jpeg_draw_core_tile(&ctx, 0, 0, 8, 2, white); // band 1 (y=0..1): all white
    jpeg_draw_core_tile(&ctx, 0, 2, 8, 2, black); // band 2 (y=2..3): triggers band-1 auto-flush
    jpeg_draw_core_flush(&ctx, 4);                // final flush for band 2
    jpeg_draw_core_finish(&ctx);

    for (int x = 0; x < 8; x++) {
        assert(get_mono_pixel(fb, 8, x, 0) == 0); // band 1: white
        assert(get_mono_pixel(fb, 8, x, 1) == 0);
        assert(get_mono_pixel(fb, 8, x, 2) == 1); // band 2: black
        assert(get_mono_pixel(fb, 8, x, 3) == 1);
    }
    printf("test_mono_dither_multi_band_auto_flush: passed\n");
}

static void test_gs4_no_dither_levels(void)
{
    uint8_t fb[2] = {0}; // phys_w=4, phys_h=2, GS4 -> w/2=2 bytes/row
    uint8_t white[1 * 1 * 3] = {255, 255, 255};
    uint8_t black[1 * 1 * 3] = {0, 0, 0};

    jpeg_draw_core_ctx_t ctx;
    jpeg_draw_core_init(&ctx, fb, 4, 2, 0, /*display_mode=*/1, 0, 0, /*invert=*/0, /*dither=*/0,
                        DITHER_KERNEL_FLOYD_STEINBERG);
    jpeg_draw_core_tile(&ctx, 0, 0, 1, 1, white);
    jpeg_draw_core_tile(&ctx, 1, 0, 1, 1, black);

    assert(get_gs4_pixel(fb, 4, 0, 0) == 7); // lightest
    assert(get_gs4_pixel(fb, 4, 1, 0) == 0); // darkest
    printf("test_gs4_no_dither_levels: passed\n");
}

static void test_invert_flips_mono(void)
{
    uint8_t fb[1] = {0}; // phys_w=8, phys_h=1
    uint8_t white[1 * 1 * 3] = {255, 255, 255};

    jpeg_draw_core_ctx_t ctx;
    jpeg_draw_core_init(&ctx, fb, 8, 1, 0, 0, 0, 0, /*invert=*/1, /*dither=*/0,
                        DITHER_KERNEL_FLOYD_STEINBERG);
    jpeg_draw_core_tile(&ctx, 0, 0, 1, 1, white);

    // Without invert, white -> level 0. With invert (inv_mask=1 for mono), level ^= 1 -> 1.
    assert(get_mono_pixel(fb, 8, 0, 0) == 1);
    printf("test_invert_flips_mono: passed\n");
}

// --- palette path ---

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

static void test_palette_no_dither_exact_matches(void)
{
    capture_t cap = {0};
    uint8_t red[1 * 1 * 3] = {255, 0, 0};
    uint8_t green[1 * 1 * 3] = {0, 255, 0};

    jpeg_draw_core_palette_ctx_t ctx;
    jpeg_draw_core_palette_init(&ctx, /*invert=*/0, /*dither=*/0, DITHER_KERNEL_FLOYD_STEINBERG,
                                palette_6color, PALETTE_N, capture_cb, &cap);
    jpeg_draw_core_palette_tile(&ctx, 0, 0, 1, 1, red);
    jpeg_draw_core_palette_tile(&ctx, 1, 0, 1, 1, green);

    assert(cap.calls == 2);
    assert(cap.values[0][0] == 4); // red
    assert(cap.values[0][1] == 2); // green
    printf("test_palette_no_dither_exact_matches: passed\n");
}

static void test_palette_dither_multi_band_auto_flush(void)
{
    capture_t cap = {0};
    uint8_t blue[2 * 2 * 3], yellow[2 * 2 * 3];
    fill_tile_rgb(blue, 2, 2, 0, 0, 255);
    fill_tile_rgb(yellow, 2, 2, 255, 255, 0);

    jpeg_draw_core_palette_ctx_t ctx;
    jpeg_draw_core_palette_init(&ctx, /*invert=*/0, /*dither=*/1, DITHER_KERNEL_FLOYD_STEINBERG,
                                palette_6color, PALETTE_N, capture_cb, &cap);
    jpeg_draw_core_palette_tile(&ctx, 0, 0, 2, 2, blue); // band 1 (y=0..1)
    jpeg_draw_core_palette_tile(&ctx, 0, 2, 2, 2,
                                yellow); // band 2 (y=2..3) -- auto-flushes band 1
    jpeg_draw_core_palette_flush(&ctx, 4);
    jpeg_draw_core_palette_finish(&ctx);

    assert(cap.calls == 8);
    for (int x = 0; x < 2; x++) {
        assert(cap.values[0][x] == 3); // blue
        assert(cap.values[1][x] == 3);
        assert(cap.values[2][x] == 5); // yellow
        assert(cap.values[3][x] == 5);
    }
    printf("test_palette_dither_multi_band_auto_flush: passed\n");
}

static void test_palette_invert_swaps_black_white_only(void)
{
    capture_t cap = {0};
    uint8_t red[1 * 1 * 3] = {255, 0, 0};

    jpeg_draw_core_palette_ctx_t ctx;
    jpeg_draw_core_palette_init(&ctx, /*invert=*/1, /*dither=*/0, DITHER_KERNEL_FLOYD_STEINBERG,
                                palette_6color, PALETTE_N, capture_cb, &cap);
    jpeg_draw_core_palette_tile(&ctx, 0, 0, 1, 1, red);

    assert(cap.values[0][0] == 4); // red untouched by invert (same contract as dither.h)
    printf("test_palette_invert_swaps_black_white_only: passed\n");
}

int main(void)
{
    test_mono_no_dither_immediate();
    test_mono_dither_band_flush_across_tiles();
    test_mono_dither_multi_band_auto_flush();
    test_gs4_no_dither_levels();
    test_invert_flips_mono();
    test_palette_no_dither_exact_matches();
    test_palette_dither_multi_band_auto_flush();
    test_palette_invert_swaps_black_white_only();
    printf("test_jpeg_draw_core: all assertions passed\n");
    return 0;
}
