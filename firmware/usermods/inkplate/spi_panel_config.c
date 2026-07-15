#include "spi_panel_config.h"

// Inkplate6COLOR (600x448, 4bpp/7-color EPD): pins from the real Arduino reference
// driver (Inkplate6COLORDriver.cpp/.h, pins.h -- user-supplied directly, docs/
// REFACTOR-PLAN.md Phase 9 step 30). Single SPI-controller chip, VSPI-native pins
// (clk=18, din=23 match the ESP32's default VSPI SCK/MOSI, same bus the pre-refactor
// Python driver already claimed via machine.SPI(2)). See epd_spi.c's own comment on
// EPD_SPI_HOST for why this doesn't collide with machine.SDCard(slot=3), which is on
// HSPI, not VSPI.
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

// Inkplate2 (104x212 native/controller resolution, 1bpp B&W + 1bpp red EPD): pins from
// the real Arduino reference driver (Inkplate2Driver.cpp/.h, pins.h -- user-supplied
// directly, docs/REFACTOR-PLAN.md Phase 9 step 31). Single SPI-controller chip. Unlike
// Inkplate6COLOR, this panel has no SD card.
//
// width/height are the panel's native controller resolution (matches the reference
// driver's E_INK_WIDTH/E_INK_HEIGHT, sent verbatim in the 0x61 resolution-set command),
// not the post-rotation width()/height() the board's default rotation(3) presents to
// callers -- same convention as spi_panel_config_inkplate6color above.
//
// spi_freq_hz = 1MHz, from the real Arduino reference's SPISettings(1000000UL, MSBFIRST,
// SPI_MODE0) -- the pre-refactor Python driver used untested values instead (800kHz at
// wake-init, 20MHz once "awake"), never derived from the reference. Kept at the
// Arduino-verified 1MHz here rather than carrying over either unverified value, same
// rationale as spi_panel_config_inkplate6color's own spi_freq_hz comment -- revisit only
// with real HIL evidence a higher speed is safe.
const spi_panel_config_t spi_panel_config_inkplate2 = {
    .name = "inkplate2",

    .width = 104,
    .height = 212,

    .pin_rst = 19,
    .pin_dc = 33,
    .pin_cs = 27,
    .pin_busy = 32,
    .pin_clk = 18,
    .pin_din = 23,

    .spi_freq_hz = 1000000,

    .chip_count = 1,
};
