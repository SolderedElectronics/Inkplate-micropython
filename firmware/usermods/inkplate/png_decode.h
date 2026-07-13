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

#endif // INKPLATE_PNG_DECODE_H
