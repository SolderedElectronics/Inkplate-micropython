#include "bmp_decode.h"

#define BMP_HEADER_MIN_LEN 54
#define BMP_SUPPORTED_BPP 24
#define BMP_COMPRESSION_NONE 0 // BI_RGB

static uint16_t read_le16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t read_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

int bmp_parse_header(const uint8_t *buf, size_t len, bmp_header_t *out)
{
    if (len < BMP_HEADER_MIN_LEN || buf[0] != 'B' || buf[1] != 'M') {
        return -1;
    }

    if (read_le16(buf + 28) != BMP_SUPPORTED_BPP) {
        return -1;
    }

    if (read_le32(buf + 30) != BMP_COMPRESSION_NONE) {
        return -1;
    }

    int32_t raw_width = (int32_t)read_le32(buf + 18);
    int32_t raw_height = (int32_t)read_le32(buf + 22);

    out->width = (uint32_t)(raw_width < 0 ? -raw_width : raw_width);
    out->height = (uint32_t)(raw_height < 0 ? -raw_height : raw_height);
    out->flip_y = raw_height > 0;
    out->data_offset = read_le32(buf + 10);
    out->row_size = (out->width * 3 + 3) & ~3u;

    return 0;
}

void bmp_decode_row(const bmp_header_t *hdr, const uint8_t *raw_row, uint8_t *out_rgb)
{
    for (uint32_t col = 0; col < hdr->width; col++) {
        const uint8_t *px = raw_row + col * 3;
        uint8_t *out = out_rgb + col * 3;
        out[0] = px[2]; // R
        out[1] = px[1]; // G
        out[2] = px[0]; // B
    }
}
