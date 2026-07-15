// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_board_config.c ../board_config.c -o test_board_config && ./test_board_config
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../board_config.h"

int main(void)
{
    const board_config_t *cfg = &board_config_inkplate10;

    assert(strcmp(cfg->name, "inkplate10") == 0);

    assert(cfg->width == 1200);
    assert(cfg->height == 825);

    const uint8_t expected_data_pins[8] = {4, 5, 18, 19, 23, 25, 26, 27};
    assert(memcmp(cfg->data_pins, expected_data_pins, sizeof(expected_data_pins)) == 0);
    assert(cfg->data_mask == 0x0E8C0030);

    assert(cfg->pin_cl == 0);
    assert(cfg->pin_le == 2);
    assert(cfg->pin_ckv == 32);
    assert(cfg->pin_sph == 33);

    assert(cfg->pin_oe.expander_addr == 0x20 && cfg->pin_oe.pin == 0);
    assert(cfg->pin_gmode.expander_addr == 0x20 && cfg->pin_gmode.pin == 1);
    assert(cfg->pin_spv.expander_addr == 0x20 && cfg->pin_spv.pin == 2);

    assert(cfg->pmic_i2c_addr == 0x48);

    assert(cfg->waveform != NULL);
    assert(cfg->waveform->levels == 8);
    assert(cfg->waveform->phases == 9);
    // Phase 1 row, cross-checked against the real Arduino waveform1[color][phase=1] column
    // (Inkplate10Driver.cpp): color0=0, color1=0, color2=0, color3=1, color4=0, color5=2,
    // color6=0, color7=0.
    const uint8_t expected_wave_row1[MAX_WAVE_LEVELS] = {0, 0, 0, 1, 0, 2, 0, 0};
    assert(memcmp(cfg->waveform->table[1], expected_wave_row1, MAX_WAVE_LEVELS) == 0);
    // Final phase (8) is the all-discharge/park row, same as phase 0.
    const uint8_t expected_wave_row8[MAX_WAVE_LEVELS] = {0, 0, 0, 0, 0, 0, 0, 0};
    assert(memcmp(cfg->waveform->table[8], expected_wave_row8, MAX_WAVE_LEVELS) == 0);

    assert(cfg->partial_reps == 5);

    assert(cfg->has_touch == 0);
    assert(cfg->has_frontlight == 0);

    // INKPLATE6 and INKPLATE6V2 share pins/waveform with each other and with Inkplate10
    // (same reference schematic) -- only name and partial_reps differ between the two.
    const board_config_t *variants[2] = {&board_config_inkplate6, &board_config_inkplate6v2};
    const char *expected_names[2] = {"inkplate6", "inkplate6v2"};
    const uint8_t expected_partial_reps[2] = {5, 6};
    // INKPLATE6 (classic) has onboard touchpads (MCP23017-driven, no C-side hook);
    // INKPLATE6V2 doesn't (same expander pins repurposed for SD_ENABLE instead).
    const uint8_t expected_has_touch[2] = {1, 0};

    for (int i = 0; i < 2; ++i) {
        const board_config_t *v = variants[i];

        assert(strcmp(v->name, expected_names[i]) == 0);

        assert(v->width == 800);
        assert(v->height == 600);

        assert(memcmp(v->data_pins, expected_data_pins, sizeof(expected_data_pins)) == 0);
        assert(v->data_mask == 0x0E8C0030);

        assert(v->pin_cl == 0);
        assert(v->pin_le == 2);
        assert(v->pin_ckv == 32);
        assert(v->pin_sph == 33);

        assert(v->pin_oe.expander_addr == 0x20 && v->pin_oe.pin == 0);
        assert(v->pin_gmode.expander_addr == 0x20 && v->pin_gmode.pin == 1);
        assert(v->pin_spv.expander_addr == 0x20 && v->pin_spv.pin == 2);

        assert(v->pmic_i2c_addr == 0x48);

        assert(v->waveform != NULL);
        assert(v->waveform->levels == 8);
        assert(v->waveform->phases == 9);
        // Phase 3 row, cross-checked against the real Arduino waveform3Bit[color][phase=3]
        // column (waveforms.h, both INKPLATE6 and INKPLATE6V2): color0=0, color1=1,
        // color2=1, color3=2, color4=1, color5=1, color6=0, color7=0.
        const uint8_t expected_wave_row3[MAX_WAVE_LEVELS] = {0, 1, 1, 2, 1, 1, 0, 0};
        assert(memcmp(v->waveform->table[3], expected_wave_row3, MAX_WAVE_LEVELS) == 0);
        // Final phase (8) is the all-discharge/park row.
        assert(memcmp(v->waveform->table[8], expected_wave_row8, MAX_WAVE_LEVELS) == 0);

        assert(v->partial_reps == expected_partial_reps[i]);

        assert(v->has_touch == expected_has_touch[i]);
        assert(v->has_frontlight == 0);
    }

    // INKPLATE5V2: same pin/data-bus layout, own resolution/waveform/partial_reps.
    const board_config_t *cfg5v2 = &board_config_inkplate5v2;

    assert(strcmp(cfg5v2->name, "inkplate5v2") == 0);

    assert(cfg5v2->width == 1280);
    assert(cfg5v2->height == 720);

    assert(memcmp(cfg5v2->data_pins, expected_data_pins, sizeof(expected_data_pins)) == 0);
    assert(cfg5v2->data_mask == 0x0E8C0030);

    assert(cfg5v2->pin_cl == 0);
    assert(cfg5v2->pin_le == 2);
    assert(cfg5v2->pin_ckv == 32);
    assert(cfg5v2->pin_sph == 33);

    assert(cfg5v2->pin_oe.expander_addr == 0x20 && cfg5v2->pin_oe.pin == 0);
    assert(cfg5v2->pin_gmode.expander_addr == 0x20 && cfg5v2->pin_gmode.pin == 1);
    assert(cfg5v2->pin_spv.expander_addr == 0x20 && cfg5v2->pin_spv.pin == 2);

    assert(cfg5v2->pmic_i2c_addr == 0x48);

    assert(cfg5v2->waveform != NULL);
    assert(cfg5v2->waveform->levels == 8);
    assert(cfg5v2->waveform->phases == 9);
    // Phase 4 row, cross-checked against the real Arduino waveform3Bit[color][phase=4]
    // column (Inkplate5V2's waveforms.h): color0=2, color1=1, color2=1, color3=1,
    // color4=1, color5=2, color6=2, color7=0.
    const uint8_t expected_wave5v2_row4[MAX_WAVE_LEVELS] = {2, 1, 1, 1, 1, 2, 2, 0};
    assert(memcmp(cfg5v2->waveform->table[4], expected_wave5v2_row4, MAX_WAVE_LEVELS) == 0);
    // Final phase (8) is the all-discharge/park row.
    assert(memcmp(cfg5v2->waveform->table[8], expected_wave_row8, MAX_WAVE_LEVELS) == 0);

    assert(cfg5v2->partial_reps == 4);

    assert(cfg5v2->has_touch == 0);
    assert(cfg5v2->has_frontlight == 0);

    // INKPLATE6FLICK: same pin/data-bus layout, own resolution/waveform/partial_reps.
    const board_config_t *cflick = &board_config_inkplate6flick;

    assert(strcmp(cflick->name, "inkplate6flick") == 0);

    assert(cflick->width == 1024);
    assert(cflick->height == 758);

    assert(memcmp(cflick->data_pins, expected_data_pins, sizeof(expected_data_pins)) == 0);
    assert(cflick->data_mask == 0x0E8C0030);

    assert(cflick->pin_cl == 0);
    assert(cflick->pin_le == 2);
    assert(cflick->pin_ckv == 32);
    assert(cflick->pin_sph == 33);

    assert(cflick->pin_oe.expander_addr == 0x20 && cflick->pin_oe.pin == 0);
    assert(cflick->pin_gmode.expander_addr == 0x20 && cflick->pin_gmode.pin == 1);
    assert(cflick->pin_spv.expander_addr == 0x20 && cflick->pin_spv.pin == 2);

    assert(cflick->pmic_i2c_addr == 0x48);

    assert(cflick->waveform != NULL);
    assert(cflick->waveform->levels == 8);
    assert(cflick->waveform->phases == 9);
    // Phase 5 row, cross-checked against the real Arduino waveform3Bit[color][phase=5]
    // column (Inkplate6FLICK.h): color0=1, color1=1, color2=1, color3=1, color4=2,
    // color5=2, color6=2, color7=0.
    const uint8_t expected_wave_flick_row5[MAX_WAVE_LEVELS] = {1, 1, 1, 1, 2, 2, 2, 0};
    assert(memcmp(cflick->waveform->table[5], expected_wave_flick_row5, MAX_WAVE_LEVELS) == 0);
    // Final phase (8) is the all-discharge/park row.
    assert(memcmp(cflick->waveform->table[8], expected_wave_row8, MAX_WAVE_LEVELS) == 0);

    assert(cflick->partial_reps == 5);

    assert(cflick->has_touch == 0);
    assert(cflick->has_frontlight == 0);

    // INKPLATE6PLUSV2: same pin/data-bus layout, same panel resolution as Inkplate6FLICK
    // (1024x758), own waveform table, same partial_reps.
    const board_config_t *c6plusv2 = &board_config_inkplate6plusv2;

    assert(strcmp(c6plusv2->name, "inkplate6plusv2") == 0);

    assert(c6plusv2->width == 1024);
    assert(c6plusv2->height == 758);

    assert(memcmp(c6plusv2->data_pins, expected_data_pins, sizeof(expected_data_pins)) == 0);
    assert(c6plusv2->data_mask == 0x0E8C0030);

    assert(c6plusv2->pin_cl == 0);
    assert(c6plusv2->pin_le == 2);
    assert(c6plusv2->pin_ckv == 32);
    assert(c6plusv2->pin_sph == 33);

    assert(c6plusv2->pin_oe.expander_addr == 0x20 && c6plusv2->pin_oe.pin == 0);
    assert(c6plusv2->pin_gmode.expander_addr == 0x20 && c6plusv2->pin_gmode.pin == 1);
    assert(c6plusv2->pin_spv.expander_addr == 0x20 && c6plusv2->pin_spv.pin == 2);

    assert(c6plusv2->pmic_i2c_addr == 0x48);

    assert(c6plusv2->waveform != NULL);
    assert(c6plusv2->waveform->levels == 8);
    assert(c6plusv2->waveform->phases == 9);
    // Phase 4 row, cross-checked against the real Arduino WAVEFORM3BIT macro's
    // waveform3Bit[color][phase=4] column (Inkplate6PLUS's pins.h/waveforms.h, as pasted
    // by the user and independently transposed via a python3 script): color0=0, color1=1,
    // color2=1, color3=2, color4=2, color5=2, color6=2, color7=2.
    const uint8_t expected_wave_6plusv2_row4[MAX_WAVE_LEVELS] = {0, 1, 1, 2, 2, 2, 2, 2};
    assert(memcmp(c6plusv2->waveform->table[4], expected_wave_6plusv2_row4, MAX_WAVE_LEVELS) ==
           0);
    // Final phase (8) is the all-discharge/park row.
    assert(memcmp(c6plusv2->waveform->table[8], expected_wave_row8, MAX_WAVE_LEVELS) == 0);

    assert(c6plusv2->partial_reps == 5);

    assert(c6plusv2->has_touch == 0);
    assert(c6plusv2->has_frontlight == 0);

    // INKPLATE4TEMPERA: same pin/data-bus layout, own 600x600 resolution, and -- unlike
    // every board above -- only 8 real waveform phases (display3b() loops for(k<8), not
    // for(k<9)).
    const board_config_t *c4t = &board_config_inkplate4tempera;

    assert(strcmp(c4t->name, "inkplate4tempera") == 0);

    assert(c4t->width == 600);
    assert(c4t->height == 600);

    assert(memcmp(c4t->data_pins, expected_data_pins, sizeof(expected_data_pins)) == 0);
    assert(c4t->data_mask == 0x0E8C0030);

    assert(c4t->pin_cl == 0);
    assert(c4t->pin_le == 2);
    assert(c4t->pin_ckv == 32);
    assert(c4t->pin_sph == 33);

    assert(c4t->pin_oe.expander_addr == 0x20 && c4t->pin_oe.pin == 0);
    assert(c4t->pin_gmode.expander_addr == 0x20 && c4t->pin_gmode.pin == 1);
    assert(c4t->pin_spv.expander_addr == 0x20 && c4t->pin_spv.pin == 2);

    assert(c4t->pmic_i2c_addr == 0x48);

    assert(c4t->waveform != NULL);
    assert(c4t->waveform->levels == 8);
    assert(c4t->waveform->phases == 9);
    // Phase 4 row, cross-checked against the real Arduino waveform3Bit[color][phase=4]
    // column (user-supplied full 9-column waveforms.h macro): color0=1, color1=2,
    // color2=0, color3=1, color4=2, color5=1, color6=2, color7=0.
    const uint8_t expected_wave_4t_row4[MAX_WAVE_LEVELS] = {1, 2, 0, 1, 2, 1, 2, 0};
    assert(memcmp(c4t->waveform->table[4], expected_wave_4t_row4, MAX_WAVE_LEVELS) == 0);
    // Both phase 0 and phase 8 are the all-discharge/park row (standard bookend
    // convention, same as every other board).
    assert(memcmp(c4t->waveform->table[0], expected_wave_row8, MAX_WAVE_LEVELS) == 0);
    assert(memcmp(c4t->waveform->table[8], expected_wave_row8, MAX_WAVE_LEVELS) == 0);

    assert(c4t->partial_reps == 9);

    assert(c4t->has_touch == 0);
    assert(c4t->has_frontlight == 0);

    printf("board_config: all assertions passed\n");
    return 0;
}
