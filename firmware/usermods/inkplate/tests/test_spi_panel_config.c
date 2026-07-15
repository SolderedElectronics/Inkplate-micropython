// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_spi_panel_config.c ../spi_panel_config.c -o test_spi_panel_config
// && ./test_spi_panel_config
#include <assert.h>
#include <string.h>

#include "../spi_panel_config.h"

int main(void)
{
    const spi_panel_config_t *cfg = &spi_panel_config_inkplate6color;

    assert(strcmp(cfg->name, "inkplate6color") == 0);

    assert(cfg->width == 600);
    assert(cfg->height == 448);

    // Pins from the real Arduino reference driver's pins.h.
    assert(cfg->pin_rst == 19);
    assert(cfg->pin_dc == 33);
    assert(cfg->pin_cs == 27);
    assert(cfg->pin_busy == 32);
    assert(cfg->pin_clk == 18);
    assert(cfg->pin_din == 23);

    assert(cfg->spi_freq_hz == 2000000);
    assert(cfg->chip_count == 1);

    return 0;
}
