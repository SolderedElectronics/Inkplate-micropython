#include "spi_panel_config.h"

// Shared pin layout for the single-SPI-controller-chip classic-ESP32 panels (6COLOR,
// Inkplate2) -- both use the same VSPI pins. Inkplate13SPECTRA is a separate ESP32-S3
// board with its own dual-chip pinout and doesn't use this macro.
#define INKPLATE_SPI_CLASSIC_PINS                                                                \
    .pin_rst = 19, .pin_dc = 33, .pin_cs = 27, .pin_busy = 32, .pin_clk = 18, .pin_din = 23

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

    INKPLATE_SPI_CLASSIC_PINS,

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

    INKPLATE_SPI_CLASSIC_PINS,

    .spi_freq_hz = 1000000,

    .chip_count = 1,
};

// Inkplate13SPECTRA (1200x1600 native controller resolution, 4bpp/6-color GDEP133C02
// panel, dual SPI-controller chip -- one per panel half): pins from the real Arduino
// reference driver (Inkplate13SPECTRADriver.cpp/.h, pins.h -- user-supplied directly,
// docs/REFACTOR-PLAN.md Phase 9 step 31). ESP32-S3 board, not classic ESP32 like the
// other two panels in this family -- built as its own firmware target, so sharing this
// struct/API doesn't imply sharing a binary.
//
// width/height are the panel's native controller resolution (matches the reference
// driver's E_INK_WIDTH/E_INK_HEIGHT), not the post-rotation width()/height() the board's
// default rotation(1) presents to callers -- same convention as the two configs above.
//
// spi_freq_hz = 10MHz, from the real Arduino reference's SPISettings(10000000, MSBFIRST,
// SPI_MODE0).
//
// pin_cs is the master chip's CS (left half); pin_cs2 is the slave chip's CS (right
// half). pin_pwr_en/pin_bs0/pin_bs1 have no equivalent on the single-chip panels above --
// pwr_en gates the panel's own power supply (absent on 6COLOR/Inkplate2, whose power
// comes from the board's shared VBAT rail), bs0/bs1 are GDEP133C02 interface-select
// straps (SPI vs parallel) the reference driver sets once and never toggles again.
const spi_panel_config_t spi_panel_config_inkplate13spectra = {
    .name = "inkplate13spectra",

    .width = 1200,
    .height = 1600,

    .pin_rst = 4,
    .pin_dc = 14,
    .pin_cs = 42,
    .pin_busy = 7,
    .pin_clk = 38,
    .pin_din = 40,

    .spi_freq_hz = 10000000,

    .chip_count = 2,

    .pin_cs2 = 39,
    .pin_pwr_en = 21,
    .pin_bs0 = 6,
    .pin_bs1 = 5,
};
