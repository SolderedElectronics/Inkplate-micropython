/**
 * @file jpeg_decode.c
 * @brief JPEG decoder implementation wrapping the ESP32 ROM's TJpgDec.
 */
#include "jpeg_decode.h"

#include <stdlib.h>

#include "rom/tjpgd.h"

// Minimum scratch pool tjpgd needs for its Huffman tables/MCU buffer; this size matches
// the ROM decoder's documented working-buffer requirement.
#define JPEG_WORK_POOL_SIZE 4096

// Single struct carries both the input-stream context and the output-tile-callback
// context together: jd_decomp() keeps calling back into the input-stream side (via
// jd->infunc, stashed by jd_prepare()) while it decodes, so JDEC.device must not be
// swapped out between jd_prepare() and jd_decomp() -- cb/ctx just ride alongside the
// input state instead of replacing it.
typedef struct {
    const uint8_t *buf;
    size_t len;
    size_t pos;
    jpeg_tile_cb_t cb;
    void *ctx;
} jpeg_session_t;

static UINT jpeg_infunc(JDEC *jd, BYTE *dst, UINT n)
{
    jpeg_session_t *s = (jpeg_session_t *)jd->device;
    size_t avail = s->len - s->pos;
    size_t take = n < avail ? n : avail;
    if (dst != NULL && take > 0) {
        for (size_t i = 0; i < take; i++) {
            dst[i] = s->buf[s->pos + i];
        }
    }
    s->pos += take;
    return (UINT)take;
}

static UINT jpeg_outfunc(JDEC *jd, void *bitmap, JRECT *rect)
{
    jpeg_session_t *s = (jpeg_session_t *)jd->device;
    jpeg_tile_t tile = {
        .x = rect->left,
        .y = rect->top,
        .w = (uint32_t)(rect->right - rect->left + 1),
        .h = (uint32_t)(rect->bottom - rect->top + 1),
        .rgb = (const uint8_t *)bitmap,
    };
    return (UINT)s->cb(s->ctx, &tile);
}

int jpeg_decode(const uint8_t *buf, size_t len, jpeg_pre_decode_cb_t pre_cb, jpeg_tile_cb_t cb,
                void *ctx, uint32_t *out_width, uint32_t *out_height)
{
    void *pool = malloc(JPEG_WORK_POOL_SIZE);
    if (pool == NULL) {
        return -1;
    }

    JDEC jd;
    jpeg_session_t s = {.buf = buf, .len = len, .pos = 0, .cb = cb, .ctx = ctx};

    JRESULT res = jd_prepare(&jd, jpeg_infunc, pool, JPEG_WORK_POOL_SIZE, &s);
    if (res != JDR_OK) {
        free(pool);
        return -1;
    }

    if (out_width != NULL) {
        *out_width = jd.width;
    }
    if (out_height != NULL) {
        *out_height = jd.height;
    }

    if (pre_cb != NULL && !pre_cb(ctx, jd.width, jd.height)) {
        // Header's parsed, dimensions are known, but the caller doesn't want to pay
        // for the actual MCU entropy decoding (e.g. the image is too wide to
        // dither) -- bail here instead, before any of that work happens.
        free(pool);
        return -2;
    }

    res = jd_decomp(&jd, jpeg_outfunc, 0);
    free(pool);
    return (res == JDR_OK) ? 0 : -1;
}
