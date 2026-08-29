/**
 * @file dither.h
 * @brief Scalar error-diffusion dithering, generalized over display_mode (mono 1bpp /
 *        3-bit GS4_HMSB).
 *
 * Kernel tables (dx/dy/weight) are defined in dither.c, including a note on a
 * pre-existing weight/divisor mismatch in the Stucki table that is preserved as-is
 * here, not fixed.
 *
 * GS3 quantization always rounds to the nearest of 8 evenly spaced levels
 * ((gray*7+127)/255), so mono and GS3 draw paths share one quantizer instead of
 * disagreeing on bucket boundaries.
 *
 * `invert` is applied as a final XOR on the quantized level, after error diffusion is
 * computed from the non-inverted reconstruction value. Applying invert before computing
 * the reconstruction value would corrupt the diffused error, since the XOR-complement
 * of an n-bit value isn't its arithmetic complement under the proportional
 * reconstruction formula -- order matters here.
 *
 * Pure logic, no MicroPython/ESP-IDF dependency -- host-compilable, see
 * tests/test_dither.c.
 */
#ifndef INKPLATE_DITHER_H
#define INKPLATE_DITHER_H

#include <stdint.h>

// Widest physical panel width across supported boards. Single source of truth for the
// per-format scratch-buffer width caps in bmp_draw.c/jpeg_draw_core.h/png_draw_core.h.
// Must not be padded up for headroom: callers size static/PSRAM scratch buffers
// directly off this value, and larger sizes have been found tight on real hardware.
#define INKPLATE_DRAW_MAX_WIDTH 1600

// Selects which diffusion kernel dither_diffuse_error/dither_diffuse_error_rgb use.
enum {
    DITHER_KERNEL_FLOYD_STEINBERG = 0,
    DITHER_KERNEL_JJN = 1,
    DITHER_KERNEL_STUCKI = 2,
    DITHER_KERNEL_BURKES = 3,
};

typedef struct {
    int width;
    int kernel_type;
    int16_t *error_current; // Width entries, diffused error still owed to this row.
    int16_t *error_next;    // Width entries, diffused error owed to the next row.
} dither_ctx_t;

/**
 * @brief Allocates and zeroes both error rows for an image of the given width.
 * @param ctx Context to initialize.
 * @param width Image width in pixels.
 * @param kernel_type One of the DITHER_KERNEL_* values.
 * @return 0 on success, -1 on allocation failure.
 */
int dither_ctx_init(dither_ctx_t *ctx, int width, int kernel_type);

/**
 * @brief Frees both error rows and clears the context's pointers.
 * @param ctx Context to free.
 */
void dither_ctx_free(dither_ctx_t *ctx);

/**
 * @brief Quantizes an already error-corrected gray value to a display level.
 * @param gray Error-corrected gray value, 0-255.
 * @param display_mode 0 for mono (1bpp): level 1 = dark/foreground (gray <= 127),
 *        level 0 = light/background -- matches the framebuf convention used by
 *        gfx_set_pixel (bit set = foreground). Nonzero for 3-bit GS (levels 0-7):
 *        level increases with gray, 0 = darkest, 7 = lightest.
 * @param out_recon Receives the gray value the returned level represents, used by
 *        the caller to compute the residual passed to dither_diffuse_error.
 * @return The quantized level.
 */
int dither_quantize(int gray, int display_mode, int *out_recon);

/**
 * @brief Adds this pixel's accumulated diffused error to gray, clamped to 0-255.
 * @param ctx Dither context holding the current row's diffused error.
 * @param x Column being processed.
 * @param gray Gray value before error correction, 0-255.
 * @return Error-corrected gray value, clamped to 0-255.
 */
int dither_apply_error(const dither_ctx_t *ctx, int x, int gray);

/**
 * @brief Diffuses a quantization error to neighboring columns per the selected kernel.
 * @param ctx Dither context whose error rows receive the diffused error.
 * @param x Column of the pixel being processed, within the drawn region (not the
 *        full image).
 * @param y Row of the pixel being processed, within the drawn region.
 * @param draw_width Width of the drawn region, bounds diffusion in x.
 * @param draw_height Height of the drawn region; diffusion to a next row is
 *        dropped once y+1 >= draw_height.
 * @param delta Error-corrected gray minus its reconstruction value.
 */
void dither_diffuse_error(dither_ctx_t *ctx, int x, int y, int draw_width, int draw_height,
                          int delta);

