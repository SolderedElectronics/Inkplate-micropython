/**
 * @file jpeg_decode.h
 * @brief JPEG decoder wrapping the ESP32 ROM's bundled TJpgDec (rom/tjpgd.h); decode
 *        logic lives in mask ROM, not in this file.
 *
 * Links against ROM symbols, so unlike bmp_decode.c/gfx.c this cannot be
 * host-gcc-compiled or unit-tested -- verification is HIL-only.
 */
#ifndef INKPLATE_JPEG_DECODE_H
#define INKPLATE_JPEG_DECODE_H

#include <stddef.h>
#include <stdint.h>

// One decoded MCU tile, RGB888, tightly packed row-major (w*h*3 bytes). Tile size is
// whatever the JPEG's subsampling/MCU geometry produces (commonly 8x8/16x16); edge
// tiles are clipped to the image bounds by the caller, not by tjpgd.
typedef struct {
    uint32_t x, y;      // tile origin, in full-image pixel coords
    uint32_t w, h;      // tile width/height
    const uint8_t *rgb; // w*h*3 bytes, RGB888, row-major
} jpeg_tile_t;

// Invoked once per decoded MCU tile, in raster order. Return 0 to abort decode early,
// nonzero to continue.
typedef int (*jpeg_tile_cb_t)(void *ctx, const jpeg_tile_t *tile);

// Invoked once, right after the JPEG header is parsed (jd_prepare) and before any
// MCU entropy decoding starts (jd_decomp) -- the expensive part. Return 0 to abort
// the decode immediately at near-zero cost, nonzero to proceed normally. Pass NULL
// to always proceed (skips this check entirely).
typedef int (*jpeg_pre_decode_cb_t)(void *ctx, uint32_t width, uint32_t height);

/**
 * @brief Decode a JPEG buffer, streaming one MCU tile at a time via callback (no
 * full-image buffer is allocated).
 * @param buf Pointer to JPEG-encoded data.
 * @param len Length of `buf` in bytes.
 * @param pre_cb Called once after the header is parsed, before entropy decoding
 * starts; return 0 to abort early, nonzero to proceed. Pass NULL to always proceed.
 * @param cb Called once per decoded tile, in raster order; return 0 to abort decode.
 * @param ctx Opaque context passed through to `pre_cb` and `cb`.
 * @param out_width Set to the image width on success (also set if `pre_cb` aborts,
 * since the header is already parsed by then).
 * @param out_height Set to the image height on success (also set if `pre_cb` aborts,
 * since the header is already parsed by then).
 * @return 0 on success, -1 on error (malformed/unsupported JPEG, ROM decode failure,
 * or `cb` returning 0), -2 if `pre_cb` aborted the decode.
 */
int jpeg_decode(const uint8_t *buf, size_t len, jpeg_pre_decode_cb_t pre_cb, jpeg_tile_cb_t cb,
                void *ctx, uint32_t *out_width, uint32_t *out_height);

#endif // INKPLATE_JPEG_DECODE_H
