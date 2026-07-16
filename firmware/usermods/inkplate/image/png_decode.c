#include "png_decode.h"

#include "pngle.h"

typedef struct {
    png_pixel_cb_t cb;
    void *ctx;
} png_session_t;

// pngle's draw callback reports a w x h block per decoded value -- always 1x1
// for non-interlaced PNGs, but wider/taller during Adam7 interlace passes
// before a later pass refines it. Expand to one call per output pixel so
// callers see a flat raster-order pixel stream regardless of interlacing.
static void png_draw_cb(pngle_t *pngle, uint32_t x, uint32_t y, uint32_t w, uint32_t h,
                        const uint8_t rgba[4])
{
    png_session_t *s = (png_session_t *)pngle_get_user_data(pngle);
    for (uint32_t dy = 0; dy < h; dy++) {
        for (uint32_t dx = 0; dx < w; dx++) {
            s->cb(s->ctx, x + dx, y + dy, rgba);
        }
    }
}

int png_decode(const uint8_t *buf, size_t len, png_pixel_cb_t cb, void *ctx, uint32_t *out_width,
               uint32_t *out_height)
{
    pngle_t *pngle = pngle_new();
    if (pngle == NULL) {
        return -1;
    }

    png_session_t s = {.cb = cb, .ctx = ctx};
    pngle_set_user_data(pngle, &s);
    pngle_set_draw_callback(pngle, png_draw_cb);

    size_t pos = 0;
    int ok = 1;
    while (pos < len) {
        int eaten = pngle_feed(pngle, buf + pos, len - pos);
        if (eaten <= 0) {
            // -1: pngle reported an error; 0 with input remaining: pngle stalled
            // (truncated/malformed stream) -- the whole file is already in buf,
            // so it can't just need more data.
            ok = 0;
            break;
        }
        pos += (size_t)eaten;
    }

    if (ok) {
        if (out_width != NULL) {
            *out_width = pngle_get_width(pngle);
        }
        if (out_height != NULL) {
            *out_height = pngle_get_height(pngle);
        }
    }

    pngle_destroy(pngle);
    return ok ? 0 : -1;
}

// PNG's fixed layout: 8-byte signature, then IHDR's 8-byte chunk header (4-byte
// length + 4-byte "IHDR" type), then IHDR's own data starting with a 4-byte width
// and 4-byte height (both big-endian) -- every valid PNG has this at the exact
// same offset (IHDR is required to be the first chunk), so width/height can be
// read directly without involving pngle/the real decoder at all. Doesn't validate
// the signature or chunk type -- a malformed file just gets caught later by the
// real png_decode() call; this is only a fast-path peek.
int png_peek_dimensions(const uint8_t *buf, size_t len, uint32_t *out_width, uint32_t *out_height)
{
    if (len < 24) {
        return -1;
    }
    *out_width = ((uint32_t)buf[16] << 24) | ((uint32_t)buf[17] << 16) |
                 ((uint32_t)buf[18] << 8) | buf[19];
    *out_height = ((uint32_t)buf[20] << 24) | ((uint32_t)buf[21] << 16) |
                  ((uint32_t)buf[22] << 8) | buf[23];
    return 0;
}

// IHDR's data (after the 16-byte signature+chunk-header prefix png_peek_dimensions
// already explains) is width(4) height(4) bit depth(1) color type(1) compression
// method(1) filter method(1) interlace method(1) -- so the interlace byte sits at a
// fixed offset (28) right after the two fields png_peek_dimensions reads, same
// no-pngle fast-path peek.
int png_peek_interlace(const uint8_t *buf, size_t len, uint8_t *out_interlace)
{
    if (len < 29) {
        return -1;
    }
    *out_interlace = buf[28];
    return 0;
}
