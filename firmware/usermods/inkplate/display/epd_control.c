/**
 * @file epd_control.c
 * @brief Bit-banged EPD control-line primitives (vscan_start/write/end, fill_screen).
 */
#include "epd_control.h"
#include "expander_bridge.h"

#include "esp_rom_sys.h"

void epd_vscan_start(const board_config_t *cfg)
{
    fast_pin_t ckv = epd_resolve_pin(cfg->pin_ckv);

    // Start a vertical scan pulse.
    epd_fast_pin_set(ckv);
    esp_rom_delay_us(7);
    expander_bridge_write(cfg->pin_spv.expander_addr, cfg->pin_spv.pin, 0);
    esp_rom_delay_us(10);
    epd_fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    epd_fast_pin_set(ckv);
    esp_rom_delay_us(8);
    expander_bridge_write(cfg->pin_spv.expander_addr, cfg->pin_spv.pin, 1);
    esp_rom_delay_us(10);

    // Pulse through 3 scan lines that end up being invisible.
    epd_fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    epd_fast_pin_set(ckv);
    esp_rom_delay_us(18);
    epd_fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    epd_fast_pin_set(ckv);
    esp_rom_delay_us(18);
    epd_fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    epd_fast_pin_set(ckv);
}

void epd_vscan_write(const board_config_t *cfg)
{
    fast_pin_t ckv = epd_resolve_pin(cfg->pin_ckv);
    fast_pin_t le = epd_resolve_pin(cfg->pin_le);

    epd_fast_pin_clear(ckv); // Remove gate drive
    epd_fast_pin_set(le);    // Pulse to latch row
    epd_fast_pin_set(le);    // Delay a tiny bit
    epd_fast_pin_clear(le);
    epd_fast_pin_clear(le); // Delay a tiny bit
    esp_rom_delay_us(0);
    epd_fast_pin_set(ckv); // Apply gate drive to next row
}

void epd_vscan_end(const board_config_t *cfg)
{
    fast_pin_t sph = epd_resolve_pin(cfg->pin_sph);
    fast_pin_t le = epd_resolve_pin(cfg->pin_le);

    epd_fast_pin_clear(sph);
    epd_fast_pin_set(le);
    epd_fast_pin_clear(le);
}

void epd_fill_screen(const board_config_t *cfg, uint32_t data)
{
    fast_pin_t cl = epd_resolve_pin(cfg->pin_cl);
    fast_pin_t le = epd_resolve_pin(cfg->pin_le);
    fast_pin_t ckv = epd_resolve_pin(cfg->pin_ckv);
    fast_pin_t sph = epd_resolve_pin(cfg->pin_sph);

    // Set the data output gpios. cfg->data_mask and `data` are both produced by the
    // byte2gpio table, which only ever sets bits for pins 0-31 on every Inkplate board
    // today, so a single low-word register write covers the whole data bus.
    // Routed through volatile pointers (not direct GPIO.out_w1tc/out_w1ts field writes)
    // so the compiler can't reorder these relative to each other or to
    // epd_fast_pin_clear(cl) below -- writes to different objects have no ordering
    // guarantee otherwise.
    volatile uint32_t *w1ts0 = &GPIO.out_w1ts;
    volatile uint32_t *w1tc0 = &GPIO.out_w1tc;
    *w1tc0 = cfg->data_mask;
    epd_fast_pin_clear(cl);
    *w1ts0 = data;

    for (uint16_t row = 0; row < cfg->height; row++) {
        // Send first byte of row with start-row signal.
        epd_fast_pin_clear(sph);
        epd_fast_pin_set(cl);
        epd_fast_pin_clear(cl);
        epd_fast_pin_set(sph);

        // Send remaining bytes (we overshoot by one, which is OK).
        int i = cfg->width >> 3;
        while (i-- > 0) {
            epd_fast_pin_set(cl);
            epd_fast_pin_clear(cl);
            epd_fast_pin_set(cl);
            epd_fast_pin_clear(cl);
        }

        // Latch row and advance to the next (inlined epd_vscan_write -- this loop runs
        // 825x/frame, so it stays inlined rather than paying a real call per row; see
        // epd_vscan_write for the standalone version used by clean()/vscan_start callers).
        epd_fast_pin_clear(ckv);
        epd_fast_pin_set(le);
        epd_fast_pin_set(le);
        epd_fast_pin_clear(le);
        epd_fast_pin_clear(le);
        esp_rom_delay_us(0);
        epd_fast_pin_set(ckv);
    }
}
