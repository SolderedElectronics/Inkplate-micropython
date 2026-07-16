// PNG decoder, thin wrapper over the vendored pngle.c (MIT, kikuchan/pngle) --
// pngle's own zlib/inflate dependency (miniz.h) resolves against ESP32 ROM's
// bundled miniz (esp_rom/include/miniz.h, exposing tinfl_decompress + mz_crc32
// straight from mask ROM) instead of a vendored copy, same "no porting, just
// wire in" treatment as step 18's ROM-tjpgd path. Phase 7, docs/REFACTOR-PLAN.md
// step 19. ESP-IDF-only (links against ROM symbols) -- can't be host-gcc built.
#ifndef INKPLATE_PNG_DECODE_H
#define INKPLATE_PNG_DECODE_H

#include <stddef.h>
#include <stdint.h>

// Invoked once per decoded output pixel, in raster order (x, y are full-image
// pixel coords). rgba is 4 bytes, always present -- callers that don't care
// about alpha (Phase 7 grayscale path) just ignore rgba[3].
typedef void (*png_pixel_cb_t)(void *ctx, uint32_t x, uint32_t y, const uint8_t rgba[4]);

// Decodes the PNG at buf/len, streaming one pixel at a time through `cb` (no
// full-image buffer is allocated). `out_width`/`out_height` receive the image
// dimensions on success. Returns 0 on success, -1 on error (malformed/truncated
// PNG or a decode failure reported by pngle).
int png_decode(const uint8_t *buf, size_t len, png_pixel_cb_t cb, void *ctx, uint32_t *out_width,
               uint32_t *out_height);

// Reads width/height directly out of the PNG's IHDR chunk (a fixed byte offset
// every valid PNG shares) without touching pngle/the real decoder at all -- lets
// a caller reject an oversized image before paying for any decode work. Returns 0
// on success, -1 if `buf` is too short to contain IHDR (the real png_decode()
// call will report the actual error in that case).
int png_peek_dimensions(const uint8_t *buf, size_t len, uint32_t *out_width,
                        uint32_t *out_height);

// Reads the interlace method byte directly out of the PNG's IHDR chunk (same fixed
// offset every valid PNG shares, right after width/height/bit depth/color type/
// compression method/filter method) without touching pngle -- 0 means no
// interlacing (pngle's draw callback then delivers pixels in strict raster order,
// top-to-bottom/left-to-right, over one single pass), 1 means Adam7 (7 passes, each
// re-sweeping the whole image in a different sub-sampling pattern, so per-pixel
// order isn't monotonic across the full decode). See png_draw.c for how this
// selects between the streamed (no interlacing) and buffered (Adam7) draw paths.
// Returns 0 on success, -1 if `buf` is too short to contain that byte.
int png_peek_interlace(const uint8_t *buf, size_t len, uint8_t *out_interlace);

#endif // INKPLATE_PNG_DECODE_H
