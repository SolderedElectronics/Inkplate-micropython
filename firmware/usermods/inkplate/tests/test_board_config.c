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
    assert(cfg->waveform->levels == 4);
    const uint8_t expected_wave_row0[MAX_WAVE_PHASES] = {1, 1, 2, 0, 0, 0, 0, 0};
    assert(memcmp(cfg->waveform->table[0], expected_wave_row0, MAX_WAVE_PHASES) == 0);

    assert(cfg->has_touch == 0);
    assert(cfg->has_frontlight == 0);

    printf("board_config: all assertions passed\n");
    return 0;
}
