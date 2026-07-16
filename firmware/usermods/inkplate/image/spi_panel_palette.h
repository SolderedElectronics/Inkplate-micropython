// Per-board palette tables + pixel packing for the SPI-controller-panel family's
// color/palette image-decode path (docs/REFACTOR-PLAN.md Phase 10 step 32/33).
//
// Deliberately NOT routed through gfx_set_pixel's GS4 packing (gfx.c): confirmed
// against each board's current shipped viper code that 6COLOR/13SPECTRA pack pixels
// into a nibble in the OPPOSITE order gfx_set_pixel's GS4 branch uses (even physical
// column -> high nibble here, vs. low nibble there), and each panel's rotation/
// coordinate-remap formula is its own board-specific quirk (6COLOR bakes a fixed
// "rotation 0" orientation with pre-flip done in the decode step, 13SPECTRA bakes a
// fixed "rotation 1" mapping with its own sign convention, Inkplate2 alone honors
// `rotation` dynamically, over two separate 1bpp bitplanes instead of one indexed
// buffer). This module ports each of those, verbatim, per board -- it does not
// attempt to unify them under one convention.
#ifndef INKPLATE_SPI_PANEL_PALETTE_H
#define INKPLATE_SPI_PANEL_PALETTE_H

#include <stdint.h>

#include "dither.h"

enum {
    SPI_PANEL_PALETTE_INKPLATE6COLOR = 0,
    SPI_PANEL_PALETTE_INKPLATE2 = 1,
    SPI_PANEL_PALETTE_INKPLATE13SPECTRA = 2,
};

// Maps a board name ("inkplate6color"/"inkplate2"/"inkplate13spectra", matching
// spi_panel_config_t.name) to its SPI_PANEL_PALETTE_* id, or -1 if unrecognized.
int spi_panel_palette_id_for_name(const char *name);

// Returns the fixed nearest-color palette table for `panel` (a SPI_PANEL_PALETTE_*
// id) via *out_n (entry count) and the return value (the table itself, static
// storage). RGB values and their `value` outputs are transcribed verbatim from that
// board's current viper nearest-color search -- already HIL-validated per Phase 9
// step 30's real-image draw on 6COLOR -- not re-derived from the Arduino reference.
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

// bmp_draw_palette_cb/jpeg_draw_palette_cb/png_draw_palette_cb-compatible callback:
// packs `value` into ctx's framebuffer(s) at image-local (x, y), applying that
// panel's own real coordinate remap + nibble/bitplane packing (see module comment
// above). `ctx` must point to a spi_panel_palette_ctx_t.
void spi_panel_palette_write_pixel(void *ctx, int x, int y, int value);

#endif // INKPLATE_SPI_PANEL_PALETTE_H
