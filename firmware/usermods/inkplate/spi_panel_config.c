#include "spi_panel_config.h"

// Inkplate6COLOR (600x448, 4bpp/7-color EPD): pins from the real Arduino reference
// driver (Inkplate6COLORDriver.cpp/.h, pins.h -- user-supplied directly, docs/
// REFACTOR-PLAN.md Phase 9 step 30). Single SPI-controller chip, VSPI-native pins
// (clk=18, din=23 match the ESP32's default VSPI SCK/MOSI, same bus the pre-refactor
// Python driver already claimed via machine.SPI(2)).
const spi_panel_config_t spi_panel_config_inkplate6color = {
    .name = "inkplate6color",

    .width = 600,
    .height = 448,

    .pin_rst = 19,
    .pin_dc = 33,
    .pin_cs = 27,
    .pin_busy = 32,
    .pin_clk = 18,
    .pin_din = 23,

    .spi_freq_hz = 2000000,

    .chip_count = 1,
};
