/**
 * @file spi_panel_palette.c
 * @brief Palette tables and pixel-packing implementation for the SPI-controller-panel
 *        family.
 */
#include "spi_panel_palette.h"

#include <string.h>

// `value` equals array index here since this panel's controller has no
// register-value gaps.
static const dither_palette_entry_t palette_inkplate6color[] = {
    {0, 0, 0, 0},       // black
    {255, 255, 255, 1}, // white
    {0, 255, 0, 2},     // green
    {0, 0, 255, 3},     // blue
    {255, 0, 0, 4},     // red
    {255, 255, 0, 5},   // yellow
    {255, 165, 0, 6},   // orange
};

// Register value 4 is skipped -- unused by this Spectra133 controller.
static const dither_palette_entry_t palette_inkplate13spectra[] = {
    {0, 0, 0, 0},       // black
    {255, 255, 255, 1}, // white
    {255, 255, 0, 2},   // yellow
    {255, 0, 0, 3},     // red
    {0, 0, 255, 5},     // blue
    {0, 255, 0, 6},     // green
};

// Inkplate2 value encoding is WHITE=0, BLACK=1, RED=2, matching this board's real
// class constants used by write_pixel.
static const dither_palette_entry_t palette_inkplate2[] = {
    {255, 255, 255, 0}, // white
    {0, 0, 0, 1},       // black
    {255, 0, 0, 2},     // red
};

// Same GDEP-family 6-color controller/register encoding as Inkplate13SPECTRA (register
// value 4 skipped) -- confirmed against the vendor Arduino driver's colorPalette[].
static const dither_palette_entry_t palette_inkplate7spectra[] = {
    {0, 0, 0, 0},       // black
    {255, 255, 255, 1}, // white
    {255, 255, 0, 2},   // yellow
    {255, 0, 0, 3},     // red
    {0, 0, 255, 5},     // blue
    {0, 255, 0, 6},     // green
};

int spi_panel_palette_id_for_name(const char *name)
{
    if (strcmp(name, "inkplate6color") == 0) {
        return SPI_PANEL_PALETTE_INKPLATE6COLOR;
    }
    if (strcmp(name, "inkplate2") == 0) {
        return SPI_PANEL_PALETTE_INKPLATE2;
    }
    if (strcmp(name, "inkplate13spectra") == 0) {
        return SPI_PANEL_PALETTE_INKPLATE13SPECTRA;
    }
    if (strcmp(name, "inkplate7spectra") == 0) {
        return SPI_PANEL_PALETTE_INKPLATE7SPECTRA;
    }
    return -1;
}

const dither_palette_entry_t *spi_panel_palette_table(int panel, int *out_n)
{
    switch (panel) {
        case SPI_PANEL_PALETTE_INKPLATE6COLOR:
            *out_n = (int)(sizeof(palette_inkplate6color) / sizeof(palette_inkplate6color[0]));
            return palette_inkplate6color;
        case SPI_PANEL_PALETTE_INKPLATE2:
            *out_n = (int)(sizeof(palette_inkplate2) / sizeof(palette_inkplate2[0]));
            return palette_inkplate2;
        case SPI_PANEL_PALETTE_INKPLATE13SPECTRA:
            *out_n =
                (int)(sizeof(palette_inkplate13spectra) / sizeof(palette_inkplate13spectra[0]));
            return palette_inkplate13spectra;
        case SPI_PANEL_PALETTE_INKPLATE7SPECTRA:
            *out_n =
                (int)(sizeof(palette_inkplate7spectra) / sizeof(palette_inkplate7spectra[0]));
            return palette_inkplate7spectra;
        default:
            *out_n = 0;
            return NULL;
    }
}

// 6COLOR/13SPECTRA/7SPECTRA share the same 4bpp nibble convention: even physical
// column -> high nibble, odd -> low nibble -- the opposite of gfx_set_pixel's GS4
// branch (gfx.c), which puts the even column in the low nibble. They differ only in
// the rotation-baked coordinate formula below.
static void spi_panel_pack_nibble(uint8_t *fb, int width, int px, int py, int value)
{
    int bytes_per_row = width / 2;
    int idx = py * bytes_per_row + (px >> 1);
    if ((px & 1) == 0) {
        fb[idx] = (uint8_t)((fb[idx] & 0x0F) | (value << 4));
    } else {
        fb[idx] = (uint8_t)((fb[idx] & 0xF0) | (value & 0x0F));
    }
}

