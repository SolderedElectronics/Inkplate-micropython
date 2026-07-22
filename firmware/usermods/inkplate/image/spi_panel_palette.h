/**
 * @file spi_panel_palette.h
 * @brief Per-board palette tables and pixel packing for the SPI-controller-panel
 *        family's color/palette image-decode path.
 *
 * Deliberately not routed through gfx_set_pixel's GS4 packing (gfx.c):
 * 6COLOR/13SPECTRA/7SPECTRA pack pixels into a nibble in the opposite order
 * gfx_set_pixel's GS4 branch uses (even physical column -> high nibble here, vs. low
 * nibble there), and each panel's rotation/coordinate-remap formula is its own
 * board-specific quirk (6COLOR and 7SPECTRA both bake a fixed "rotation 0" orientation
 * with a pre-flip done in the decode step -- same formula, since 7SPECTRA's panel is
 * mounted rotated 180 degrees the same way 6COLOR's is -- 13SPECTRA bakes a fixed
 * "rotation 1" mapping with its own sign convention, Inkplate2 alone honors `rotation`
 * dynamically, over two separate 1bpp bitplanes instead of one indexed buffer). Each
 * board is handled on its own terms rather than unified under one shared convention.
 */
#ifndef INKPLATE_SPI_PANEL_PALETTE_H
#define INKPLATE_SPI_PANEL_PALETTE_H

#include <stdint.h>

#include "dither.h"

enum {
    SPI_PANEL_PALETTE_INKPLATE6COLOR = 0,
    SPI_PANEL_PALETTE_INKPLATE2 = 1,
    SPI_PANEL_PALETTE_INKPLATE13SPECTRA = 2,
    SPI_PANEL_PALETTE_INKPLATE7SPECTRA = 3,
};

/**
 * @brief Look up the SPI_PANEL_PALETTE_* id for a board name.
 * @param name Board name ("inkplate6color"/"inkplate2"/"inkplate13spectra"/
 *        "inkplate7spectra"), matching spi_panel_config_t.name.
 * @return SPI_PANEL_PALETTE_* id, or -1 if unrecognized.
 */
int spi_panel_palette_id_for_name(const char *name);

// RGB values and their `value` outputs match each board's own nearest-color search
// exactly, not re-derived generically.
/**
 * @brief Get the fixed nearest-color palette table for a panel.
 * @param panel SPI_PANEL_PALETTE_* id.
 * @param out_n Set to the number of entries in the returned table.
 * @return Pointer to the palette table (static storage), or NULL if `panel` is
 *         unrecognized.
 */
const dither_palette_entry_t *spi_panel_palette_table(int panel, int *out_n);

typedef struct {
    int panel; // SPI_PANEL_PALETTE_* id

    uint8_t *fb;  // primary framebuffer: 6COLOR/13SPECTRA's single indexed buffer,
                  // or Inkplate2's black/white bitplane.
    uint8_t *fb2; // Inkplate2 only: its red bitplane. Unused (NULL) for the other
                  // two boards.

    int width, height; // panel's PHYSICAL (unrotated) pixel dimensions, i.e.
                       // spi_panel_config_t's own width/height.
    int rotation;      // current display rotation (0-3). Honored dynamically only
                       // for Inkplate2, matching its existing write_pixel; ignored
                       // for 6COLOR/13SPECTRA (fixed orientation), matching their
                       // existing write_image, which never read rotation either.
    int x0, y0;        // draw offset, pre-rotation/logical coordinates
} spi_panel_palette_ctx_t;

// bmp_draw_palette_cb/jpeg_draw_palette_cb/png_draw_palette_cb-compatible callback,
// applying each panel's own coordinate remap and nibble/bitplane packing (see
// module comment above).
/**
 * @brief Write a palette-indexed pixel into a panel's framebuffer(s).
 * @param ctx Pointer to a spi_panel_palette_ctx_t.
 * @param x Image-local x coordinate.
 * @param y Image-local y coordinate.
 * @param value Palette index/register value to write, per the panel's palette table.
 */
void spi_panel_palette_write_pixel(void *ctx, int x, int y, int value);

#endif // INKPLATE_SPI_PANEL_PALETTE_H