/**
 * @brief Swaps current/next error rows and zeroes the new "next" row.
 * @param ctx Dither context to advance. Call once per row, after all
 *        dither_apply_error/dither_diffuse_error calls for that row.
 */
void dither_row_advance(dither_ctx_t *ctx);

/**
 * @brief One-pixel mono/GS quantize + diffuse + invert sequence.
 * @param dctx Dither context for error diffusion; may be NULL if have_dctx is 0.
 * @param have_dctx Nonzero to apply/diffuse error; 0 for the no-diffusion case.
 * @param x Column of the pixel being processed.
 * @param y Row of the pixel being processed.
 * @param draw_w Width of the drawn region, diffusion bound.
 * @param draw_h Height of the drawn region, diffusion bound.
 * @param gray Gray value to quantize, 0-255.
 * @param display_mode 0 for mono (1bpp), nonzero for 3-bit GS. See dither_quantize.
 * @param invert Nonzero to XOR-invert the quantized level.
 * @return The quantized (and possibly inverted) level.
 */
int dither_process_mono(dither_ctx_t *dctx, int have_dctx, int x, int y, int draw_w, int draw_h,
                        int gray, int display_mode, int invert);

// General N-color RGB palette path for color/BWR panels, complementing the
// mono/GS3-only engine above with full-RGB nearest-color search and 3-channel
// error diffusion.

// One palette entry: `r/g/b` is the reference color used for nearest-match search
// and (pre-invert) error-diffusion reconstruction; `value` is the raw pixel value
// written to the framebuffer for this entry. `value` is NOT always the entry's
// array index -- some panels skip a register value, so their table may be
// {0,1,2,3,5,6} rather than {0,1,2,3,4,5}.
typedef struct {
    uint8_t r, g, b;
    uint8_t value;
} dither_palette_entry_t;

/**
 * @brief Brute-force nearest-color search (squared RGB distance) over a palette.
 * @param r Target red channel, 0-255.
 * @param g Target green channel, 0-255.
 * @param b Target blue channel, 0-255.
 * @param palette Palette entries to search (n is small -- a handful of entries --
 *        so brute force is cheap).
 * @param n Number of entries in palette.
 * @param out_recon_r Receives the matched entry's r, always computed pre-invert so
 *        invert never corrupts the diffused error.
 * @param out_recon_g Receives the matched entry's g, pre-invert.
 * @param out_recon_b Receives the matched entry's b, pre-invert.
 * @return The matched entry's `value`.
 */
int dither_quantize_palette(int r, int g, int b, const dither_palette_entry_t *palette, int n,
                            int *out_recon_r, int *out_recon_g, int *out_recon_b);

/**
 * @brief Scans a palette for its pure-black and pure-white entries' values.
 * @param palette Palette entries to scan.
 * @param n Number of entries in palette.
 * @param out_black_value Receives the (0,0,0) entry's `value`, or -1 if absent.
 * @param out_white_value Receives the (255,255,255) entry's `value`, or -1 if absent.
 */
void dither_find_bw_values(const dither_palette_entry_t *palette, int n, int *out_black_value,
                           int *out_white_value);

/**
 * @brief Applies invert to an already-quantized palette value.
 * @param value Quantized palette value to invert.
 * @param black_value Palette value representing pure black, from dither_find_bw_values.
 * @param white_value Palette value representing pure white, from dither_find_bw_values.
 * @return white_value if value == black_value, black_value if value == white_value,
 *         otherwise value unchanged -- chromatic entries are deliberately left untouched.
 */
int dither_invert_palette_bw(int value, int black_value, int white_value);

// Three-channel (RGB) counterpart of dither_ctx_t/dither_apply_error/
// dither_diffuse_error/dither_row_advance above -- palette mode diffuses the full
// RGB error vector, not a single luma channel. error_current/next are width*3
// entries, interleaved r,g,b per column. Reuses the same kernel tables (dither.c).
typedef struct {
    int width;
    int kernel_type;
    int16_t *error_current;
    int16_t *error_next;
} dither_rgb_ctx_t;

/**
 * @brief Allocates and zeroes both RGB error rows for an image of the given width.
 * @param ctx Context to initialize.
 * @param width Image width in pixels.
 * @param kernel_type One of the DITHER_KERNEL_* values.
 * @return 0 on success, -1 on allocation failure.
 */
int dither_rgb_ctx_init(dither_rgb_ctx_t *ctx, int width, int kernel_type);

