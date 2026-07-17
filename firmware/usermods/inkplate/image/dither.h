// Scalar error-diffusion dithering, generalized over display_mode (mono 1bpp / 3-bit
// GS4_HMSB), ported from boards/inkplate10/inkplate10.py's write_row/write_image/
// process_image (docs/REFACTOR-PLAN.md Phase 7 step 21). Kernel tables (dx/dy/weight)
// are transcribed verbatim from write_image's fs_*/jjn_*/stucki_*/burkes_* byte arrays --
// see dither.c for a note on a pre-existing weight/divisor mismatch in the Stucki table
// that is preserved as-is, not fixed here.
//
// Two things the old Python did NOT do consistently are deliberately NOT preserved:
//  - GS3 quantization here always rounds to the nearest of 8 evenly spaced levels
//    ((gray*7+127)/255), matching the already-shipped non-dither placeholders in
//    jpeg_draw.c/png_draw.c/bmp_draw.c, instead of the old dithered path's separate
//    floor-bucket (gray>>5) -- one quantizer for both, not two that disagree.
//  - `invert` is applied as a final XOR on the quantized level, after error diffusion
//    is computed from the non-inverted reconstruction value. The old code applied
//    invert before computing the reconstruction value used for error diffusion, which
//    (since XOR-complement of an n-bit value isn't its arithmetic complement under the
//    proportional reconstruction formula) corrupted the diffused error whenever invert
//    was combined with dither.
//
// Pure logic, no MicroPython/ESP-IDF dependency -- host-compilable, see tests/test_dither.c.
#ifndef INKPLATE_DITHER_H
#define INKPLATE_DITHER_H

#include <stdint.h>

// Widest board's physical width across every board this repo supports (parallel-bus and
// SPI-controller-panel families alike) -- Inkplate5v2, 1280px (board_config.c). Single
// source of truth for the per-format row/band/whole-image scratch-buffer width caps in
// bmp_draw.c/jpeg_draw_core.h/png_draw_core.h -- those previously each hardcoded their own
// number with the same stated "widest board" rationale but disagreed (1600 vs 1200),
// meaning a real Inkplate5v2-width (1280px) image would dither fine via BMP but get
// rejected as "too wide to dither" via the equivalent JPEG/PNG. Exactly 1280, not padded
// with extra headroom: JPEG's cap sizes static internal-RAM buffers and PNG's sizes a
// PSRAM allocation already found tight on real hardware at large sizes
// (docs/REFACTOR-PLAN.md Phase 7 step 21), so this deliberately doesn't grow past what a
// real supported board actually needs.
#define INKPLATE_DRAW_MAX_WIDTH 1280

// Matches boards/inkplate10/inkplate10.py's write_image kernel_type values.
enum {
    DITHER_KERNEL_FLOYD_STEINBERG = 0,
    DITHER_KERNEL_JJN = 1,
    DITHER_KERNEL_STUCKI = 2,
    DITHER_KERNEL_BURKES = 3,
};

typedef struct {
    int width;
    int kernel_type;
    int16_t *error_current; // width entries, diffused error still owed to this row
    int16_t *error_next;    // width entries, diffused error owed to the next row
} dither_ctx_t;

// Allocates and zeroes both error rows for an image `width` pixels wide. Returns 0 on
// success, -1 on allocation failure.
int dither_ctx_init(dither_ctx_t *ctx, int width, int kernel_type);
void dither_ctx_free(dither_ctx_t *ctx);

// Quantizes an already error-corrected `gray` value (0-255) to a level for the given
// display_mode's storage convention, and returns via *out_recon the gray value that
// level represents (used by the caller to compute the residual passed to
// dither_diffuse_error). display_mode == 0 (mono, 1bpp): level 1 = dark/foreground
// (gray <= 127), level 0 = light/background -- matches the framebuf convention used by
// gfx_set_pixel (bit set = foreground). display_mode != 0 (3-bit GS, levels 0-7): level
// increases with gray, 0 = darkest, 7 = lightest.
int dither_quantize(int gray, int display_mode, int *out_recon);

// Adds this pixel's accumulated diffused error (owed to column x) to `gray`, clamped to
// 0-255.
int dither_apply_error(const dither_ctx_t *ctx, int x, int gray);

// Diffuses `delta` (the error-corrected gray minus its reconstruction value) from
// column x of the row currently being processed to neighboring columns per the
// selected kernel. `draw_width`/`draw_height` bound the diffusion -- `x`/`y` are the
// pixel's position within the drawn region (not the full image), matching the old
// code's edge handling (diffusion to a next row is dropped once y+1 >= draw_height).
void dither_diffuse_error(dither_ctx_t *ctx, int x, int y, int draw_width, int draw_height,
                          int delta);

// Swaps current/next error rows and zeroes the new "next" row. Call once per row,
// after all dither_apply_error/dither_diffuse_error calls for that row.
void dither_row_advance(dither_ctx_t *ctx);

