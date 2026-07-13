// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_bmp_decode.c ../bmp_decode.c -o test_bmp_decode \
//              && ./test_bmp_decode
#include <assert.h>
#include <string.h>

#include "../bmp_decode.h"

// All sample images below share the same 2x2 layout (top-down, as a human would view it):
//   top-left=red(255,0,0)     top-right=green(0,255,0)
//   bottom-left=blue(0,0,255) bottom-right=yellow(255,255,0)
// and are stored bottom-up (biHeight > 0), so file row 0 is the bottom image row
// (blue, yellow) and file row 1 is the top image row (red, green).

// clang-format off
static const uint8_t sample_bmp_24[70] = {
    // BITMAPFILEHEADER (14 bytes)
    'B', 'M',       // bfType
    70, 0, 0, 0,    // bfSize (little-endian u32)
    0, 0, 0, 0,     // bfReserved1/2
    54, 0, 0, 0,    // bfOffBits
    // BITMAPINFOHEADER (40 bytes)
    40, 0, 0, 0,    // biSize
    2, 0, 0, 0,     // biWidth = 2
    2, 0, 0, 0,     // biHeight = 2 (positive -> bottom-up)
    1, 0,           // biPlanes
    24, 0,          // biBitCount = 24
    0, 0, 0, 0,     // biCompression = BI_RGB
    16, 0, 0, 0,    // biSizeImage = row_size(8) * height(2)
    0, 0, 0, 0,     // biXPelsPerMeter
    0, 0, 0, 0,     // biYPelsPerMeter
    0, 0, 0, 0,     // biClrUsed
    0, 0, 0, 0,     // biClrImportant
    // Pixel data, file row 0 (bottom image row: blue, yellow), BGR + 2 bytes padding
    255, 0, 0, 0, 255, 255, 0, 0,
    // Pixel data, file row 1 (top image row: red, green), BGR + 2 bytes padding
    0, 0, 255, 0, 255, 0, 0, 0,
};

// Same image as sample_bmp_24, but wrapped in a 124-byte BITMAPV5HEADER (as produced by
// e.g. Photoshop) instead of the classic 40-byte BITMAPINFOHEADER -- the extra 84 bytes
// (RGBA masks + colorspace/ICC fields) are zeroed since they're unused for BI_RGB 24-bit.
// bfOffBits = 14 + 124 = 138.
static const uint8_t sample_bmp_24_v5[154] = {
    'B', 'M',
    154, 0, 0, 0,
    0, 0, 0, 0,
    138, 0, 0, 0,   // bfOffBits
    124, 0, 0, 0,   // biSize = 124 (BITMAPV5HEADER)
    2, 0, 0, 0,
    2, 0, 0, 0,
    1, 0,
    24, 0,
    0, 0, 0, 0,
    16, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    // 84 bytes of V5-only fields (masks/CSType/endpoints/gamma/profile), unused here.
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0,
    // Pixel data, file row 0 (bottom: blue, yellow) + 2 padding
    255, 0, 0, 0, 255, 255, 0, 0,
    // Pixel data, file row 1 (top: red, green) + 2 padding
    0, 0, 255, 0, 255, 0, 0, 0,
};

// 8-bit indexed. Palette (BGRA quads): 0=red, 1=green, 2=blue, 3=yellow.
// row_size = ((2*8+7)/8 + 3) & ~3 = 4 (2 index bytes + 2 padding).
static const uint8_t sample_bmp_8[78] = {
    'B', 'M',
    78, 0, 0, 0,
    0, 0, 0, 0,
    70, 0, 0, 0,    // bfOffBits = 54 (headers) + 16 (4-entry palette)
    40, 0, 0, 0,    // biSize
    2, 0, 0, 0,     // biWidth = 2
    2, 0, 0, 0,     // biHeight = 2 (bottom-up)
    1, 0,           // biPlanes
    8, 0,           // biBitCount = 8
    0, 0, 0, 0,     // biCompression = BI_RGB
    8, 0, 0, 0,     // biSizeImage = row_size(4) * height(2)
    0, 0, 0, 0,
    0, 0, 0, 0,
    4, 0, 0, 0,     // biClrUsed = 4
    0, 0, 0, 0,
    // Palette: BGRA
    0, 0, 255, 0,   // 0 = red
    0, 255, 0, 0,   // 1 = green
    255, 0, 0, 0,   // 2 = blue
    0, 255, 255, 0, // 3 = yellow
    // Pixel data, file row 0 (bottom: blue=idx2, yellow=idx3) + 2 padding
    2, 3, 0, 0,
    // Pixel data, file row 1 (top: red=idx0, green=idx1) + 2 padding
    0, 1, 0, 0,
};

