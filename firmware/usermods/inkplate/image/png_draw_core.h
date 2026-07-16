// Pure per-pixel dither+quantize+blit logic for PNG rendering, deliberately decode-agnostic
// (no png_decode.h/pngle/ROM-miniz dependency) so it host-compiles/tests -- see
// tests/test_png_draw_core.c. png_draw.c is the thin ESP-IDF-dependent wrapper that drives
// the real png_decode()/png_peek_dimensions/png_peek_interlace and forwards each decoded
// pixel here; this split exists only so the pixel-in/pixels-out logic has test coverage the
// real decoder can't give it on host (docs/REFACTOR-PLAN.md Phase 12 test-hardening pass).
#ifndef INKPLATE_PNG_DRAW_CORE_H
#define INKPLATE_PNG_DRAW_CORE_H

#include <stddef.h>
#include <stdint.h>

#include "dither.h"

// Whole-image buffered-path cap (Adam7-interlaced sources only -- see png_draw.c/png_draw.h).
// Width aliases dither.h's INKPLATE_DRAW_MAX_WIDTH -- one shared widest-board cap across
// bmp_draw.c/jpeg_draw_core.h/png_draw_core.h, not three independently-chosen numbers (this
// one previously said 1200, disagreeing with BMP's 1600 for the same stated "widest board"
// rationale). Height (825, Inkplate10's) is a separate, height-only cap, not part of that
// disagreement -- left as its own constant.
#define PNG_DRAW_CORE_MAX_WIDTH INKPLATE_DRAW_MAX_WIDTH
#define PNG_DRAW_CORE_MAX_HEIGHT 825

// --- Mono/GS4 (writes straight into a gfx.h framebuffer) ---

// Buffered path (Adam7-interlaced sources): pixels accumulate into a caller-owned
// PNG_DRAW_CORE_MAX_WIDTH x PNG_DRAW_CORE_MAX_HEIGHT luma buffer during decode, then
// png_draw_core_dither_pass runs the real dither+blit in one guaranteed row-major sweep
// after decode completes.
typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    int dither;
    int kernel_type;
    uint8_t *luma; // [y * PNG_DRAW_CORE_MAX_WIDTH + x], caller-owned, only read if dither is set
    int oversized; // set if a pixel ever falls outside the PNG_DRAW_CORE_MAX_* cap
} png_draw_core_ctx_t;

void png_draw_core_init(png_draw_core_ctx_t *ctx, uint8_t *fb, int phys_w, int phys_h,
                        int rotation, int display_mode, int x0, int y0, int invert, int dither,
                        int kernel_type, uint8_t *luma);

// Matches png_decode.h's png_pixel_cb_t signature (void(*)(void*, uint32_t, uint32_t, const
// uint8_t[4])) structurally, without including that header -- see png_draw.c.
void png_draw_core_pixel(png_draw_core_ctx_t *ctx, uint32_t x, uint32_t y, const uint8_t rgba[4]);

// Runs after decode completes: dithers the buffered luma (w x h, both <= PNG_DRAW_CORE_MAX_*)
// in one guaranteed row-major pass and writes the result into fb. Falls back to plain
// (non-diffused) quantization if the error-diffusion context can't be allocated, so a
// transient OOM degrades to a banded image instead of a blank one. No-op (and no allocation)
// when ctx->dither is 0 -- see png_draw.c, which only calls this when dither was requested.
void png_draw_core_dither_pass(png_draw_core_ctx_t *ctx, uint32_t w, uint32_t h);

// Streamed path (the common, non-interlaced case): pngle delivers every pixel in one
// strictly raster-order sweep, so error diffusion runs inline per pixel -- no whole-image
// buffer, no PNG_DRAW_CORE_MAX_* cap.
typedef struct {
    uint8_t *fb;
    int phys_w, phys_h, rotation, display_mode;
    int x0, y0;
    int invert;
    uint32_t width, height;
    dither_ctx_t dctx;
    int have_dctx;
    int cur_row;   // -1 until the first pixel is seen
    int oversized; // set if a pixel ever falls outside width/height
} png_draw_core_stream_ctx_t;

// Allocates the error-diffusion context up front (width is already known from
// png_peek_dimensions before decode starts, unlike the row-band-buffered paths in
// jpeg_draw_core.c, which must defer allocation until a band's width is known). Falls back
// to plain (non-diffused) quantization if allocation fails -- ctx->have_dctx reflects which
// happened; degrade-not-fail, same philosophy as png_draw_core_dither_pass.
void png_draw_core_stream_init(png_draw_core_stream_ctx_t *ctx, uint8_t *fb, int phys_w,
                               int phys_h, int rotation, int display_mode, int x0, int y0,
                               int invert, uint32_t width, uint32_t height, int kernel_type);

void png_draw_core_pixel_stream(png_draw_core_stream_ctx_t *ctx, uint32_t x, uint32_t y,
                                const uint8_t rgba[4]);

// Releases the error-diffusion context if one was allocated. Call once after decode
// completes.
void png_draw_core_stream_finish(png_draw_core_stream_ctx_t *ctx);

// --- Palette/color (writes through a caller-supplied write_pixel callback) ---

typedef void (*png_draw_core_palette_write_cb)(void *cb_ctx, int x, int y, int value);

// Buffered path (Adam7-interlaced sources): pixels accumulate into a caller-owned RGB565
// scratch buffer (max_width x max_height, caller's choice -- see png_draw.h) during decode,
// then png_draw_core_palette_dither_pass runs the real dither+blit afterward.
typedef struct {
    int invert;
    int dither;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    png_draw_core_palette_write_cb write_pixel;
    void *cb_ctx;
    int max_width;
    int max_height;
    uint16_t *rgb; // [y * max_width + x], RGB565, caller-owned, only read if dither is set
} png_draw_core_palette_ctx_t;

void png_draw_core_palette_init(png_draw_core_palette_ctx_t *ctx, int invert, int dither,
                                int kernel_type, const dither_palette_entry_t *palette,
                                int palette_n, png_draw_core_palette_write_cb write_pixel,
                                void *cb_ctx, int max_width, int max_height, uint16_t *rgb);

void png_draw_core_palette_pixel(png_draw_core_palette_ctx_t *ctx, uint32_t x, uint32_t y,
                                 const uint8_t rgba[4]);

void png_draw_core_palette_dither_pass(png_draw_core_palette_ctx_t *ctx, uint32_t w, uint32_t h);

// Streamed palette path -- same reasoning as png_draw_core_stream_ctx_t above.
typedef struct {
    int invert;
    int kernel_type;
    const dither_palette_entry_t *palette;
    int palette_n;
    png_draw_core_palette_write_cb write_pixel;
    void *cb_ctx;
    uint32_t width, height;
    dither_rgb_ctx_t dctx;
    int have_dctx;
    int cur_row;
    int oversized;
} png_draw_core_palette_stream_ctx_t;

// Same eager-allocation reasoning as png_draw_core_stream_init above.
void png_draw_core_palette_stream_init(png_draw_core_palette_stream_ctx_t *ctx, int invert,
                                       int kernel_type, const dither_palette_entry_t *palette,
                                       int palette_n, png_draw_core_palette_write_cb write_pixel,
                                       void *cb_ctx, uint32_t width, uint32_t height);

void png_draw_core_palette_pixel_stream(png_draw_core_palette_stream_ctx_t *ctx, uint32_t x,
                                        uint32_t y, const uint8_t rgba[4]);

void png_draw_core_palette_stream_finish(png_draw_core_palette_stream_ctx_t *ctx);

#endif // INKPLATE_PNG_DRAW_CORE_H
