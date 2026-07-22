/**
 * @file spi_panel_config.h
 * @brief Board configuration for the SPI-controller-panel family (Inkplate6COLOR,
 *        Inkplate2, Inkplate13SPECTRA, Inkplate7SPECTRA).
 *
 * Architecturally separate from board_config.h's parallel-bus/I2S struct: these panels
 * carry their own timing-controller ASIC talked to over a plain SPI bus
 * (CS/DC/RST/BUSY/SCK/MOSI), not a bit-banged 8-bit-wide data bus -- no
 * data_pins[8]/waveform/PMIC fields here.
 */
#ifndef INKPLATE_SPI_PANEL_CONFIG_H
#define INKPLATE_SPI_PANEL_CONFIG_H

#include <stdint.h>

typedef struct {
    const char *name;

    // Panel geometry
    uint16_t width;
    uint16_t height;

    // Direct ESP32 GPIO pins -- this family has no expander-controlled lines involved in
    // the SPI transport itself (Inkplate6COLOR's PCAL6416A at 0x20 only carries VBAT_EN
    // and unused user-GPIO, handled entirely in Python, same as every parallel-bus
    // board's non-hot-path expander use).
    uint8_t pin_rst;
    uint8_t pin_dc;
    uint8_t pin_cs;
    uint8_t pin_busy;
    uint8_t pin_clk;
    uint8_t pin_din; // MOSI

    // SPI clock (2MHz, SPI_MODE0). An earlier MicroPython driver ran this panel at 20MHz
    // instead, untested against real timing margins -- kept at the verified 2MHz here
    // rather than carrying over the unverified faster value; revisit only with real HIL
    // evidence it's safe to raise.
    uint32_t spi_freq_hz;

    // Number of SPI-controller chips this panel carries. Inkplate6COLOR/Inkplate2 are 1;
    // Inkplate13SPECTRA is 2 (dual-chip, one per panel half, each with its own CS).
    uint8_t chip_count;

    // Fields below are only read when chip_count == 2 (Inkplate13SPECTRA today) -- left
    // as 0 (unread) for every chip_count == 1 board, same convention chip_count itself
    // already established. Inkplate7SPECTRA also has a power-enable GPIO and two
    // interface-select straps despite being chip_count == 1 -- it does NOT use these
    // fields for that (see boards/inkplate7spectra/inkplate7spectra.py, which drives
    // those three pins directly via machine.Pin instead).
    uint8_t pin_cs2;    // slave chip's CS (pin_cs above is the master chip's CS)
    uint8_t pin_pwr_en; // panel power-enable GPIO
    uint8_t pin_bs0;    // interface bus-select strap 0 (SPI vs parallel, set once at init)
    uint8_t pin_bs1;    // interface bus-select strap 1
} spi_panel_config_t;

extern const spi_panel_config_t spi_panel_config_inkplate6color;
extern const spi_panel_config_t spi_panel_config_inkplate2;
extern const spi_panel_config_t spi_panel_config_inkplate13spectra;
extern const spi_panel_config_t spi_panel_config_inkplate7spectra;

#endif // INKPLATE_SPI_PANEL_CONFIG_H
