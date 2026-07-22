// Host-compiled unit test, no ESP-IDF/hardware dependency.
// Build/run: gcc -I.. test_spi_panel_config.c ../spi_panel_config.c -o test_spi_panel_config
// && ./test_spi_panel_config
#include <assert.h>
#include <string.h>

#include "../display/spi_panel_config.h"

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

    const spi_panel_config_t *cfg2 = &spi_panel_config_inkplate2;

    assert(strcmp(cfg2->name, "inkplate2") == 0);

    assert(cfg2->width == 104);
    assert(cfg2->height == 212);

    // Pins from the real Arduino reference driver's pins.h.
    assert(cfg2->pin_rst == 19);
    assert(cfg2->pin_dc == 33);
    assert(cfg2->pin_cs == 27);
    assert(cfg2->pin_busy == 32);
    assert(cfg2->pin_clk == 18);
    assert(cfg2->pin_din == 23);

    assert(cfg2->spi_freq_hz == 1000000);
    assert(cfg2->chip_count == 1);

    const spi_panel_config_t *cfg3 = &spi_panel_config_inkplate13spectra;

    assert(strcmp(cfg3->name, "inkplate13spectra") == 0);

    assert(cfg3->width == 1200);
    assert(cfg3->height == 1600);

    // Pins from the real Arduino reference driver's pins.h.
    assert(cfg3->pin_rst == 4);
    assert(cfg3->pin_dc == 14);
    assert(cfg3->pin_cs == 42);
    assert(cfg3->pin_busy == 7);
    assert(cfg3->pin_clk == 38);
    assert(cfg3->pin_din == 40);

    assert(cfg3->spi_freq_hz == 10000000);
    assert(cfg3->chip_count == 2);

    assert(cfg3->pin_cs2 == 39);
    assert(cfg3->pin_pwr_en == 21);
    assert(cfg3->pin_bs0 == 6);
    assert(cfg3->pin_bs1 == 5);

    const spi_panel_config_t *cfg4 = &spi_panel_config_inkplate7spectra;

    assert(strcmp(cfg4->name, "inkplate7spectra") == 0);

    assert(cfg4->width == 800);
    assert(cfg4->height == 480);

    // Pins from the real Arduino reference driver's pins.h.
    assert(cfg4->pin_rst == 4);
    assert(cfg4->pin_dc == 14);
    assert(cfg4->pin_cs == 42);
    assert(cfg4->pin_busy == 7);
    assert(cfg4->pin_clk == 38);
    assert(cfg4->pin_din == 40);

    assert(cfg4->spi_freq_hz == 8000000);
    assert(cfg4->chip_count == 1);

    // PWR_EN/BS0/BS1 are intentionally NOT modeled in this struct -- see
    // spi_panel_config_inkplate7spectra's own comment in spi_panel_config.c.
    assert(cfg4->pin_cs2 == 0);
    assert(cfg4->pin_pwr_en == 0);
    assert(cfg4->pin_bs0 == 0);
    assert(cfg4->pin_bs1 == 0);

    return 0;
}
