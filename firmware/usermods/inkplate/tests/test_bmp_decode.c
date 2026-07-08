// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_bmp_decode.c ../bmp_decode.c -o test_bmp_decode \
//              && ./test_bmp_decode
#include <assert.h>
#include <string.h>

#include "../bmp_decode.h"

// Hand-built 2x2, 24-bit, bottom-up BMP (BITMAPFILEHEADER + BITMAPINFOHEADER, biHeight > 0
// means bottom-up storage). Image (top-down, as a human would view it):
//   top-left=red(255,0,0)   top-right=green(0,255,0)
//   bottom-left=blue(0,0,255) bottom-right=yellow(255,255,0)
// Bottom-up storage means file row 0 is the image's bottom row (blue, yellow), file row 1
// is the top row (red, green). Row size = (2*3+3)&~3 = 8 (6 pixel bytes + 2 padding).
// clang-format off
static const uint8_t sample_bmp[70] = {
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
// clang-format on

int main(void)
{
    bmp_header_t hdr;

    // Bad signature.
    uint8_t bad_sig[70];
    memcpy(bad_sig, sample_bmp, sizeof(sample_bmp));
    bad_sig[0] = 'X';
    assert(bmp_parse_header(bad_sig, sizeof(bad_sig), &hdr) == -1);

    // Truncated header.
    assert(bmp_parse_header(sample_bmp, 40, &hdr) == -1);

    // Unsupported bit depth.
    uint8_t bad_depth[70];
    memcpy(bad_depth, sample_bmp, sizeof(sample_bmp));
    bad_depth[28] = 8;
    assert(bmp_parse_header(bad_depth, sizeof(bad_depth), &hdr) == -1);

    // Unsupported compression.
    uint8_t bad_compression[70];
    memcpy(bad_compression, sample_bmp, sizeof(sample_bmp));
    bad_compression[30] = 1;
    assert(bmp_parse_header(bad_compression, sizeof(bad_compression), &hdr) == -1);

    // Valid bottom-up header.
    assert(bmp_parse_header(sample_bmp, sizeof(sample_bmp), &hdr) == 0);
    assert(hdr.width == 2);
    assert(hdr.height == 2);
    assert(hdr.data_offset == 54);
    assert(hdr.row_size == 8);
    assert(hdr.flip_y == 1);

    const uint8_t *pixel_data = sample_bmp + hdr.data_offset;
    uint8_t out_row[6];

    // File row 0 -> blue, yellow (as RGB888).
    bmp_decode_row(&hdr, pixel_data, out_row);
    uint8_t expected_row0[6] = {0, 0, 255, 255, 255, 0};
    assert(memcmp(out_row, expected_row0, sizeof(out_row)) == 0);

    // File row 1 -> red, green (as RGB888).
    bmp_decode_row(&hdr, pixel_data + hdr.row_size, out_row);
    uint8_t expected_row1[6] = {255, 0, 0, 0, 255, 0};
    assert(memcmp(out_row, expected_row1, sizeof(out_row)) == 0);

    // Top-down variant: same pixel layout, biHeight negative -> flip_y should clear.
    uint8_t top_down[70];
    memcpy(top_down, sample_bmp, sizeof(sample_bmp));
    top_down[22] = (uint8_t)(-2 & 0xFF);
    top_down[23] = 0xFF;
    top_down[24] = 0xFF;
    top_down[25] = 0xFF;
    assert(bmp_parse_header(top_down, sizeof(top_down), &hdr) == 0);
    assert(hdr.height == 2);
    assert(hdr.flip_y == 0);

    return 0;
}
