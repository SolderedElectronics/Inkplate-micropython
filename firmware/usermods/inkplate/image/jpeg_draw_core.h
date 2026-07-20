/**
 * @file jpeg_draw_core.h
 * @brief Per-tile/per-band dither+quantize+blit logic for JPEG rendering.
 *
 * Deliberately decode-agnostic (no jpeg_decode.h/ROM-tjpgd dependency) so this logic
 * can be exercised on host by tests/test_jpeg_draw_core.c, independent of the real
 * decoder. jpeg_draw.c is the thin ESP-IDF-dependent wrapper that drives jpeg_decode()
 * and forwards each decoded tile here.
 */
#ifndef INKPLATE_JPEG_DRAW_CORE_H
#define INKPLATE_JPEG_DRAW_CORE_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Row-band buffer width cap, shared with jpeg_draw.c's pre-decode callback (which rejects
// wider images before any tile arrives -- see jpeg_draw_core_band_max_w()). Aliases
// dither.h's INKPLATE_DRAW_MAX_WIDTH, the widest-board cap, so it stays one shared constant
// across bmp_draw.c/jpeg_draw_core.h/png_draw_core.h instead of independently-chosen numbers
// that can drift out of sync with each other.
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

/**
 * @brief Initializes a grayscale/mono JPEG draw context.
 * @param ctx Context to initialize.
 * @param fb Framebuffer to write into.
 * @param phys_w Physical display width, in pixels.
 * @param phys_h Physical display height, in pixels.
 * @param rotation Display rotation passed through to gfx_set_pixel.
 * @param display_mode Display mode passed through to gfx_set_pixel.
 * @param x0 Destination X origin for the image.
 * @param y0 Destination Y origin for the image.
 * @param invert Non-zero to invert pixel levels.
 * @param dither Non-zero to enable error-diffusion dithering.
 * @param kernel_type Dither kernel selection.
 */
void jpeg_draw_core_init(jpeg_draw_core_ctx_t *ctx, uint8_t *fb, int phys_w, int phys_h,
                         int rotation, int display_mode, int x0, int y0, int invert, int dither,
                         int kernel_type);

/**
 * @brief Processes one decoded MCU tile into the grayscale draw context.
 *
 * Tiles for a given row-band must arrive fully (tjpgd's raster order guarantee) before the
 * next band's first tile -- same contract jpeg_decode.h's jpeg_tile_cb_t documents.
 *
 * @param ctx Grayscale draw context.
 * @param tile_x Tile origin X, in full-image pixel coordinates.
 * @param tile_y Tile origin Y, in full-image pixel coordinates.
 * @param tile_w Tile width, in pixels.
 * @param tile_h Tile height, in pixels.
 * @param rgb Tile pixel data, RGB888 row-major, tile_w*tile_h*3 bytes.
 */
void jpeg_draw_core_tile(jpeg_draw_core_ctx_t *ctx, uint32_t tile_x, uint32_t tile_y,
                         uint32_t tile_w, uint32_t tile_h, const uint8_t *rgb);

/**
 * @brief Dithers and writes the currently-buffered band to the framebuffer.
 *
 * No-op if nothing is buffered, including when dither is off since the immediate path in
 * jpeg_draw_core_tile never buffers.
 *
 * @param ctx Grayscale draw context.
 * @param draw_height Bottom-edge bound for error diffusion; pass a large sentinel (e.g.
 * INT32_MAX) for a mid-decode flush when image height isn't known yet, or the real decoded
 * height for the final flush after decode completes.
 */
void jpeg_draw_core_flush(jpeg_draw_core_ctx_t *ctx, int draw_height);

/**
 * @brief Releases the error-diffusion context if one was allocated.
 *
 * Call once, after the final jpeg_draw_core_flush(), when ctx->dither was set.
 *
 * @param ctx Grayscale draw context.
 */
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

/**
 * @brief Initializes a palette/color JPEG draw context.
 * @param ctx Context to initialize.
 * @param invert Non-zero to invert pixel levels.
 * @param dither Non-zero to enable error-diffusion dithering.
 * @param kernel_type Dither kernel selection.
 * @param palette Target color palette entries.
 * @param palette_n Number of entries in palette.
 * @param write_pixel Callback invoked to write each output pixel.
 * @param cb_ctx Opaque context passed to write_pixel.
 */
void jpeg_draw_core_palette_init(jpeg_draw_core_palette_ctx_t *ctx, int invert, int dither,
                                 int kernel_type, const dither_palette_entry_t *palette,
                                 int palette_n, jpeg_draw_core_palette_write_cb write_pixel,
                                 void *cb_ctx);

/**
 * @brief Processes one decoded MCU tile into the palette draw context.
 *
 * Same raster-order tile contract as jpeg_draw_core_tile().
 *
 * @param ctx Palette draw context.
 * @param tile_x Tile origin X, in full-image pixel coordinates.
 * @param tile_y Tile origin Y, in full-image pixel coordinates.
 * @param tile_w Tile width, in pixels.
 * @param tile_h Tile height, in pixels.
 * @param rgb Tile pixel data, RGB888 row-major, tile_w*tile_h*3 bytes.
 */
void jpeg_draw_core_palette_tile(jpeg_draw_core_palette_ctx_t *ctx, uint32_t tile_x,
                                 uint32_t tile_y, uint32_t tile_w, uint32_t tile_h,
                                 const uint8_t *rgb);

/**
 * @brief Dithers and writes the currently-buffered palette band to the output.
 *
 * No-op if nothing is buffered, including when dither is off.
 *
 * @param ctx Palette draw context.
 * @param draw_height Bottom-edge bound for error diffusion; pass a large sentinel (e.g.
 * INT32_MAX) for a mid-decode flush when image height isn't known yet, or the real decoded
 * height for the final flush after decode completes.
 */
void jpeg_draw_core_palette_flush(jpeg_draw_core_palette_ctx_t *ctx, int draw_height);

/**
 * @brief Releases the error-diffusion context if one was allocated.
 *
 * Call once, after the final jpeg_draw_core_palette_flush(), when ctx->dither was set.
 *
 * @param ctx Palette draw context.
 */
void jpeg_draw_core_palette_finish(jpeg_draw_core_palette_ctx_t *ctx);

#endif // INKPLATE_JPEG_DRAW_CORE_H
