#include "bmp_draw.h"

#include "bmp_decode.h"
#include "gfx.h"

// Static row-scratch buffer for bmp_decode_row's RGB888 output, sized with headroom
// over the widest board resolution in scope today (Inkplate5v2, 1280px). Static rather
// than a stack VLA/malloc so a draw call doesn't grow the caller's task stack or need
// an ESP-IDF heap allocator (bmp_decode.c itself stays pure logic, no allocation).
#define BMP_DRAW_MAX_WIDTH 1600
static uint8_t bmp_draw_row_rgb[BMP_DRAW_MAX_WIDTH * 3];

int bmp_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int x0, int y0,
                 const uint8_t *buf, size_t len, uint32_t *out_width, uint32_t *out_height)
{
    bmp_header_t hdr;
    if (bmp_parse_header(buf, len, &hdr) != 0) {
        return -1;
    }
    if (hdr.width > BMP_DRAW_MAX_WIDTH) {
        return -1;
    }

    if (hdr.bpp <= 8) {
        size_t palette_bytes = (size_t)hdr.palette_count * 4;
        if ((size_t)hdr.palette_offset + palette_bytes > len ||
            bmp_parse_palette(&hdr, buf + hdr.palette_offset, palette_bytes) != 0) {
            return -1;
        }
    } else if (hdr.bpp == 16 && hdr.bitfield_offset != 0) {
        if ((size_t)hdr.bitfield_offset + 12 > len ||
            bmp_parse_bitfields(&hdr, buf + hdr.bitfield_offset, 12) != 0) {
            return -1;
        }
    }

    if ((size_t)hdr.data_offset + (size_t)hdr.row_size * hdr.height > len) {
        return -1;
    }

    for (uint32_t file_row = 0; file_row < hdr.height; file_row++) {
        const uint8_t *raw_row = buf + hdr.data_offset + (size_t)file_row * hdr.row_size;
        bmp_decode_row(&hdr, raw_row, bmp_draw_row_rgb);

        uint32_t y = hdr.flip_y ? (hdr.height - 1 - file_row) : file_row;
        for (uint32_t x = 0; x < hdr.width; x++) {
            const uint8_t *px = bmp_draw_row_rgb + x * 3;
            // ITU-R BT.601 luma, integer approximation.
            uint32_t luma = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;
            // Nearest of 8 levels (0-7) -- no error diffusion, that's step 21's job.
            int level = (int)((luma * 7 + 127) / 255);
            gfx_set_pixel(fb, phys_w, phys_h, rotation, 1, x0 + (int)x, y0 + (int)y, level);
        }
    }

    *out_width = hdr.width;
    *out_height = hdr.height;
    return 0;
}
