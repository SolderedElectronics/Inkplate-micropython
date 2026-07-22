/**
 * @file spi_panel_config.c
 * @brief Board configuration data for the SPI-controller-panel family.
 */
#include "spi_panel_config.h"

// Shared pin layout for the single-SPI-controller-chip classic-ESP32 panels (6COLOR,
// Inkplate2) -- both use the same VSPI pins. Inkplate13SPECTRA is a separate ESP32-S3
// board with its own dual-chip pinout and doesn't use this macro.
#define INKPLATE_SPI_CLASSIC_PINS                                                                \
    .pin_rst = 19, .pin_dc = 33, .pin_cs = 27, .pin_busy = 32, .pin_clk = 18, .pin_din = 23

// Inkplate6COLOR (600x448, 4bpp/7-color EPD). Single SPI-controller chip, VSPI-native
// pins (clk=18, din=23 match the ESP32's default VSPI SCK/MOSI, same bus the previous
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

// Inkplate2 (104x212 native/controller resolution, 1bpp B&W + 1bpp red EPD). Single
// SPI-controller chip. Unlike Inkplate6COLOR, this panel has no SD card.
//
// width/height are the panel's native controller resolution (matches E_INK_WIDTH/
// E_INK_HEIGHT, sent verbatim in the 0x61 resolution-set command), not the post-rotation
// width()/height() the board's default rotation(3) presents to callers -- same convention
// as spi_panel_config_inkplate6color above.
//
// spi_freq_hz = 1MHz (SPI_MODE0). An earlier Python driver used untested values instead
// (800kHz at wake-init, 20MHz once "awake"). Kept at the verified 1MHz here rather than
// carrying over either unverified value, same rationale as
// spi_panel_config_inkplate6color's own spi_freq_hz comment -- revisit only with real HIL
// evidence a higher speed is safe.
const spi_panel_config_t spi_panel_config_inkplate2 = {
    .name = "inkplate2",

    .width = 104,
    .height = 212,

    INKPLATE_SPI_CLASSIC_PINS,

    .spi_freq_hz = 1000000,

    .chip_count = 1,
};

// Inkplate13SPECTRA (1200x1600 native controller resolution, 4bpp/6-color GDEP133C02
// panel, dual SPI-controller chip -- one per panel half). ESP32-S3 board, not classic
// ESP32 like the other two panels in this family -- built as its own firmware target, so
// sharing this struct/API doesn't imply sharing a binary.
//
// width/height are the panel's native controller resolution (matches E_INK_WIDTH/
// E_INK_HEIGHT), not the post-rotation width()/height() the board's default rotation(1)
// presents to callers -- same convention as the two configs above.
//
// spi_freq_hz = 10MHz (SPI_MODE0).
//
// pin_cs is the master chip's CS (left half); pin_cs2 is the slave chip's CS (right
// half). pin_pwr_en/pin_bs0/pin_bs1 have no equivalent on the single-chip panels above --
// pwr_en gates the panel's own power supply (absent on 6COLOR/Inkplate2, whose power
// comes from the board's shared VBAT rail), bs0/bs1 are GDEP133C02 interface-select
// straps (SPI vs parallel) set once and never toggled again.
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

// Inkplate7SPECTRA (800x480 native controller resolution, 4bpp/6-color GDEP-family
// panel, single SPI-controller chip). ESP32-S3 board, same eval-board pinout as
// Inkplate13SPECTRA (RST/DC/CS/BUSY/CLK/DIN pin numbers are identical between the two
// vendor Arduino drivers) but chip_count == 1, not 2.
//
// The vendor driver also drives a panel power-enable GPIO (PWR_EN, pin 21) and two
// interface bus-select straps (BS0/BS1, pins 6/5) -- same pin numbers Inkplate13SPECTRA
// uses its pin_pwr_en/pin_bs0/pin_bs1 fields for. This struct deliberately leaves those
// fields at 0/unused: reusing them here would mean going through
// epd_spi_dual_power_up_io()/epd_spi_dual_pins_low(), which unconditionally also
// configures pin_cs2 as a second CS output -- for a chip_count == 1 board pin_cs2 is 0
// (GPIO0), and toggling that as a bogus "slave CS" is wrong. Instead, PWR_EN/BS0/BS1 are
// driven directly from Python as plain machine.Pin GPIOs, the same as any other
// board-specific non-hot-path GPIO in this codebase (see
// boards/inkplate7spectra/inkplate7spectra.py). Only RST/DC/CS/BUSY/CLK/DIN go through
// the C epd_spi_* single-chip transport, same as Inkplate6COLOR/Inkplate2 above.
//
// spi_freq_hz = 8MHz (SPI_MODE0), matching the vendor Arduino driver's epdSpiSettings.
const spi_panel_config_t spi_panel_config_inkplate7spectra = {
    .name = "inkplate7spectra",

    .width = 800,
    .height = 480,

    .pin_rst = 4,
    .pin_dc = 14,
    .pin_cs = 42,
    .pin_busy = 7,
    .pin_clk = 38,
    .pin_din = 40,

    .spi_freq_hz = 8000000,

    .chip_count = 1,
};
