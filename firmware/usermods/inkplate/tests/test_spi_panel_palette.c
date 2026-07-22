// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_spi_panel_palette.c ../spi_panel_palette.c -o \
//              test_spi_panel_palette && ./test_spi_panel_palette
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../image/spi_panel_palette.h"

static void test_id_for_name(void)
{
    assert(spi_panel_palette_id_for_name("inkplate6color") == SPI_PANEL_PALETTE_INKPLATE6COLOR);
    assert(spi_panel_palette_id_for_name("inkplate2") == SPI_PANEL_PALETTE_INKPLATE2);
    assert(spi_panel_palette_id_for_name("inkplate13spectra") ==
           SPI_PANEL_PALETTE_INKPLATE13SPECTRA);
    assert(spi_panel_palette_id_for_name("inkplate7spectra") ==
           SPI_PANEL_PALETTE_INKPLATE7SPECTRA);
    assert(spi_panel_palette_id_for_name("inkplate10v1") == -1);

    printf("test_id_for_name: passed\n");
}

static void test_palette_tables(void)
{
    int n;
    const dither_palette_entry_t *p =
        spi_panel_palette_table(SPI_PANEL_PALETTE_INKPLATE6COLOR, &n);
    assert(n == 7);
    assert(p[0].r == 0 && p[0].g == 0 && p[0].b == 0 && p[0].value == 0);     // black
    assert(p[6].r == 255 && p[6].g == 165 && p[6].b == 0 && p[6].value == 6); // orange

    p = spi_panel_palette_table(SPI_PANEL_PALETTE_INKPLATE13SPECTRA, &n);
    assert(n == 6);
    // Register value 4 must not appear anywhere in this table (Spectra133 skips it).
    for (int i = 0; i < n; i++) {
        assert(p[i].value != 4);
    }
    assert(p[4].value == 5 && p[4].b == 255); // blue -> register value 5

    p = spi_panel_palette_table(SPI_PANEL_PALETTE_INKPLATE2, &n);
    assert(n == 3);
    assert(p[1].r == 0 && p[1].g == 0 && p[1].b == 0 && p[1].value == 1); // black

    p = spi_panel_palette_table(SPI_PANEL_PALETTE_INKPLATE7SPECTRA, &n);
    assert(n == 6);
    // Same register-value gap as 13SPECTRA (value 4 skipped).
    for (int i = 0; i < n; i++) {
        assert(p[i].value != 4);
    }
    assert(p[4].value == 5 && p[4].b == 255); // blue -> register value 5

    n = 0;
    assert(spi_panel_palette_table(-1, &n) == NULL);
    assert(n == 0);

    printf("test_palette_tables: passed\n");
}

static void test_write_pixel_6color(void)
{
    // width=4 -> bytes_per_row=2, height=2. write_pixel_6color bakes in a 180 deg
    // flip (px=width-1-lx, py=height-1-ly) since the generic C decoders it's fed
    // from don't pre-flip the way this board's old bmp24_to_rgb565/png_to_rgb565/
    // jpeg.Decoder(rotation=180) did.
    uint8_t fb[4] = {0};
    spi_panel_palette_ctx_t ctx = {.panel = SPI_PANEL_PALETTE_INKPLATE6COLOR,
                                   .fb = fb,
                                   .fb2 = NULL,
                                   .width = 4,
                                   .height = 2,
                                   .rotation = 0,
                                   .x0 = 0,
                                   .y0 = 0};

    // (x=0,y=0) -> px=3,py=1 (odd -> low nibble). (x=1,y=0) -> px=2,py=1 (even ->
    // high nibble). Both land in byte idx = 1*2 + 1 = 3.
    spi_panel_palette_write_pixel(&ctx, 0, 0, 5);
    spi_panel_palette_write_pixel(&ctx, 1, 0, 3);
    assert(fb[3] == 0x35);

    // x0/y0 offset shifts placement; out-of-bounds (negative or >= width/height
    // after offset) is silently dropped, not wrapped.
    ctx.x0 = -1;
    spi_panel_palette_write_pixel(&ctx, 0, 0, 7); // lx = -1, dropped
    assert(fb[3] == 0x35);                        // unchanged

    ctx.x0 = 0;
    ctx.y0 = 5;
    spi_panel_palette_write_pixel(&ctx, 0, 0, 7); // ly = 5 >= height(2), dropped
    assert(fb[3] == 0x35);

    printf("test_write_pixel_6color: passed\n");
}

static void test_write_pixel_13spectra(void)
{
    // width=4, height=4 -> bytes_per_row=2. phys_x = y0+y, phys_y = width-1-x0-x.
    uint8_t fb[8] = {0};
    spi_panel_palette_ctx_t ctx = {.panel = SPI_PANEL_PALETTE_INKPLATE13SPECTRA,
                                   .fb = fb,
                                   .fb2 = NULL,
                                   .width = 4,
                                   .height = 4,
                                   .rotation = 1, // ignored -- 13SPECTRA never reads it
                                   .x0 = 0,
                                   .y0 = 0};

    // x=0,y=0 -> phys_x=0, phys_y=3. idx = 3*2 + 0 = 6, even phys_x -> high nibble.
    spi_panel_palette_write_pixel(&ctx, 0, 0, 6);
    assert(fb[6] == 0x60);

    // x=1,y=2 -> phys_x=2, phys_y=4-1-0-1=2. idx = 2*2 + 1 = 5, even phys_x -> high
    // nibble.
    spi_panel_palette_write_pixel(&ctx, 1, 2, 3);
    assert(fb[5] == 0x30);

    // Out-of-bounds phys_y (x0+x >= width) is dropped.
    memset(fb, 0, sizeof(fb));
    spi_panel_palette_write_pixel(&ctx, 10, 0, 1);
    for (size_t i = 0; i < sizeof(fb); i++) {
        assert(fb[i] == 0);
    }

    printf("test_write_pixel_13spectra: passed\n");
}

