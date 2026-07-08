#include "gs_pack.h"

void inkplate_gs4_row_to_gs2(const uint8_t *gs4_row, uint16_t gs2_row_bytes, uint8_t *gs2_row)
{
    for (uint16_t i = 0; i < gs2_row_bytes; i++) {
        uint8_t a = gs4_row[i * 2];
        uint8_t b = gs4_row[i * 2 + 1];
        uint8_t p0 = (uint8_t)((a & 0x0F) >> 1);
        uint8_t p1 = (uint8_t)((a >> 4) >> 1);
        uint8_t p2 = (uint8_t)((b & 0x0F) >> 1);
        uint8_t p3 = (uint8_t)((b >> 4) >> 1);
        gs2_row[i] = (uint8_t)(p0 | (p1 << 2) | (p2 << 4) | (p3 << 6));
    }
}
