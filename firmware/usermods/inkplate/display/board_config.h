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

// Waveform table: one row per phase, one column per gray level (pixel value 0..levels-1).
// Row order matches the sequence the display gets written N times, in order.
// table[phase][level] -> code: 0=discharge,1=black,2=white,3=skip
// Inkplate10 is populated with the real 3-bit/8-level table (Arduino reference driver's
// default `waveform1`, transposed from its [color][phase] layout to this struct's
// [phase][color] layout -- docs/REFACTOR-PLAN.md Phase 5 step 15).
#define MAX_WAVE_PHASES 9
#define MAX_WAVE_LEVELS 8

typedef struct {
    uint8_t levels; // number of gray levels (pixel values) this table encodes (4 or 8)
    uint8_t phases; // number of phases actually used (rows of table[])
    uint8_t table[MAX_WAVE_PHASES][MAX_WAVE_LEVELS];
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

    // Number of times a mono partial-update frame gets pushed over I2S (fixed pulse-train
    // length, not a data-dependent loop bound) -- board/variant-specific per the real
    // Arduino reference driver (INKPLATE6=5, INKPLATE6V2=6); Inkplate10 uses 5, carried
    // over from this project's own already-HIL-verified value (docs/REFACTOR-PLAN.md
    // step 16), not derived from either Inkplate6 variant's number.
    uint8_t partial_reps;

    // Feature flags
    uint8_t has_touch;
    uint8_t has_frontlight;
} board_config_t;

extern const board_config_t board_config_inkplate10v1;
extern const board_config_t board_config_inkplate10v2;
extern const board_config_t board_config_inkplate6v1;
extern const board_config_t board_config_inkplate6v2;
extern const board_config_t board_config_inkplate5v2;
extern const board_config_t board_config_inkplate6flick;
extern const board_config_t board_config_inkplate6plusv2;
extern const board_config_t board_config_inkplate4tempera;

// board_config_row_bytes: bytes needed for one row of 2-bit-per-pixel wire codes --
// driven only by panel width, since the wire format is always 2 bits/pixel regardless
// of the source framebuffer's bit depth (1bpp mono expands into it, 2bpp GS maps 1:1).
// epd_i2s.c and any future GS I2S path should derive row-buffer size from this instead
// of hand-rolling width>>2/width>>3 per call site.
static inline uint16_t board_config_row_bytes(const board_config_t *cfg)
{
    return cfg->width >> 2;
}

#endif // INKPLATE_BOARD_CONFIG_H