// 4-bit indexed. Same palette as the 8-bit sample, packed 2px/byte (high nibble first).
// row_size = ((2*4+7)/8 + 3) & ~3 = 4 (1 data byte + 3 padding).
static const uint8_t sample_bmp_4[78] = {
    'B', 'M',
    78, 0, 0, 0,
    0, 0, 0, 0,
    70, 0, 0, 0,    // bfOffBits = 54 + 16
    40, 0, 0, 0,
    2, 0, 0, 0,
    2, 0, 0, 0,
    1, 0,
    4, 0,           // biBitCount = 4
    0, 0, 0, 0,
    8, 0, 0, 0,     // biSizeImage = row_size(4) * height(2)
    0, 0, 0, 0,
    0, 0, 0, 0,
    4, 0, 0, 0,     // biClrUsed = 4
    0, 0, 0, 0,
    0, 0, 255, 0,
    0, 255, 0, 0,
    255, 0, 0, 0,
    0, 255, 255, 0,
    // file row 0 (bottom: blue=idx2 high nibble, yellow=idx3 low nibble) + 3 padding
    0x23, 0, 0, 0,
    // file row 1 (top: red=idx0 high nibble, green=idx1 low nibble) + 3 padding
    0x01, 0, 0, 0,
};

// 1-bit indexed, checkerboard (only 2 colors fit). Palette: 0=black, 1=white.
// top row = white,black ; bottom row = black,white.
// row_size = ((2*1+7)/8 + 3) & ~3 = 4 (1 data byte + 3 padding).
static const uint8_t sample_bmp_1[70] = {
    'B', 'M',
    70, 0, 0, 0,
    0, 0, 0, 0,
    62, 0, 0, 0,    // bfOffBits = 54 + 8 (2-entry palette)
    40, 0, 0, 0,
    2, 0, 0, 0,
    2, 0, 0, 0,
    1, 0,
    1, 0,           // biBitCount = 1
    0, 0, 0, 0,
    8, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    2, 0, 0, 0,     // biClrUsed = 2
    0, 0, 0, 0,
    0, 0, 0, 0,     // 0 = black
    255, 255, 255, 0, // 1 = white
    // file row 0 (bottom: black=idx0, white=idx1 -> bits 0,1,...) + 3 padding
    0x40, 0, 0, 0,
    // file row 1 (top: white=idx1, black=idx0 -> bits 1,0,...) + 3 padding
    0x80, 0, 0, 0,
};

// 16-bit, BI_RGB (implicit 555). row_size = (2*2+3) & ~3 = 4, no padding.
// R=(255,0,0)->0x7C00, G=(0,255,0)->0x03E0, B=(0,0,255)->0x001F, Y=(255,255,0)->0x7FE0.
static const uint8_t sample_bmp_16_555[62] = {
    'B', 'M',
    62, 0, 0, 0,
    0, 0, 0, 0,
    54, 0, 0, 0,    // bfOffBits = 54, no palette/bitfields section for BI_RGB
    40, 0, 0, 0,
    2, 0, 0, 0,
    2, 0, 0, 0,
    1, 0,
    16, 0,          // biBitCount = 16
    0, 0, 0, 0,     // biCompression = BI_RGB
    8, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    // file row 0 (bottom: blue=0x001F, yellow=0x7FE0)
    0x1F, 0x00, 0xE0, 0x7F,
    // file row 1 (top: red=0x7C00, green=0x03E0)
    0x00, 0x7C, 0xE0, 0x03,
};

