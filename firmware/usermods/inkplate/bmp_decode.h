// BMP decoder, pure logic (no I/O, no ESP-IDF/hardware headers) -- host-compiled unit test
// target, same tier as waveform.c/epd_partial_lut.c. Phase 7, docs/REFACTOR-PLAN.md step 19.
//
// Scope matches the existing Python draw_bmp_from_sd/_web (boards/inkplate10/inkplate10.py):
// 24-bit uncompressed (BI_RGB) BMP only, top-down or bottom-up. Decode is split from
// grayscale/dithering (that's step 20) -- this only turns file bytes into RGB888 rows.
#ifndef INKPLATE_BMP_DECODE_H
#define INKPLATE_BMP_DECODE_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t width;       // pixels per row
    uint32_t height;      // number of rows
    uint32_t data_offset; // byte offset from start of file to pixel data (bfOffBits)
    uint32_t row_size;    // bytes per row in the file, including 4-byte padding
    int flip_y;           // 1 if stored bottom-up (file row 0 is the image's LAST row),
                          // 0 if stored top-down. Caller maps decoded rows to destination
                          // y using this; bmp_decode_row itself does no reordering.
} bmp_header_t;

// Parses a BMP file/BITMAPINFOHEADER header from the first `len` bytes of `buf` (must
// include at least the 54-byte BITMAPFILEHEADER+BITMAPINFOHEADER). Returns 0 and fills
// `out` on success; returns -1 on error (bad signature, truncated header, unsupported
// bit depth, or compressed pixel data -- only 24-bit BI_RGB is supported).
int bmp_parse_header(const uint8_t *buf, size_t len, bmp_header_t *out);

// Decodes one raw file row (`raw_row`, exactly hdr->row_size bytes: BGR888 pixels plus
// trailing padding) into `out_rgb` (hdr->width * 3 bytes, RGB888, padding stripped).
// Rows are decoded in file order -- caller uses hdr->flip_y to pick the destination y.
void bmp_decode_row(const bmp_header_t *hdr, const uint8_t *raw_row, uint8_t *out_rgb);

#endif // INKPLATE_BMP_DECODE_H
