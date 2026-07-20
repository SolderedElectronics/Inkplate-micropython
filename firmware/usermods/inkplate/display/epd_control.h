/**
 * @file epd_control.h
 * @brief Bit-banged control-line driver for the classic-ESP32 parallel EPD bus
 *        (SPH/CL/LE/CKV/SPV via direct GPIO register writes).
 *
 * No DMA/framebuffer here -- see epd_i2s.c for the pixel-data path. Provides the
 * row-scan/clear primitives (vscan_start/vscan_write/vscan_end/fill_screen) every
 * board's clean()/begin() build on.
 */
#ifndef INKPLATE_EPD_CONTROL_H
#define INKPLATE_EPD_CONTROL_H

#include "board_config.h"
#include <stdint.h>

// Header-only so each translation unit gets its own inlined copy, no new object
// file/link dependency introduced.
#include "soc/gpio_struct.h"

typedef struct {
    volatile uint32_t *w1ts;
    volatile uint32_t *w1tc;
    uint32_t mask;
} fast_pin_t;

// Pins 0-31 live in the low GPIO word (out_w1ts/out_w1tc), pins 32-39 in the high word
// (out1_w1ts/out1_w1tc).
/**
 * @brief Resolves a GPIO number to its W1TS/W1TC register pair and bit mask.
 * @param gpio_num GPIO pin number, 0-39.
 * @return fast_pin_t encoding the pin's set/clear registers and mask.
 */
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

/**
 * @brief Drives a resolved GPIO pin high.
 * @param p Fast-pin descriptor from epd_resolve_pin().
 */
static inline void epd_fast_pin_set(fast_pin_t p)
{
    *p.w1ts = p.mask;
}

/**
 * @brief Drives a resolved GPIO pin low.
 * @param p Fast-pin descriptor from epd_resolve_pin().
 */
static inline void epd_fast_pin_clear(fast_pin_t p)
{
    *p.w1tc = p.mask;
}

/**
 * @brief Begins a vertical scan, toggling SPV and CKV to prime the panel for a new frame.
 * Call once before the first epd_vscan_write() of a frame.
 * @param cfg Board configuration providing pin_ckv/pin_spv.
 */
void epd_vscan_start(const board_config_t *cfg);

/**
 * @brief Latches the current row into the display and advances the gate drive to the
 * next row.
 * @param cfg Board configuration providing pin_ckv/pin_le.
 */
void epd_vscan_write(const board_config_t *cfg);

/**
 * @brief Ends a vertical scan by dropping SPH and pulsing LE.
 * @param cfg Board configuration providing pin_sph/pin_le.
 */
void epd_vscan_end(const board_config_t *cfg);

/**
 * @brief Writes the same data-bus pattern to every row of the panel, for full-screen
 * clean/clear passes.
 * @param cfg Board configuration providing pin geometry and data_mask.
 * @param data W1TS0/W1TC0-register-form value, as produced by the byte2gpio lookup table.
 */
void epd_fill_screen(const board_config_t *cfg, uint32_t data);

#endif // INKPLATE_EPD_CONTROL_H
