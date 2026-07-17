// Pure per-tile/per-band dither+quantize+blit logic for JPEG rendering, deliberately
// decode-agnostic (no jpeg_decode.h/ROM-tjpgd dependency) so it host-compiles/tests --
// see tests/test_jpeg_draw_core.c. jpeg_draw.c is the thin ESP-IDF-dependent wrapper that
// drives the real jpeg_decode() and forwards each decoded tile here; this split exists
// only so the tile-in/pixels-out logic has test coverage the real decoder can't give it
// on host (docs/REFACTOR-PLAN.md Phase 12 test-hardening pass).
#ifndef INKPLATE_JPEG_DRAW_CORE_H
#define INKPLATE_JPEG_DRAW_CORE_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Row-band buffer width cap, shared with jpeg_draw.c's pre-decode callback (which rejects
// wider images before any tile arrives -- see jpeg_draw_core_band_max_w()). Aliases
// dither.h's INKPLATE_DRAW_MAX_WIDTH -- the widest-board cap is one shared constant across
// bmp_draw.c/jpeg_draw_core.h/png_draw_core.h, not three independently-chosen numbers that
// can drift out of sync with each other (they previously did: 1200 here vs BMP's 1600,
// meaning a real Inkplate5v2-width image dithered via BMP but was wrongly rejected via
// JPEG/PNG).
#define JPEG_DRAW_CORE_BAND_MAX_W INKPLATE_DRAW_MAX_WIDTH
// Largest MCU height tjpgd can produce (msy <= 2 blocks of 8px per rom/tjpgd.h -- standard
// JPEG subsampling never exceeds a 2x2-block MCU).
#define JPEG_DRAW_CORE_MCU_MAX_H 16

// --- Grayscale/mono (writes straight into a gfx.h framebuffer) ---

typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    int dither;
    int kernel_type;
    int band_y0; // image row where the buffered band starts, -1 if nothing buffered
    int band_h;  // valid rows in the band buffer (this band's MCU tile height)
    int band_w;  // widest x+w seen so far this band -- equals the real image width
                 // once a band's tiles have all arrived
    dither_ctx_t dctx;
    // -1: not yet attempted (band_w, needed to size dctx, isn't known until the first
    // band completes); 0: attempted and failed (degrade to non-diffused quantization);
    // 1: ready.
    int have_dctx;
} jpeg_draw_core_ctx_t;

void jpeg_draw_core_init(jpeg_draw_core_ctx_t *ctx, uint8_t *fb, int phys_w, int phys_h,
                         int rotation, int display_mode, int x0, int y0, int invert, int dither,
                         int kernel_type);

// Processes one decoded MCU tile (RGB888, tile_w*tile_h*3 bytes, row-major) whose origin is
// (tile_x, tile_y) in full-image pixel coords. Tiles for a given row-band must arrive fully
// (tjpgd's raster order guarantee) before the next band's first tile -- same contract
// jpeg_decode.h's jpeg_tile_cb_t documents.
void jpeg_draw_core_tile(jpeg_draw_core_ctx_t *ctx, uint32_t tile_x, uint32_t tile_y,
                         uint32_t tile_w, uint32_t tile_h, const uint8_t *rgb);

// Dithers+writes the currently-buffered band (a no-op if nothing is buffered, and if
// dither is off since the immediate path in jpeg_draw_core_tile never buffers). `draw_height`
// bounds bottom-edge error diffusion -- pass a large sentinel (e.g. INT32_MAX) for a
// mid-decode flush (image height isn't known yet) and the real decoded height for the
// final flush after decode completes.
void jpeg_draw_core_flush(jpeg_draw_core_ctx_t *ctx, int draw_height);

// Releases the error-diffusion context if one was allocated. Call once, after the final
// jpeg_draw_core_flush(), when ctx->dither was set.
void jpeg_draw_core_finish(jpeg_draw_core_ctx_t *ctx);

// --- Palette/color (writes through a caller-supplied write_pixel callback) ---

typedef void (*jpeg_draw_core_palette_write_cb)(void *cb_ctx, int x, int y, int value);

typedef struct {
    int invert;
    int dither;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    int black_value, white_value; // from dither_find_bw_values, computed once at init
    jpeg_draw_core_palette_write_cb write_pixel;
    void *cb_ctx;
    int band_y0;
    int band_h;
    int band_w;
    dither_rgb_ctx_t dctx;
    int have_dctx;
} jpeg_draw_core_palette_ctx_t;

void jpeg_draw_core_palette_init(jpeg_draw_core_palette_ctx_t *ctx, int invert, int dither,
                                 int kernel_type, const dither_palette_entry_t *palette,
                                 int palette_n, jpeg_draw_core_palette_write_cb write_pixel,
                                 void *cb_ctx);

void jpeg_draw_core_palette_tile(jpeg_draw_core_palette_ctx_t *ctx, uint32_t tile_x,
                                 uint32_t tile_y, uint32_t tile_w, uint32_t tile_h,
                                 const uint8_t *rgb);

void jpeg_draw_core_palette_flush(jpeg_draw_core_palette_ctx_t *ctx, int draw_height);

void jpeg_draw_core_palette_finish(jpeg_draw_core_palette_ctx_t *ctx);

#endif // INKPLATE_JPEG_DRAW_CORE_H
