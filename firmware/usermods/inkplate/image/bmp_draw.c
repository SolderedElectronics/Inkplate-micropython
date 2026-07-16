#include "bmp_draw.h"

#include "bmp_decode.h"
#include "dither.h"
#include "../display/gfx.h"

// Static row-scratch buffer for bmp_decode_row's RGB888 output, sized with headroom
// over the widest board resolution in scope today (Inkplate5v2, 1280px). Static rather
// than a stack VLA/malloc so a draw call doesn't grow the caller's task stack or need
// an ESP-IDF heap allocator (bmp_decode.c itself stays pure logic, no allocation).
#define BMP_DRAW_MAX_WIDTH 1600
static uint8_t bmp_draw_row_rgb[BMP_DRAW_MAX_WIDTH * 3];

int bmp_draw_gs4(uint8_t *fb, int phys_w, int phys_h, int rotation, int display_mode, int x0,
                 int y0, const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                 uint32_t *out_width, uint32_t *out_height)
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

    dither_ctx_t dctx;
    if (dither && dither_ctx_init(&dctx, (int)hdr.width, kernel_type) != 0) {
        return -1;
    }
    int inv_mask = display_mode == 0 ? 1 : 7;

    for (uint32_t file_row = 0; file_row < hdr.height; file_row++) {
        const uint8_t *raw_row = buf + hdr.data_offset + (size_t)file_row * hdr.row_size;
        bmp_decode_row(&hdr, raw_row, bmp_draw_row_rgb);

        uint32_t y = hdr.flip_y ? (hdr.height - 1 - file_row) : file_row;
        for (uint32_t x = 0; x < hdr.width; x++) {
            const uint8_t *px = bmp_draw_row_rgb + x * 3;
            // ITU-R BT.601 luma, integer approximation.
            int gray = (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000;

            int level, recon;
            if (dither) {
                gray = dither_apply_error(&dctx, (int)x, gray);
                level = dither_quantize(gray, display_mode, &recon);
                dither_diffuse_error(&dctx, (int)x, (int)y, (int)hdr.width, (int)hdr.height,
                                     gray - recon);
            } else {
                level = dither_quantize(gray, display_mode, &recon);
            }
            if (invert) {
                level ^= inv_mask;
            }
            gfx_set_pixel(fb, phys_w, phys_h, rotation, display_mode, x0 + (int)x, y0 + (int)y,
                          level);
        }
        if (dither) {
            dither_row_advance(&dctx);
        }
    }
    if (dither) {
        dither_ctx_free(&dctx);
    }

    *out_width = hdr.width;
    *out_height = hdr.height;
    return 0;
}

int bmp_draw_palette(const uint8_t *buf, size_t len, int invert, int dither, int kernel_type,
                     const dither_palette_entry_t *palette, int palette_n,
                     bmp_draw_palette_cb write_pixel, void *cb_ctx, uint32_t *out_width,
                     uint32_t *out_height)
{
    bmp_header_t hdr;
    if (bmp_parse_header(buf, len, &hdr) != 0) {
        return -1;
    }
    if (hdr.width > BMP_DRAW_MAX_WIDTH) {
        // Distinct from a generic parse/decode failure -- see bmp_draw.h's comment
        // above (docs/REFACTOR-PLAN.md Phase 10 step 32's followup, same reasoning
        // as jpeg/png_draw_palette's identical -2): the caller can raise a clear
        // "image too wide" error instead of an indistinguishable "BMP decode
        // failed".
        return -2;
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

    dither_rgb_ctx_t dctx;
    if (dither && dither_rgb_ctx_init(&dctx, (int)hdr.width, kernel_type) != 0) {
        return -1;
    }

    for (uint32_t file_row = 0; file_row < hdr.height; file_row++) {
        const uint8_t *raw_row = buf + hdr.data_offset + (size_t)file_row * hdr.row_size;
        bmp_decode_row(&hdr, raw_row, bmp_draw_row_rgb);

        uint32_t y = hdr.flip_y ? (hdr.height - 1 - file_row) : file_row;
        for (uint32_t x = 0; x < hdr.width; x++) {
            const uint8_t *px = bmp_draw_row_rgb + x * 3;
            int r = px[0], g = px[1], b = px[2];

            int value, recon_r, recon_g, recon_b;
            if (dither) {
                dither_apply_error_rgb(&dctx, (int)x, &r, &g, &b);
                value = dither_quantize_palette(r, g, b, palette, palette_n, &recon_r, &recon_g,
                                                &recon_b);
                dither_diffuse_error_rgb(&dctx, (int)x, (int)y, (int)hdr.width, (int)hdr.height,
                                         r - recon_r, g - recon_g, b - recon_b);
            } else {
                value = dither_quantize_palette(r, g, b, palette, palette_n, &recon_r, &recon_g,
                                                &recon_b);
            }
            if (invert) {
                value = dither_invert_palette_bw(value, palette, palette_n);
            }
            write_pixel(cb_ctx, (int)x, (int)y, value);
        }
        if (dither) {
            dither_row_advance_rgb(&dctx);
        }
    }
    if (dither) {
        dither_rgb_ctx_free(&dctx);
    }

    *out_width = hdr.width;
    *out_height = hdr.height;
    return 0;
}
