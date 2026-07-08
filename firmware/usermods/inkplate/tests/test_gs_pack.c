// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_gs_pack.c ../gs_pack.c -o test_gs_pack && ./test_gs_pack
#include <assert.h>
#include <stdio.h>

#include "../gs_pack.h"

// Round-trips all 8 raw pixel levels (0-7) through the GS4->GS2 fold and checks both the
// raw>>1 level reduction and the nibble/byte packing position match build_gs_row's
// expected GS2_HMSB shape (p0 in bits1:0, p1 in bits3:2, p2 in bits5:4, p3 in bits7:6).
static void test_all_levels_fold_and_pack(void)
{
    for (int raw0 = 0; raw0 < 8; raw0++) {
        for (int raw1 = 0; raw1 < 8; raw1++) {
            for (int raw2 = 0; raw2 < 8; raw2++) {
                for (int raw3 = 0; raw3 < 8; raw3++) {
                    uint8_t gs4_row[2] = {
                        (uint8_t)(raw0 | (raw1 << 4)),
                        (uint8_t)(raw2 | (raw3 << 4)),
                    };
                    uint8_t gs2_row[1];
                    inkplate_gs4_row_to_gs2(gs4_row, 1, gs2_row);

                    uint8_t expected = (uint8_t)((raw0 >> 1) | ((raw1 >> 1) << 2) |
                                                 ((raw2 >> 1) << 4) | ((raw3 >> 1) << 6));
                    assert(gs2_row[0] == expected);
                }
            }
        }
    }
    printf("test_all_levels_fold_and_pack: passed\n");
}

// Multi-byte row: two GS2-style output bytes from four GS4 input bytes.
static void test_multi_byte_row(void)
{
    uint8_t gs4_row[4] = {
        (uint8_t)(0 | (7 << 4)), // pixels 0,1 -> raw 0,7
        (uint8_t)(3 | (4 << 4)), // pixels 2,3 -> raw 3,4
        (uint8_t)(1 | (6 << 4)), // pixels 4,5 -> raw 1,6
        (uint8_t)(2 | (5 << 4)), // pixels 6,7 -> raw 2,5
    };
    uint8_t gs2_row[2];
    inkplate_gs4_row_to_gs2(gs4_row, 2, gs2_row);

    uint8_t expected0 = (uint8_t)((0 >> 1) | ((7 >> 1) << 2) | ((3 >> 1) << 4) | ((4 >> 1) << 6));
    uint8_t expected1 = (uint8_t)((1 >> 1) | ((6 >> 1) << 2) | ((2 >> 1) << 4) | ((5 >> 1) << 6));
    assert(gs2_row[0] == expected0);
    assert(gs2_row[1] == expected1);

    printf("test_multi_byte_row: passed\n");
}

int main(void)
{
    test_all_levels_fold_and_pack();
    test_multi_byte_row();
    printf("test_gs_pack: all assertions passed\n");
    return 0;
}