/**
 * @brief Frees both RGB error rows and clears the context's pointers.
 * @param ctx Context to free.
 */
void dither_rgb_ctx_free(dither_rgb_ctx_t *ctx);

/**
 * @brief Adds this pixel's accumulated diffused error to r/g/b, clamped to 0-255.
 * @param ctx RGB dither context holding the current row's diffused error.
 * @param x Column being processed.
 * @param r In/out red channel, 0-255.
 * @param g In/out green channel, 0-255.
 * @param b In/out blue channel, 0-255.
 */
void dither_apply_error_rgb(const dither_rgb_ctx_t *ctx, int x, int *r, int *g, int *b);

/**
 * @brief Diffuses a per-channel quantization error to neighboring columns.
 * @param ctx RGB dither context whose error rows receive the diffused error.
 * @param x Column of the pixel being processed, within the drawn region.
 * @param y Row of the pixel being processed, within the drawn region.
 * @param draw_width Width of the drawn region, bounds diffusion in x.
 * @param draw_height Height of the drawn region; diffusion to a next row is
 *        dropped once y+1 >= draw_height.
 * @param dr Error-corrected red minus its reconstruction value.
 * @param dg Error-corrected green minus its reconstruction value.
 * @param db Error-corrected blue minus its reconstruction value.
 */
void dither_diffuse_error_rgb(dither_rgb_ctx_t *ctx, int x, int y, int draw_width,
                              int draw_height, int dr, int dg, int db);

/**
 * @brief Swaps current/next RGB error rows and zeroes the new "next" row.
 * @param ctx RGB dither context to advance. Call once per row, after all
 *        dither_apply_error_rgb/dither_diffuse_error_rgb calls for that row.
 */
void dither_row_advance_rgb(dither_rgb_ctx_t *ctx);

/**
 * @brief One-pixel palette/RGB quantize + diffuse + invert sequence.
 * @param dctx RGB dither context for error diffusion; may be NULL if have_dctx is 0.
 * @param have_dctx Nonzero to apply/diffuse error; 0 for the no-diffusion case.
 * @param x Column of the pixel being processed.
 * @param y Row of the pixel being processed.
 * @param draw_w Width of the drawn region, diffusion bound.
 * @param draw_h Height of the drawn region, diffusion bound.
 * @param r Red channel to quantize, 0-255.
 * @param g Green channel to quantize, 0-255.
 * @param b Blue channel to quantize, 0-255.
 * @param palette Palette to quantize against.
 * @param n Number of entries in palette.
 * @param invert Nonzero to invert black/white via dither_invert_palette_bw.
 * @param black_value Palette value representing pure black, from dither_find_bw_values,
 *        computed once by the caller (loop-invariant).
 * @param white_value Palette value representing pure white, from dither_find_bw_values.
 * @return The quantized (and possibly inverted) palette value.
 */
int dither_process_rgb(dither_rgb_ctx_t *dctx, int have_dctx, int x, int y, int draw_w,
                       int draw_h, int r, int g, int b, const dither_palette_entry_t *palette,
                       int n, int invert, int black_value, int white_value);

// RGB565 pack/unpack for callers that buffer a full decoded image before dithering --
// storing RGB565 (2 bytes/pixel) instead of RGB888 (3 bytes/pixel) cuts that buffer's
// PSRAM footprint by a third. Unpacking replicates the component's top bits into the
// low bits it's missing, rather than zero-filling, so full black/white stay exact and
// the ramp between them stays smooth. This is a lossy round-trip (5/6/5 bits vs.
// 8/8/8) -- fine for dithering scratch storage, which is already approximating a
// limited palette.

/**
 * @brief Packs an RGB888 color into RGB565.
 * @param r Red channel, 0-255.
 * @param g Green channel, 0-255.
 * @param b Blue channel, 0-255.
 * @return Packed RGB565 value.
 */
uint16_t dither_pack_rgb565(int r, int g, int b);

/**
 * @brief Unpacks an RGB565 color into RGB888, replicating top bits into low bits.
 * @param rgb565 Packed RGB565 value.
 * @param out_r Receives the expanded red channel, 0-255.
 * @param out_g Receives the expanded green channel, 0-255.
 * @param out_b Receives the expanded blue channel, 0-255.
 */
void dither_unpack_rgb565(uint16_t rgb565, int *out_r, int *out_g, int *out_b);

#endif // INKPLATE_DITHER_H