static void test_write_pixel_7spectra(void)
{
    // Identical formula/layout to write_pixel_6color -- same 180-degree-mounted-panel
    // compensation, just a different physical resolution (800x480 vs 600x448). Reuse
    // the same 4x2 test geometry as test_write_pixel_6color to keep the expected byte
    // math identical.
    uint8_t fb[4] = {0};
    spi_panel_palette_ctx_t ctx = {.panel = SPI_PANEL_PALETTE_INKPLATE7SPECTRA,
                                   .fb = fb,
                                   .fb2 = NULL,
                                   .width = 4,
                                   .height = 2,
                                   .rotation = 0,
                                   .x0 = 0,
                                   .y0 = 0};

    // (x=0,y=0) -> px=3,py=1 (odd -> low nibble). (x=1,y=0) -> px=2,py=1 (even ->
    // high nibble). Both land in byte idx = 1*2 + 1 = 3.
    spi_panel_palette_write_pixel(&ctx, 0, 0, 5);
    spi_panel_palette_write_pixel(&ctx, 1, 0, 3);
    assert(fb[3] == 0x35);

    // Out-of-bounds is silently dropped, not wrapped.
    ctx.y0 = 5;
    spi_panel_palette_write_pixel(&ctx, 0, 0, 7); // ly = 5 >= height(2), dropped
    assert(fb[3] == 0x35);

    printf("test_write_pixel_7spectra: passed\n");
}

static void test_write_pixel_inkplate2(void)
{
    // Real physical dims (E_INK_WIDTH=104, E_INK_HEIGHT=212), matching
    // boards/inkplate2/inkplate2.py exactly so the rotation formulas are exercised
    // at their real aspect ratio (deliberately non-square, to catch an axis swap).
    const int phys_w = 104, phys_h = 212;
    uint8_t fb[(104 * 212) / 8] = {0};
    uint8_t fb2[(104 * 212) / 8] = {0};
    spi_panel_palette_ctx_t ctx = {.panel = SPI_PANEL_PALETTE_INKPLATE2,
                                   .fb = fb,
                                   .fb2 = fb2,
                                   .width = phys_w,
                                   .height = phys_h,
                                   .rotation = 2, // identity: px=lx, py=ly
                                   .x0 = 0,
                                   .y0 = 0};

    // rotation=2 is the identity case -- (0,0) maps straight to physical (0,0),
    // which is byte 0, bit 7 (MSB-first).
    memset(fb, 0, sizeof(fb));
    memset(fb2, 0, sizeof(fb2));
    spi_panel_palette_write_pixel(&ctx, 0, 0, 1); // black
    assert(fb[0] == 0x00);                        // bit cleared (black)
    assert(fb2[0] == 0x80);                       // untouched/inactive (still set)

    memset(fb, 0, sizeof(fb));
    memset(fb2, 0, sizeof(fb2));
    spi_panel_palette_write_pixel(&ctx, 0, 0, 0); // white
    assert(fb[0] == 0x80);                        // bit stays set (white)
    assert(fb2[0] == 0x80);

    memset(fb, 0, sizeof(fb));
    memset(fb2, 0, sizeof(fb2));
    spi_panel_palette_write_pixel(&ctx, 0, 0, 2); // red
    assert(fb[0] == 0x80);                        // BW plane untouched/inactive
    assert(fb2[0] == 0x00);                       // RED plane bit cleared (active)

    // rotation=1 swaps axes (logical_w=phys_h=212, logical_h=phys_w=104):
    // px = logical_h - ly - 1 = 104 - ly - 1, py = lx.
    ctx.rotation = 1;
    memset(fb, 0, sizeof(fb));
    memset(fb2, 0, sizeof(fb2));
    spi_panel_palette_write_pixel(&ctx, 3, 2, 1); // lx=3, ly=2
    // px = 104 - 2 - 1 = 101, py = 3. x_sub=101%8=5, byte_x=101/8=12.
    // position = (104/8)*3 + 12 = 13*3 + 12 = 51. mask = 1<<(7-5) = 0x04.
    assert((fb[51] & 0x04) == 0);  // cleared (black)
    assert((fb2[51] & 0x04) != 0); // untouched/inactive

    // Out-of-bounds (logical coordinate outside the rotated logical_w/h) is
    // silently dropped.
    memset(fb, 0xFF, sizeof(fb));
    memset(fb2, 0xFF, sizeof(fb2));
    ctx.rotation = 2;
    spi_panel_palette_write_pixel(&ctx, phys_w, 0, 1); // lx == logical_w, out of range
    for (size_t i = 0; i < sizeof(fb); i++) {
        assert(fb[i] == 0xFF);
        assert(fb2[i] == 0xFF);
    }

    printf("test_write_pixel_inkplate2: passed\n");
}

int main(void)
{
    test_id_for_name();
    test_palette_tables();
    test_write_pixel_6color();
    test_write_pixel_13spectra();
    test_write_pixel_7spectra();
    test_write_pixel_inkplate2();
    printf("test_spi_panel_palette: all assertions passed\n");
    return 0;
}