// This callback applies no transform of its own for 6COLOR and never reads
// rotation -- the 180-degree flip needed to reproduce the panel's real pixel
// placement happens here at pack time instead, since the shared decoders this
// callback is fed from (bmp_decode.c/png_decode.c/jpeg_decode.c) are generic and
// orientation-agnostic. Equivalent to rotation==0's `x=w-x-1, y=h-y-1` case --
// this board's default/only-ever-used rotation.
static void write_pixel_6color(const spi_panel_palette_ctx_t *ctx, int x, int y, int value)
{
    int lx = ctx->x0 + x;
    int ly = ctx->y0 + y;
    if (lx < 0 || ly < 0 || lx >= ctx->width || ly >= ctx->height) {
        return;
    }
    int px = ctx->width - 1 - lx;
    int py = ctx->height - 1 - ly;
    spi_panel_pack_nibble(ctx->fb, ctx->width, px, py, value);
}

// Identical formula to write_pixel_6color -- 7SPECTRA's panel is mounted rotated 180
// degrees inside its enclosure the same way 6COLOR's is, and this board's default (and
// only-ever-used) rotation compensates for that the same way. Kept as its own named
// function rather than aliased, matching how every other board here gets its own
// function even when the formula happens to coincide.
static void write_pixel_7spectra(const spi_panel_palette_ctx_t *ctx, int x, int y, int value)
{
    int lx = ctx->x0 + x;
    int ly = ctx->y0 + y;
    if (lx < 0 || ly < 0 || lx >= ctx->width || ly >= ctx->height) {
        return;
    }
    int px = ctx->width - 1 - lx;
    int py = ctx->height - 1 - ly;
    spi_panel_pack_nibble(ctx->fb, ctx->width, px, py, value);
}

// Bakes a fixed "rotation 1" coordinate formula and never reads rotation
// dynamically, same reasoning as 6COLOR above. ctx->width/height here are the
// panel's physical, unrotated dimensions (1200x1600).
static void write_pixel_13spectra(const spi_panel_palette_ctx_t *ctx, int x, int y, int value)
{
    int phys_x = ctx->y0 + y;
    int phys_y = ctx->width - 1 - ctx->x0 - x;
    if (phys_x < 0 || phys_x >= ctx->width || phys_y < 0 || phys_y >= ctx->height) {
        return;
    }
    spi_panel_pack_nibble(ctx->fb, ctx->width, phys_x, phys_y, value);
}

// The only one of the three boards whose image-decode path honors `rotation`
// dynamically. Two separate 1bpp bitplanes (fb=BW, fb2=RED), MSB-first; `value`
// is WHITE=0/BLACK=1/RED=2, matching this board's real class constants.
static void write_pixel_inkplate2(const spi_panel_palette_ctx_t *ctx, int x, int y, int value)
{
    int phys_w = ctx->width;
    int phys_h = ctx->height;
    int logical_w = (ctx->rotation & 1) ? phys_h : phys_w;
    int logical_h = (ctx->rotation & 1) ? phys_w : phys_h;

    int lx = ctx->x0 + x;
    int ly = ctx->y0 + y;
    if (lx < 0 || ly < 0 || lx >= logical_w || ly >= logical_h) {
        return;
    }

    int px, py;
    switch (ctx->rotation) {
        case 3:
            px = ly;
            py = logical_w - lx - 1;
            break;
        case 0:
            px = logical_w - lx - 1;
            py = logical_h - ly - 1;
            break;
        case 1:
            px = logical_h - ly - 1;
            py = lx;
            break;
        default: // 2
            px = lx;
            py = ly;
            break;
    }

    int x_sub = px % 8;
    int byte_x = px / 8;
    int position = (phys_w / 8) * py + byte_x;
    uint8_t mask = (uint8_t)(1 << (7 - x_sub));

    ctx->fb[position] |= mask;
    ctx->fb2[position] |= mask;
    if (value < 2) {
        ctx->fb[position] &= (uint8_t) ~(value << (7 - x_sub));
    } else {
        ctx->fb2[position] &= (uint8_t)~mask;
    }
}

void spi_panel_palette_write_pixel(void *ctx_, int x, int y, int value)
{
    const spi_panel_palette_ctx_t *ctx = (const spi_panel_palette_ctx_t *)ctx_;
    switch (ctx->panel) {
        case SPI_PANEL_PALETTE_INKPLATE6COLOR:
            write_pixel_6color(ctx, x, y, value);
            break;
        case SPI_PANEL_PALETTE_INKPLATE13SPECTRA:
            write_pixel_13spectra(ctx, x, y, value);
            break;
        case SPI_PANEL_PALETTE_INKPLATE7SPECTRA:
            write_pixel_7spectra(ctx, x, y, value);
            break;
        case SPI_PANEL_PALETTE_INKPLATE2:
            write_pixel_inkplate2(ctx, x, y, value);
            break;
        default:
            break;
    }
}
