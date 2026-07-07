// Board configuration struct shared by all classic-ESP32 parallel-bus Inkplate boards
// (Inkplate10/6/5v2/6FLICK/6PLUS/4TEMPERA). One instance per board, selected at build/init time.
#ifndef INKPLATE_BOARD_CONFIG_H
#define INKPLATE_BOARD_CONFIG_H

#include <stdint.h>

// Combines 8 GPIO numbers into the W1TS/W1TC bitmask covering all of them -- use this to
// derive a board's data_mask from its data_pins instead of hand-translating to hex, so the
// two fields can't silently drift apart.
#define INKPLATE_DATA_MASK8(p0, p1, p2, p3, p4, p5, p6, p7)                                      \
    ((1u << (p0)) | (1u << (p1)) | (1u << (p2)) | (1u << (p3)) | (1u << (p4)) | (1u << (p5)) |   \
     (1u << (p6)) | (1u << (p7)))

// Waveform table: [level_from][level_to] -> phase codes, MAX_WAVE_PHASES codes per entry.
// Populated with the 2-bit (4-level) waveform until 3-bit tables are confirmed per board (Phase 5).
#define MAX_WAVE_LEVELS 8
#define MAX_WAVE_PHASES 8

typedef struct {
    uint8_t levels; // number of gray levels this table encodes (4 or 8)
    uint8_t phases; // number of phases per entry actually used
    uint8_t table[MAX_WAVE_LEVELS]
                 [MAX_WAVE_PHASES]; // phase codes: 0=discharge,1=black,2=white,3=skip
} waveform_table_t;

typedef struct {
    uint8_t expander_addr; // PCAL6416A I2C address
    uint8_t pin;           // pin number within that expander (0-15)
} expander_pin_t;

typedef struct {
    const char *name;

    // Panel geometry
    uint16_t width;
    uint16_t height;

    // Data bus: GPIO number for each of D0..D7, plus the combined W1TS/W1TC bitmask
    uint8_t data_pins[8];
    uint32_t data_mask;

    // Control lines (direct ESP32 GPIO, bit-banged in Phase 2, I2S-driven from Phase 3)
    uint8_t pin_cl;
    uint8_t pin_le;
    uint8_t pin_ckv;
    uint8_t pin_sph;

    // PCAL6416A-controlled lines
    expander_pin_t pin_oe;
    expander_pin_t pin_gmode;
    expander_pin_t pin_spv;

    // Power management IC (TPS65186)
    uint8_t pmic_i2c_addr;

    // Waveform data
    const waveform_table_t *waveform;

    // Feature flags
    uint8_t has_touch;
    uint8_t has_frontlight;
} board_config_t;

extern const board_config_t board_config_inkplate10;

#endif // INKPLATE_BOARD_CONFIG_H
