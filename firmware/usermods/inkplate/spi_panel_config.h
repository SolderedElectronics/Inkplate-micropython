// Board configuration for the SPI-controller-panel family (Inkplate6COLOR, Inkplate2,
// Inkplate13SPECTRA) -- docs/REFACTOR-PLAN.md Phase 9 step 29. Architecturally separate
// from board_config.h's parallel-bus/I2S struct: these panels carry their own
// timing-controller ASIC talked to over a plain SPI bus (CS/DC/RST/BUSY/SCK/MOSI), not a
// bit-banged 8-bit-wide data bus -- no data_pins[8]/waveform/PMIC fields here.
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

    // SPI clock, from the real Arduino reference driver's SPISettings (2MHz, SPI_MODE0).
    // The pre-refactor MicroPython driver ran this panel at 20MHz instead (untested
    // against real timing margins, not derived from the reference) -- kept at the
    // Arduino-verified 2MHz here rather than carrying over the unverified faster value;
    // revisit only with real HIL evidence it's safe to raise.
    uint32_t spi_freq_hz;

    // Number of SPI-controller chips this panel carries. Inkplate6COLOR/Inkplate2 are 1;
    // Inkplate13SPECTRA is 2 (dual-chip, one per panel half, each with its own CS) --
    // epd_spi.c only implements the chip_count==1 case so far. Field exists now so this
    // struct's shape doesn't need to change again once Inkplate13SPECTRA is wired
    // (docs/REFACTOR-PLAN.md Phase 9 step 31).
    uint8_t chip_count;
} spi_panel_config_t;

extern const spi_panel_config_t spi_panel_config_inkplate6color;

#endif // INKPLATE_SPI_PANEL_CONFIG_H
