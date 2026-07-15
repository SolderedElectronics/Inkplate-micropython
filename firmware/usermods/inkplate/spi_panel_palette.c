#include "spi_panel_palette.h"

#include <string.h>

// Verbatim from boards/inkplate6color/inkplate6_color.py's write_image nearest-color
// search (unrolled black/white/green/blue/red/yellow/orange comparisons) -- `value`
// equals array index here since this panel's controller has no register-value gaps.
static const dither_palette_entry_t palette_inkplate6color[] = {
    {0, 0, 0, 0},       // black
    {255, 255, 255, 1}, // white
    {0, 255, 0, 2},     // green
    {0, 0, 255, 3},     // blue
    {255, 0, 0, 4},     // red
    {255, 255, 0, 5},   // yellow
    {255, 165, 0, 6},   // orange
};

// Verbatim from boards/inkplate13spectra/inkplate13_spectra.py's write_image
// nearest-color search. Register value 4 is skipped (unused by this Spectra133
// controller) -- matches this board's own `_color_palette = [0, 1, 2, 3, 5, 6]`.
static const dither_palette_entry_t palette_inkplate13spectra[] = {
    {0, 0, 0, 0},       // black
    {255, 255, 255, 1}, // white
    {255, 255, 0, 2},   // yellow
    {255, 0, 0, 3},     // red
    {0, 0, 255, 5},     // blue
    {0, 255, 0, 6},     // green
};

// Inkplate2 is a 3-color BWR panel (WHITE=0, BLACK=1, RED=2 -- see write_pixel/the
// class constants in boards/inkplate2/inkplate2.py); its current viper decode paths
// use ad hoc RGB-threshold heuristics instead of a real nearest-color search (and
// disagree with each other -- the JPEG path's classifier even swaps black/white
// relative to the real WHITE=0/BLACK=1 constants before writing). This table is the
// intended generalization per docs/REFACTOR-PLAN.md Phase 10 step 32 (nearest-RGB
// search over the panel's real palette), not a byte-for-byte port of any one of
// those inconsistent heuristics -- verify red classification against real red ink
// on hardware (HIL), since it may shift which borderline reddish-brown pixels get
// called red vs. black/white compared to today's heuristics.
static const dither_palette_entry_t palette_inkplate2[] = {
    {255, 255, 255, 0}, // white
    {0, 0, 0, 1},       // black
    {255, 0, 0, 2},     // red
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
        default:
            *out_n = 0;
            return NULL;
    }
}

// 6COLOR/13SPECTRA share the same 4bpp nibble convention -- even physical column ->
// high nibble, odd -> low nibble (boards/inkplate6color/inkplate6_color.py's
// write_pixel pixel_mask_glut=[0xF,0xF0]/write_image pack, and 13SPECTRA's identical
// write_pixel/write_image pack) -- the OPPOSITE of gfx_set_pixel's GS4 branch
// (gfx.c), which puts even column in the low nibble. They differ only in the
// rotation-baked coordinate formula below.
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

// 6COLOR's write_image never reads rotation and places pixels with zero transform
// of its own -- but it only gets away with that because its callers pre-flip the
// source pixels 180 degrees during decode (bmp24_to_rgb565/png_to_rgb565's own
// explicit "180 deg rotation: flip horizontally and vertically", and the built-in
// `jpeg` module's `rotation=180` decoder setting). bmp_decode.c/png_decode.c/
// jpeg_decode.c (the shared C decoders this callback is fed from) do no such
// pre-flip -- they're generic, orientation-agnostic decoders -- so the 180 deg flip
// has to happen here instead, at pack time, to reproduce the same net placement
// that was already HIL-validated on real 6COLOR hardware (docs/REFACTOR-PLAN.md
// Phase 9 step 30). This matches write_pixel's own rotation==0 case exactly
// (`x=w-x-1, y=h-y-1`) -- this board's default/only-ever-used rotation.
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

// Ported verbatim from write_image's baked-in "rotation 1" coordinate formula
// (boards/inkplate13spectra/inkplate13_spectra.py: `phys_x = y0 + row`, `phys_y`
// decrementing from `_screen_width - 1 - x0` once per column) -- also never reads
// rotation dynamically, same reasoning as 6COLOR above. ctx->width/height here are
// the panel's physical, unrotated dimensions (1200x1600).
static void write_pixel_13spectra(const spi_panel_palette_ctx_t *ctx, int x, int y, int value)
{
    int phys_x = ctx->y0 + y;
    int phys_y = ctx->width - 1 - ctx->x0 - x;
    if (phys_x < 0 || phys_x >= ctx->width || phys_y < 0 || phys_y >= ctx->height) {
        return;
    }
    spi_panel_pack_nibble(ctx->fb, ctx->width, phys_x, phys_y, value);
}

// Ported verbatim from Inkplate2's write_pixel (boards/inkplate2/inkplate2.py) --
// the only one of the three boards whose image-decode path already honors
// `rotation` dynamically. Two separate 1bpp bitplanes (fb=BW, fb2=RED), MSB-first;
// `value` is WHITE=0/BLACK=1/RED=2, matching this board's real class constants
// (fixing, as a side effect of routing through this shared table instead of the old
// per-format heuristics, the JPEG-decode path's black/white swap bug that existed in
// the pre-port viper code).
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
        ctx->fb[position] &= (uint8_t)~(value << (7 - x_sub));
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
        case SPI_PANEL_PALETTE_INKPLATE2:
            write_pixel_inkplate2(ctx, x, y, value);
            break;
        default:
            break;
    }
}
