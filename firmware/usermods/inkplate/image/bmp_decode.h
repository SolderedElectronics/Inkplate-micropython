/**
 * @file bmp_decode.h
 * @brief BMP decoder, pure logic (no I/O, no ESP-IDF/hardware headers).
 *
 * Supports uncompressed BMPs at 24-bit BGR888, 1/4/8-bit indexed (palette), and 16-bit
 * 555/565 (BI_RGB implies 555; BI_BITFIELDS masks are decoded generically, so any valid
 * 16-bit RGB bitfield layout works, not just exactly 565). Classic BITMAPINFOHEADER
 * (biSize == 40) and its BITMAPV4HEADER (108) / BITMAPV5HEADER (124) supersets are all
 * accepted -- their first 40 bytes share the same field layout, and real-world files
 * (e.g. Photoshop exports) commonly use V4/V5. RLE1/RLE4/RLE8, 32-bit, and OS/2
 * BITMAPCOREHEADER-family headers are out of scope. Decode is split from grayscale/
 * dithering -- this only turns file bytes into RGB888 rows.
 *
 * Streaming design, no whole-file buffering: caller reads the fixed-size header (54
 * bytes) first, calls bmp_parse_header, then -- for bpp <= 8 or 16-bit BI_BITFIELDS --
 * reads the small palette/bitmask section that follows and calls
 * bmp_parse_palette/bmp_parse_bitfields once, then streams pixel-data rows one at a
 * time through bmp_decode_row.
 */
#ifndef INKPLATE_BMP_DECODE_H
#define INKPLATE_BMP_DECODE_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t width;       // Pixels per row
    uint32_t height;      // Number of rows
    uint32_t data_offset; // Byte offset from start of file to pixel data (bfOffBits)
    uint32_t row_size;    // Bytes per row in the file, including 4-byte padding
    int flip_y;           // 1 if stored bottom-up (file row 0 is the image's LAST row),
                          // 0 if stored top-down. Caller maps decoded rows to destination
                          // y using this; bmp_decode_row itself does no reordering.
    uint16_t bpp;         // Bits per pixel: 1, 4, 8, 16, or 24

    // Indexed formats (bpp <= 8) only. palette_count is 0 for bpp > 8.
    uint32_t palette_offset; // Byte offset from start of file to the palette table
    uint32_t palette_count;  // Number of populated palette entries (<= 256)
    uint8_t palette[256][3]; // RGB888; entries >= palette_count are zeroed

    // 16-bit only. r_mask/g_mask/b_mask are 0 for other depths.
    uint16_t r_mask, g_mask, b_mask;   // Bit masks within the little-endian 16-bit pixel
    uint8_t r_shift, g_shift, b_shift; // Position of each channel's LSB within the mask
    uint8_t r_bits, g_bits, b_bits;    // Width in bits of each channel
    uint32_t bitfield_offset;          // Byte offset to the 3 packed DWORD masks (BI_BITFIELDS
                                       // only); 0 if the masks were already resolved by
                                       // bmp_parse_header (BI_RGB 16-bit, implicit 555) and no
                                       // further read/call is needed
} bmp_header_t;

/**
 * @brief Parses a BMP file/BITMAPINFOHEADER header, resolving row layout and (for 16-bit)
 * color masks.
 * @param buf Pointer to at least the 54-byte BITMAPFILEHEADER+BITMAPINFOHEADER.
 * @param len Number of bytes available at `buf`.
 * @param out Filled with the parsed header on success.
 * @return 0 on success; -1 on error (bad signature, truncated/non-BITMAPINFOHEADER header,
 * unsupported bit depth, or unsupported compression for the given bit depth). For 16-bit
 * BI_RGB, resolves the implicit 555 masks immediately (bitfield_offset == 0); for 16-bit
 * BI_BITFIELDS, sets bitfield_offset so the caller knows to read the mask section and call
 * bmp_parse_bitfields before decoding any rows.
 */
int bmp_parse_header(const uint8_t *buf, size_t len, bmp_header_t *out);

/**
 * @brief Reads the palette table (BGRA-quad entries, reserved byte ignored) starting at
 * hdr->palette_offset.
 * @param hdr Header from bmp_parse_header; palette is populated in place.
 * @param buf Pointer to at least hdr->palette_count * 4 bytes read from hdr->palette_offset.
 * @param len Number of bytes available at `buf`.
 * @return 0 on success, or as a no-op if hdr->bpp > 8; -1 if `len` is too short.
 */
int bmp_parse_palette(bmp_header_t *hdr, const uint8_t *buf, size_t len);

/**
 * @brief Reads the 3 packed little-endian DWORD R/G/B bit masks (BI_BITFIELDS section, 12
 * bytes) starting at hdr->bitfield_offset and resolves hdr->{r,g,b}_{mask,shift,bits}.
 * @param hdr Header from bmp_parse_header; only valid when hdr->bpp == 16 and
 * hdr->bitfield_offset != 0 (i.e. bmp_parse_header saw BI_BITFIELDS, not BI_RGB).
 * @param buf Pointer to at least 12 bytes read from hdr->bitfield_offset.
 * @param len Number of bytes available at `buf`.
 * @return 0 on success; -1 if `len` < 12 or if a mask is empty/non-contiguous.
 */
int bmp_parse_bitfields(bmp_header_t *hdr, const uint8_t *buf, size_t len);

/**
 * @brief Decodes one raw file row into RGB888, in file order (caller uses hdr->flip_y to
 * pick the destination y).
 * @param hdr Parsed header; for bpp <= 8, hdr->palette must already be populated (via
 * bmp_parse_palette); for 16-bit BI_BITFIELDS, hdr's mask fields must already be resolved
 * (via bmp_parse_bitfields).
 * @param raw_row Exactly hdr->row_size bytes.
 * @param out_rgb Output buffer, hdr->width * 3 bytes, RGB888, padding stripped.
 */
void bmp_decode_row(const bmp_header_t *hdr, const uint8_t *raw_row, uint8_t *out_rgb);

#endif // INKPLATE_BMP_DECODE_H
