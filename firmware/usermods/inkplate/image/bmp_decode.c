#include "bmp_decode.h"

#include <string.h>

#define BMP_HEADER_MIN_LEN 54
// BITMAPINFOHEADER (40), BITMAPV4HEADER (108), and BITMAPV5HEADER (124) all share the
// same first-40-bytes field layout (width/height/planes/bitcount/compression/sizeimage/
// ppm/clrused/clrimportant) -- the extra bytes in V4/V5 are RGBA masks (unused here, we
// resolve masks generically via BI_BITFIELDS or hardcoded 555 instead) and colorspace/
// ICC-profile fields we don't need. Anything else (OS/2 BITMAPCOREHEADER, WinCE variants,
// etc.) is out of scope.
#define BMP_CORE_HEADER_SIZE 40
#define BMP_COMPRESSION_RGB 0
#define BMP_COMPRESSION_BITFIELDS 3

static int is_supported_infoheader_size(uint32_t size)
{
    return size == 40 || size == 108 || size == 124;
}

static uint16_t read_le16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t read_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

// Position of the lowest set bit in `mask`, or 0 if `mask` is 0.
static uint8_t mask_shift(uint16_t mask)
{
    uint8_t shift = 0;
    while (mask && !(mask & 1)) {
        mask >>= 1;
        shift++;
    }
    return shift;
}

// Number of set bits in `mask`. Only meaningful for the contiguous-run masks
// bmp_parse_bitfields validates.
static uint8_t mask_bits(uint16_t mask)
{
    uint8_t bits = 0;
    while (mask) {
        bits += (uint8_t)(mask & 1);
        mask >>= 1;
    }
    return bits;
}

// True if `mask` is empty or not a single contiguous run of 1 bits.
static int mask_is_invalid(uint16_t mask)
{
    if (mask == 0) {
        return 1;
    }
    uint16_t shifted = (uint16_t)(mask >> mask_shift(mask));
    return (shifted & (uint16_t)(shifted + 1)) != 0; // shifted isn't all-ones
}

static void resolve_bitfield_channel(uint16_t mask, uint16_t *out_mask, uint8_t *out_shift,
                                     uint8_t *out_bits)
{
    *out_mask = mask;
    *out_shift = mask_shift(mask);
    *out_bits = mask_bits(mask);
}

int bmp_parse_header(const uint8_t *buf, size_t len, bmp_header_t *out)
{
    if (len < BMP_HEADER_MIN_LEN || buf[0] != 'B' || buf[1] != 'M') {
        return -1;
    }

    uint32_t info_header_size = read_le32(buf + 14);
    if (!is_supported_infoheader_size(info_header_size)) {
        return -1;
    }

    uint16_t bpp = read_le16(buf + 28);
    uint32_t compression = read_le32(buf + 30);

    if (bpp != 1 && bpp != 4 && bpp != 8 && bpp != 16 && bpp != 24) {
        return -1;
    }

    memset(out, 0, sizeof(*out));

    int32_t raw_width = (int32_t)read_le32(buf + 18);
    int32_t raw_height = (int32_t)read_le32(buf + 22);

    out->width = (uint32_t)(raw_width < 0 ? -raw_width : raw_width);
    out->height = (uint32_t)(raw_height < 0 ? -raw_height : raw_height);
    out->flip_y = raw_height > 0;
    out->data_offset = read_le32(buf + 10);
    out->bpp = bpp;

    if (bpp <= 8) {
        if (compression != BMP_COMPRESSION_RGB) {
            return -1; // RLE4/RLE8 out of scope
        }
        uint32_t bytes_per_row = (out->width * bpp + 7) / 8;
        out->row_size = (bytes_per_row + 3) & ~3u;

        uint32_t clr_used = read_le32(buf + 46);
        uint32_t max_entries = 1u << bpp;
        out->palette_count = (clr_used != 0 && clr_used <= max_entries) ? clr_used : max_entries;
        out->palette_offset = 14 + info_header_size;
    } else if (bpp == 16) {
        out->row_size = (out->width * 2 + 3) & ~3u;

        if (compression == BMP_COMPRESSION_RGB) {
            // Implicit 555: bits 14:10 = R, 9:5 = G, 4:0 = B, top bit unused.
            resolve_bitfield_channel(0x7C00, &out->r_mask, &out->r_shift, &out->r_bits);
            resolve_bitfield_channel(0x03E0, &out->g_mask, &out->g_shift, &out->g_bits);
            resolve_bitfield_channel(0x001F, &out->b_mask, &out->b_shift, &out->b_bits);
            out->bitfield_offset = 0; // already resolved, no further read needed
        } else if (compression == BMP_COMPRESSION_BITFIELDS) {
            // Masks sit at a fixed offset right after the 40-byte core header fields,
            // whether appended as a classic-header extension or baked into V4/V5's own
            // RedMask/GreenMask/BlueMask struct fields at that same relative position --
            // NOT after the full (possibly 108/124-byte) header.
            out->bitfield_offset = 14 + BMP_CORE_HEADER_SIZE;
        } else {
            return -1;
        }
    } else { // bpp == 24
        if (compression != BMP_COMPRESSION_RGB) {
            return -1;
        }
        out->row_size = (out->width * 3 + 3) & ~3u;
    }

    return 0;
}