// One-pixel mono/GS quantize+diffuse+invert, the sequence every bmp/jpeg/png_draw*.c
// caller previously duplicated inline (apply error if diffusing, quantize, diffuse the
// residual, then XOR-invert). Pass have_dctx=0 (dctx may be NULL) for the no-diffusion
// case -- immediate/non-dither call sites share this same tail. draw_w/draw_h/x/y are
// the diffusion bounds/position, same convention as dither_diffuse_error.
int dither_process_mono(dither_ctx_t *dctx, int have_dctx, int x, int y, int draw_w, int draw_h,
                        int gray, int display_mode, int invert);

// docs/REFACTOR-PLAN.md Phase 10 step 32: general N-color RGB palette path for the
// SPI color/BWR panels (Inkplate2, 6COLOR, 13SPECTRA), completing the engine above
// (mono/GS3-only) with full-RGB nearest-color search + 3-channel error diffusion.

// One palette entry: `r/g/b` is the reference color used for nearest-match search
// and (pre-invert) error-diffusion reconstruction; `value` is the raw pixel value
// written to the framebuffer for this entry. `value` is NOT always the entry's
// array index -- e.g. Inkplate13SPECTRA's controller skips register value 4, so
// its table is {0,1,2,3,5,6}, not {0,1,2,3,4,5}.
typedef struct {
    uint8_t r, g, b;
    uint8_t value;
} dither_palette_entry_t;

// Brute-force nearest-color search (squared RGB distance) over `palette` (n
// entries, n is small -- 3 to 7 across today's boards -- so brute force is cheap).
// Returns the matched entry's `value`; *out_recon_{r,g,b} receive that entry's own
// r/g/b, always computed pre-invert -- same invariant as dither_quantize/this
// file's module comment, so invert never corrupts the diffused error.
int dither_quantize_palette(int r, int g, int b, const dither_palette_entry_t *palette, int n,
                            int *out_recon_r, int *out_recon_g, int *out_recon_b);

// Scans `palette` once for its pure-black (0,0,0) and pure-white (255,255,255) entries'
// `value`s, returned via *out_black_value/*out_white_value (-1 if the palette has no
// such entry). Call once per image/draw (palette is loop-invariant across every pixel
// of a draw) and pass the results into dither_invert_palette_bw below instead of
// re-scanning the whole palette per pixel.
void dither_find_bw_values(const dither_palette_entry_t *palette, int n, int *out_black_value,
                           int *out_white_value);

// Applies invert to an already-quantized palette `value`: swaps strictly between
// black_value and white_value (from dither_find_bw_values) if `value` matches either,
// otherwise returns `value` unchanged -- chromatic entries (red, blue, ...) are
// deliberately left untouched. Replaces each color board's current invert attempt
// (XOR-ing the whole nibble against the palette's index range), which produces
// out-of-palette values whenever the entry count isn't a full 16 (true for every board
// in scope: 3/6/7 entries).
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

int dither_rgb_ctx_init(dither_rgb_ctx_t *ctx, int width, int kernel_type);
void dither_rgb_ctx_free(dither_rgb_ctx_t *ctx);
void dither_apply_error_rgb(const dither_rgb_ctx_t *ctx, int x, int *r, int *g, int *b);
void dither_diffuse_error_rgb(dither_rgb_ctx_t *ctx, int x, int y, int draw_width,
                              int draw_height, int dr, int dg, int db);
void dither_row_advance_rgb(dither_rgb_ctx_t *ctx);

// One-pixel palette/RGB quantize+diffuse+invert, the dither_process_mono counterpart
// for the palette/color path -- same duplicated-sequence consolidation, same
// have_dctx=0/dctx=NULL convention for no-diffusion call sites. black_value/white_value
// come from dither_find_bw_values, computed once by the caller (loop-invariant).
int dither_process_rgb(dither_rgb_ctx_t *dctx, int have_dctx, int x, int y, int draw_w,
                       int draw_h, int r, int g, int b, const dither_palette_entry_t *palette,
                       int n, int invert, int black_value, int white_value);

// RGB565 pack/unpack for callers that buffer a full decoded image before dithering
// (jpeg_draw.c/png_draw.c's palette-mode scratch buffers) -- storing RGB565 (2
// bytes/pixel) instead of RGB888 (3 bytes/pixel) cuts that buffer's PSRAM footprint
// by a third, same bit-expansion convention already used elsewhere in this codebase
// (e.g. boards/inkplate6color/inkplate6_color.py's old RGB565->RGB888 unpack:
// replicate the component's top bits into the low bits it's missing, rather than
// zero-filling, so full black/white stay exact and the ramp between them stays
// smooth). This is a lossy round-trip (5/6/5 bits vs. 8/8/8) -- fine for dithering
// scratch storage, which is already approximating a limited palette.
uint16_t dither_pack_rgb565(int r, int g, int b);
void dither_unpack_rgb565(uint16_t rgb565, int *out_r, int *out_g, int *out_b);

#endif // INKPLATE_DITHER_H
