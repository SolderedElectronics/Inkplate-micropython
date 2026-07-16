// Bit-banged control-line driver for the classic-ESP32 parallel EPD bus.
// De-risking step (Phase 2 of docs/REFACTOR-PLAN.md): proves the C port can drive the
// panel via direct GPIO register writes before I2S/DMA (Phase 3) is introduced.
// No DMA, no framebuffer/data-path here -- only the SPH/CL/LE/CKV/SPV control-line
// sequencing that scans one row at a time, matching boards/inkplate10/inkplate10.py's
// vscan_start/vscan_write/vscan_end/fill_screen byte-for-byte.
#ifndef INKPLATE_EPD_BITBANG_H
#define INKPLATE_EPD_BITBANG_H

#include "board_config.h"
#include <stdint.h>

// Shared by epd_bitbang.c and epd_partial.c (both bit-bang the data/CL/SPH lines
// directly). Header-only so each translation unit gets its own inlined copy, no new
// object file/link dependency introduced.
#include "soc/gpio_struct.h"

typedef struct {
    volatile uint32_t *w1ts;
    volatile uint32_t *w1tc;
    uint32_t mask;
} fast_pin_t;

// Resolves a GPIO number to its W1TS/W1TC register pair + bit mask. Pins 0-31 live in
// the low GPIO word (out_w1ts/out_w1tc), pins 32-39 in the high word
// (out1_w1ts/out1_w1tc).
static inline fast_pin_t epd_resolve_pin(uint8_t gpio_num)
{
    fast_pin_t p;
    if (gpio_num < 32) {
        p.w1ts = &GPIO.out_w1ts;
        p.w1tc = &GPIO.out_w1tc;
        p.mask = 1u << gpio_num;
    } else {
        p.w1ts = &GPIO.out1_w1ts.val;
        p.w1tc = &GPIO.out1_w1tc.val;
        p.mask = 1u << (gpio_num - 32);
    }
    return p;
}

static inline void epd_fast_pin_set(fast_pin_t p)
{
    *p.w1ts = p.mask;
}

static inline void epd_fast_pin_clear(fast_pin_t p)
{
    *p.w1tc = p.mask;
}

// Begins a vertical scan: toggles SPV (via the expander bridge) and CKV to prime the
// panel for a new frame. Call once before the first epd_vscan_write() of a frame.
void epd_vscan_start(const board_config_t *cfg);

// Latches the current row into the display and advances the gate drive to the next row.
void epd_vscan_write(const board_config_t *cfg);

// Ends a vertical scan by dropping SPH and pulsing LE.
void epd_vscan_end(const board_config_t *cfg);

// Writes the same data-bus pattern to every row of the panel -- used for full-screen
// clean/clear passes. `data` is a W1TS0/W1TC0-register-form value, as produced by the
// (still Python-side) byte2gpio lookup table -- same contract as the original
// _Inkplate.fill_screen(data) it replaces.
void epd_fill_screen(const board_config_t *cfg, uint32_t data);

#endif // INKPLATE_EPD_BITBANG_H
