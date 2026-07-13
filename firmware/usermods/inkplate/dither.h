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

#endif // INKPLATE_DITHER_H
