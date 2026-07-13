#include "dither.h"

#include <stdlib.h>

typedef struct {
    const int8_t *dx;
    const int8_t *dy;
    const int8_t *weight;
    int length;
    int divisor;
} dither_kernel_t;

// Transcribed verbatim from boards/inkplate10/inkplate10.py's write_image
// fs_*/jjn_*/stucki_*/burkes_* byte arrays. NOTE: the JJN and Stucki kernels there are
// both a 2-row truncation of their textbook 3-row form (the y+2 row is missing) --
// preserved as-is here, since that's the shipped/HIL-verified behavior being ported, not
// re-derived. For JJN, weight sum (35) still doesn't match the textbook full-kernel
// divisor (48) it's ported with, so its total diffused energy is under 1 (~73%) --
// same shape of mismatch as Stucki below. Burkes only ever had 2 rows, so its ported
// weight sum (32) does equal its divisor (32) -- it's the one kernel of the four that
// isn't under-diffusing.
static const int8_t fs_dx[] = {1, -1, 0, 1};
static const int8_t fs_dy[] = {0, 1, 1, 1};
static const int8_t fs_wt[] = {7, 3, 5, 1};

static const int8_t jjn_dx[] = {1, 2, -2, -1, 0, 1, 2};
static const int8_t jjn_dy[] = {0, 0, 1, 1, 1, 1, 1};
static const int8_t jjn_wt[] = {7, 5, 3, 5, 7, 5, 3};

// Same dx/dy as JJN. weight sum (32) doesn't match the divisor (42) it's ported with --
// the textbook Stucki kernel's full 3-row weight sum is 42, but the y+2 row (which
// would contribute the missing 10) isn't present in this truncated 2-row table, so only
// ~76% of each pixel's quantization error is actually diffused, not fixed here (see the
// module-level comment in dither.h).
static const int8_t stucki_wt[] = {8, 4, 2, 4, 8, 4, 2};

// Same dx/dy/weight as Stucki in the source, but Burkes' own textbook divisor (32)
// happens to equal this truncated table's weight sum, so unlike Stucki this one isn't
// under-diffusing.
static const int8_t burkes_wt[] = {8, 4, 2, 4, 8, 4, 2};

static const dither_kernel_t kernels[] = {
    [DITHER_KERNEL_FLOYD_STEINBERG] = {fs_dx, fs_dy, fs_wt, 4, 16},
    [DITHER_KERNEL_JJN] = {jjn_dx, jjn_dy, jjn_wt, 7, 48},
    [DITHER_KERNEL_STUCKI] = {jjn_dx, jjn_dy, stucki_wt, 7, 42},
    [DITHER_KERNEL_BURKES] = {jjn_dx, jjn_dy, burkes_wt, 7, 32},
};

int dither_ctx_init(dither_ctx_t *ctx, int width, int kernel_type)
{
    ctx->width = width;
    ctx->kernel_type = kernel_type;
    ctx->error_current = calloc((size_t)width, sizeof(int16_t));
    ctx->error_next = calloc((size_t)width, sizeof(int16_t));
    if (ctx->error_current == NULL || ctx->error_next == NULL) {
        dither_ctx_free(ctx);
        return -1;
    }
    return 0;
}

void dither_ctx_free(dither_ctx_t *ctx)
{
    free(ctx->error_current);
    free(ctx->error_next);
    ctx->error_current = NULL;
    ctx->error_next = NULL;
}

int dither_quantize(int gray, int display_mode, int *out_recon)
{
    if (display_mode == 0) {
        int level = (gray <= 127) ? 1 : 0;
        *out_recon = level ? 0 : 255;
        return level;
    }
    int level = (gray * 7 + 127) / 255;
    level = level < 0 ? 0 : (level > 7 ? 7 : level);
    *out_recon = level * 255 / 7;
    return level;
}

int dither_apply_error(const dither_ctx_t *ctx, int x, int gray)
{
    int corrected = gray + ctx->error_current[x];
    return corrected < 0 ? 0 : (corrected > 255 ? 255 : corrected);
}

void dither_diffuse_error(dither_ctx_t *ctx, int x, int y, int draw_width, int draw_height,
                          int delta)
{
    const dither_kernel_t *k = &kernels[ctx->kernel_type];
    for (int i = 0; i < k->length; i++) {
        int nx = x + k->dx[i];
        if (nx < 0 || nx >= draw_width) {
            continue;
        }
        if (k->dy[i] == 0) {
            ctx->error_current[nx] += (int16_t)((delta * k->weight[i]) / k->divisor);
        } else if (y + k->dy[i] < draw_height) {
            ctx->error_next[nx] += (int16_t)((delta * k->weight[i]) / k->divisor);
        }
    }
}

void dither_row_advance(dither_ctx_t *ctx)
{
    int16_t *tmp = ctx->error_current;
    ctx->error_current = ctx->error_next;
    ctx->error_next = tmp;
    for (int i = 0; i < ctx->width; i++) {
        ctx->error_next[i] = 0;
    }
}