// 16-bit, BI_BITFIELDS (explicit 565). Masks (R=0xF800, G=0x07E0, B=0x001F) sit as 3
// packed LE DWORDs right after the header, before pixel data.
// R=(255,0,0)->0xF800, G=(0,255,0)->0x07E0, B=(0,0,255)->0x001F, Y=(255,255,0)->0xFFE0.
static const uint8_t sample_bmp_16_565[74] = {
    'B', 'M',
    74, 0, 0, 0,
    0, 0, 0, 0,
    66, 0, 0, 0,    // bfOffBits = 54 + 12 (bitfield masks)
    40, 0, 0, 0,
    2, 0, 0, 0,
    2, 0, 0, 0,
    1, 0,
    16, 0,
    3, 0, 0, 0,     // biCompression = BI_BITFIELDS
    8, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0, 0,
    // R/G/B masks, LE u32 each
    0x00, 0xF8, 0x00, 0x00,
    0xE0, 0x07, 0x00, 0x00,
    0x1F, 0x00, 0x00, 0x00,
    // file row 0 (bottom: blue=0x001F, yellow=0xFFE0)
    0x1F, 0x00, 0xE0, 0xFF,
    // file row 1 (top: red=0xF800, green=0x07E0)
    0x00, 0xF8, 0xE0, 0x07,
};
// clang-format on

static void expect_2x2_rows(const bmp_header_t *hdr, const uint8_t *pixel_data)
{
    uint8_t out_row[6];

    // File row 0 -> blue, yellow (as RGB888).
    bmp_decode_row(hdr, pixel_data, out_row);
    uint8_t expected_row0[6] = {0, 0, 255, 255, 255, 0};
    assert(memcmp(out_row, expected_row0, sizeof(out_row)) == 0);

    // File row 1 -> red, green (as RGB888).
    bmp_decode_row(hdr, pixel_data + hdr->row_size, out_row);
    uint8_t expected_row1[6] = {255, 0, 0, 0, 255, 0};
    assert(memcmp(out_row, expected_row1, sizeof(out_row)) == 0);
}

