/**
 * @file png_decode.h
 * @brief PNG decoder, thin wrapper over pngle (MIT, kikuchan/pngle).
 *
 * Pngle's own zlib/inflate dependency (miniz.h) resolves against ESP32 ROM's bundled
 * miniz (esp_rom/include/miniz.h, exposing tinfl_decompress + mz_crc32 straight from
 * mask ROM) instead of a vendored copy. ESP-IDF-only (links against ROM symbols) --
 * can't be host-gcc built.
 */
#ifndef INKPLATE_PNG_DECODE_H
#define INKPLATE_PNG_DECODE_H

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Callback invoked once per decoded pixel, in raster order.
 * @param ctx User-supplied context pointer, passed through unchanged.
 * @param x Full-image pixel x coordinate.
 * @param y Full-image pixel y coordinate.
 * @param rgba 4-byte RGBA pixel value, always present; callers that don't care about alpha can
 * ignore rgba[3].
 */
typedef void (*png_pixel_cb_t)(void *ctx, uint32_t x, uint32_t y, const uint8_t rgba[4]);

/**
 * @brief Decode a PNG image, streaming decoded pixels through a callback.
 *
 * No full-image buffer is allocated; pixels are delivered one at a time as they're decoded.
 * @param buf Pointer to the encoded PNG data.
 * @param len Length of buf in bytes.
 * @param cb Callback invoked once per decoded pixel.
 * @param ctx User context pointer, passed through to cb unchanged.
 * @param out_width Receives the image width on success (may be NULL).
 * @param out_height Receives the image height on success (may be NULL).
 * @return 0 on success, -1 on error (malformed/truncated PNG or a decode failure reported by
 * pngle).
 */
int png_decode(const uint8_t *buf, size_t len, png_pixel_cb_t cb, void *ctx, uint32_t *out_width,
               uint32_t *out_height);

/**
 * @brief Read width/height directly out of a PNG's IHDR chunk, without running pngle.
 *
 * Lets a caller reject an oversized image before paying for any decode work. Every valid PNG
 * has IHDR at the same fixed byte offset, since IHDR is required to be the first chunk.
 * @param buf Pointer to the encoded PNG data.
 * @param len Length of buf in bytes.
 * @param out_width Receives the image width on success.
 * @param out_height Receives the image height on success.
 * @return 0 on success, -1 if buf is too short to contain IHDR (the real png_decode() call will
 * report the actual error in that case).
 */
int png_peek_dimensions(const uint8_t *buf, size_t len, uint32_t *out_width,
                        uint32_t *out_height);

/**
 * @brief Read the interlace method byte directly out of a PNG's IHDR chunk, without touching
 * pngle.
 *
 * 0 means no interlacing: pngle's draw callback delivers pixels in strict raster order,
 * top-to-bottom/left-to-right, over one single pass. 1 means Adam7: 7 passes, each re-sweeping
 * the whole image in a different sub-sampling pattern, so per-pixel order isn't monotonic across
 * the full decode. See png_draw.c for how this selects between the streamed (no interlacing) and
 * buffered (Adam7) draw paths.
 * @param buf Pointer to the encoded PNG data.
 * @param len Length of buf in bytes.
 * @param out_interlace Receives the interlace method byte on success.
 * @return 0 on success, -1 if buf is too short to contain that byte.
 */
int png_peek_interlace(const uint8_t *buf, size_t len, uint8_t *out_interlace);

#endif // INKPLATE_PNG_DECODE_H
