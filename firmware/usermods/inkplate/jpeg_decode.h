// JPEG decoder, thin wrapper over ESP32 ROM's bundled TJpgDec (rom/tjpgd.h) -- no
// external component, no porting: decode logic lives in mask ROM already. Phase 7,
// docs/REFACTOR-PLAN.md step 18. ESP-IDF-only (links against ROM symbols) -- unlike
// bmp_decode.c/gfx.c, this cannot be host-gcc-compiled/tested; verify is HIL-only.
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

// Decodes `len` bytes of JPEG data at `buf`, streaming one tile at a time through `cb`
// (no full-image buffer is allocated). `out_width`/`out_height` receive the image
// dimensions on success. Returns 0 on success, -1 on error (malformed/unsupported
// JPEG, ROM decode failure, or `cb` returning 0).
int jpeg_decode(const uint8_t *buf, size_t len, jpeg_tile_cb_t cb, void *ctx, uint32_t *out_width,
                uint32_t *out_height);

#endif // INKPLATE_JPEG_DECODE_H