int main(void)
{
    bmp_header_t hdr;

    // Bad signature.
    uint8_t bad_sig[70];
    memcpy(bad_sig, sample_bmp_24, sizeof(sample_bmp_24));
    bad_sig[0] = 'X';
    assert(bmp_parse_header(bad_sig, sizeof(bad_sig), &hdr) == -1);

    // Truncated header.
    assert(bmp_parse_header(sample_bmp_24, 40, &hdr) == -1);

    // Unsupported bit depth (not one of 1/4/8/16/24).
    uint8_t bad_depth[70];
    memcpy(bad_depth, sample_bmp_24, sizeof(sample_bmp_24));
    bad_depth[28] = 2;
    assert(bmp_parse_header(bad_depth, sizeof(bad_depth), &hdr) == -1);

    // Unsupported compression (RLE, on a 24-bit header where only BI_RGB is valid).
    uint8_t bad_compression[70];
    memcpy(bad_compression, sample_bmp_24, sizeof(sample_bmp_24));
    bad_compression[30] = 1;
    assert(bmp_parse_header(bad_compression, sizeof(bad_compression), &hdr) == -1);

    // Unsupported header size (not one of the classic/V4/V5 sizes {40,108,124},
    // e.g. OS/2 BITMAPCOREHEADER-family) rejected.
    uint8_t bad_infoheader[70];
    memcpy(bad_infoheader, sample_bmp_24, sizeof(sample_bmp_24));
    bad_infoheader[14] = 52;
    assert(bmp_parse_header(bad_infoheader, sizeof(bad_infoheader), &hdr) == -1);

    // ---- 24-bit ----
    assert(bmp_parse_header(sample_bmp_24, sizeof(sample_bmp_24), &hdr) == 0);
    assert(hdr.width == 2);
    assert(hdr.height == 2);
    assert(hdr.bpp == 24);
    assert(hdr.data_offset == 54);
    assert(hdr.row_size == 8);
    assert(hdr.flip_y == 1);
    expect_2x2_rows(&hdr, sample_bmp_24 + hdr.data_offset);

    // Top-down variant: same pixel layout, biHeight negative -> flip_y should clear.
    uint8_t top_down[70];
    memcpy(top_down, sample_bmp_24, sizeof(sample_bmp_24));
    top_down[22] = (uint8_t)(-2 & 0xFF);
    top_down[23] = 0xFF;
    top_down[24] = 0xFF;
    top_down[25] = 0xFF;
    assert(bmp_parse_header(top_down, sizeof(top_down), &hdr) == 0);
    assert(hdr.height == 2);
    assert(hdr.flip_y == 0);

    // ---- 24-bit, BITMAPV5HEADER (real-world files, e.g. Photoshop exports, use this) ----
    assert(bmp_parse_header(sample_bmp_24_v5, sizeof(sample_bmp_24_v5), &hdr) == 0);
    assert(hdr.bpp == 24);
    assert(hdr.data_offset == 138);
    assert(hdr.row_size == 8);
    expect_2x2_rows(&hdr, sample_bmp_24_v5 + hdr.data_offset);

    // ---- 8-bit indexed ----
    assert(bmp_parse_header(sample_bmp_8, sizeof(sample_bmp_8), &hdr) == 0);
    assert(hdr.bpp == 8);
    assert(hdr.row_size == 4);
    assert(hdr.palette_offset == 54);
    assert(hdr.palette_count == 4);
    // Too-short palette buffer rejected.
    assert(bmp_parse_palette(&hdr, sample_bmp_8 + hdr.palette_offset, 4) == -1);
    assert(bmp_parse_palette(&hdr, sample_bmp_8 + hdr.palette_offset, 16) == 0);
    assert(hdr.palette[2][0] == 0 && hdr.palette[2][1] == 0 && hdr.palette[2][2] == 255);
    expect_2x2_rows(&hdr, sample_bmp_8 + hdr.data_offset);

    // ---- 4-bit indexed ----
    assert(bmp_parse_header(sample_bmp_4, sizeof(sample_bmp_4), &hdr) == 0);
    assert(hdr.bpp == 4);
    assert(hdr.row_size == 4);
    assert(hdr.palette_count == 4);
    assert(bmp_parse_palette(&hdr, sample_bmp_4 + hdr.palette_offset, 16) == 0);
    expect_2x2_rows(&hdr, sample_bmp_4 + hdr.data_offset);

    // ---- 1-bit indexed ----
    assert(bmp_parse_header(sample_bmp_1, sizeof(sample_bmp_1), &hdr) == 0);
    assert(hdr.bpp == 1);
    assert(hdr.row_size == 4);
    assert(hdr.palette_count == 2);
    assert(bmp_parse_palette(&hdr, sample_bmp_1 + hdr.palette_offset, 8) == 0);
    {
        uint8_t out_row[6];
        const uint8_t *pixel_data = sample_bmp_1 + hdr.data_offset;
        bmp_decode_row(&hdr, pixel_data, out_row); // bottom: black, white
        uint8_t expected_row0[6] = {0, 0, 0, 255, 255, 255};
        assert(memcmp(out_row, expected_row0, sizeof(out_row)) == 0);
        bmp_decode_row(&hdr, pixel_data + hdr.row_size, out_row); // top: white, black
        uint8_t expected_row1[6] = {255, 255, 255, 0, 0, 0};
        assert(memcmp(out_row, expected_row1, sizeof(out_row)) == 0);
    }

    // ---- 16-bit, implicit 555 ----
    assert(bmp_parse_header(sample_bmp_16_555, sizeof(sample_bmp_16_555), &hdr) == 0);
    assert(hdr.bpp == 16);
    assert(hdr.row_size == 4);
    assert(hdr.bitfield_offset == 0); // already resolved
    assert(hdr.r_bits == 5 && hdr.g_bits == 5 && hdr.b_bits == 5);
    expect_2x2_rows(&hdr, sample_bmp_16_555 + hdr.data_offset);

    // ---- 16-bit, explicit 565 (BI_BITFIELDS) ----
    assert(bmp_parse_header(sample_bmp_16_565, sizeof(sample_bmp_16_565), &hdr) == 0);
    assert(hdr.bpp == 16);
    assert(hdr.row_size == 4);
    assert(hdr.bitfield_offset == 54);
    // Not yet resolved -- decoding now would use garbage masks.
    assert(bmp_parse_bitfields(&hdr, sample_bmp_16_565 + hdr.bitfield_offset, 4) == -1);
    assert(bmp_parse_bitfields(&hdr, sample_bmp_16_565 + hdr.bitfield_offset, 12) == 0);
    assert(hdr.r_bits == 5 && hdr.g_bits == 6 && hdr.b_bits == 5);
    expect_2x2_rows(&hdr, sample_bmp_16_565 + hdr.data_offset);

    // Non-contiguous mask rejected.
    uint8_t bad_mask[12] = {0x55, 0x55, 0, 0, 0xE0, 0x07, 0, 0, 0x1F, 0, 0, 0};
    assert(bmp_parse_bitfields(&hdr, bad_mask, sizeof(bad_mask)) == -1);

    return 0;
}