int bmp_parse_palette(bmp_header_t *hdr, const uint8_t *buf, size_t len)
{
    if (hdr->bpp > 8) {
        return 0;
    }
    if (len < (size_t)hdr->palette_count * 4) {
        return -1;
    }

    memset(hdr->palette, 0, sizeof(hdr->palette));
    for (uint32_t i = 0; i < hdr->palette_count; i++) {
        const uint8_t *entry = buf + i * 4;
        hdr->palette[i][0] = entry[2]; // R
        hdr->palette[i][1] = entry[1]; // G
        hdr->palette[i][2] = entry[0]; // B
    }
    return 0;
}

int bmp_parse_bitfields(bmp_header_t *hdr, const uint8_t *buf, size_t len)
{
    if (len < 12) {
        return -1;
    }

    uint16_t r_mask = (uint16_t)read_le32(buf + 0);
    uint16_t g_mask = (uint16_t)read_le32(buf + 4);
    uint16_t b_mask = (uint16_t)read_le32(buf + 8);

    if (mask_is_invalid(r_mask) || mask_is_invalid(g_mask) || mask_is_invalid(b_mask)) {
        return -1;
    }

    resolve_bitfield_channel(r_mask, &hdr->r_mask, &hdr->r_shift, &hdr->r_bits);
    resolve_bitfield_channel(g_mask, &hdr->g_mask, &hdr->g_shift, &hdr->g_bits);
    resolve_bitfield_channel(b_mask, &hdr->b_mask, &hdr->b_shift, &hdr->b_bits);
    return 0;
}

// Scales a `bits`-wide channel value up to 8 bits, rounding to nearest.
static uint8_t scale_to_8(uint16_t value, uint8_t bits)
{
    if (bits == 0) {
        return 0;
    }
    uint32_t max_val = (1u << bits) - 1;
    return (uint8_t)((value * 255u + max_val / 2) / max_val);
}

static void decode_pixel_16(const bmp_header_t *hdr, const uint8_t *px, uint8_t *out)
{
    uint16_t raw = read_le16(px);
    uint16_t r = (uint16_t)((raw & hdr->r_mask) >> hdr->r_shift);
    uint16_t g = (uint16_t)((raw & hdr->g_mask) >> hdr->g_shift);
    uint16_t b = (uint16_t)((raw & hdr->b_mask) >> hdr->b_shift);
    out[0] = scale_to_8(r, hdr->r_bits);
    out[1] = scale_to_8(g, hdr->g_bits);
    out[2] = scale_to_8(b, hdr->b_bits);
}

void bmp_decode_row(const bmp_header_t *hdr, const uint8_t *raw_row, uint8_t *out_rgb)
{
    switch (hdr->bpp) {
        case 24:
            for (uint32_t col = 0; col < hdr->width; col++) {
                const uint8_t *px = raw_row + col * 3;
                uint8_t *out = out_rgb + col * 3;
                out[0] = px[2]; // R
                out[1] = px[1]; // G
                out[2] = px[0]; // B
            }
            break;
        case 16:
            for (uint32_t col = 0; col < hdr->width; col++) {
                decode_pixel_16(hdr, raw_row + col * 2, out_rgb + col * 3);
            }
            break;
        case 8:
            for (uint32_t col = 0; col < hdr->width; col++) {
                uint8_t index = raw_row[col];
                uint8_t *out = out_rgb + col * 3;
                out[0] = hdr->palette[index][0];
                out[1] = hdr->palette[index][1];
                out[2] = hdr->palette[index][2];
            }
            break;
        case 4:
            for (uint32_t col = 0; col < hdr->width; col++) {
                uint8_t byte = raw_row[col / 2];
                uint8_t index = (col % 2 == 0) ? (byte >> 4) : (byte & 0x0F);
                uint8_t *out = out_rgb + col * 3;
                out[0] = hdr->palette[index][0];
                out[1] = hdr->palette[index][1];
                out[2] = hdr->palette[index][2];
            }
            break;
        case 1:
            for (uint32_t col = 0; col < hdr->width; col++) {
                uint8_t byte = raw_row[col / 8];
                uint8_t index = (byte >> (7 - (col % 8))) & 0x01;
                uint8_t *out = out_rgb + col * 3;
                out[0] = hdr->palette[index][0];
                out[1] = hdr->palette[index][1];
                out[2] = hdr->palette[index][2];
            }
            break;
        default:
            break;
    }
}
