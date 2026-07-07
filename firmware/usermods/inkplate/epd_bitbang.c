#include "epd_bitbang.h"
#include "expander_bridge.h"

#include "esp_rom_sys.h"
#include "soc/gpio_struct.h"

// Resolves a GPIO number to its W1TS/W1TC register pair + bit mask once per call site
// (not per bit-toggle), so the hot per-row loop below stays branch-free -- matching how
// the original viper implementation pre-hoisted its register/mask constants. Pins 0-31
// live in the low GPIO word (out_w1ts/out_w1tc), pins 32-39 in the high word
// (out1_w1ts/out1_w1tc).
typedef struct {
    volatile uint32_t *w1ts;
    volatile uint32_t *w1tc;
    uint32_t mask;
} fast_pin_t;

static fast_pin_t resolve_pin(uint8_t gpio_num)
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

static inline void fast_pin_set(fast_pin_t p)
{
    *p.w1ts = p.mask;
}

static inline void fast_pin_clear(fast_pin_t p)
{
    *p.w1tc = p.mask;
}

void epd_vscan_start(const board_config_t *cfg)
{
    fast_pin_t ckv = resolve_pin(cfg->pin_ckv);

    // Start a vertical scan pulse.
    fast_pin_set(ckv);
    esp_rom_delay_us(7);
    expander_bridge_write(cfg->pin_spv.expander_addr, cfg->pin_spv.pin, 0);
    esp_rom_delay_us(10);
    fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    fast_pin_set(ckv);
    esp_rom_delay_us(8);
    expander_bridge_write(cfg->pin_spv.expander_addr, cfg->pin_spv.pin, 1);
    esp_rom_delay_us(10);

    // Pulse through 3 scan lines that end up being invisible.
    fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    fast_pin_set(ckv);
    esp_rom_delay_us(18);
    fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    fast_pin_set(ckv);
    esp_rom_delay_us(18);
    fast_pin_clear(ckv);
    esp_rom_delay_us(0);
    fast_pin_set(ckv);
}

void epd_vscan_write(const board_config_t *cfg)
{
    fast_pin_t ckv = resolve_pin(cfg->pin_ckv);
    fast_pin_t le = resolve_pin(cfg->pin_le);

    fast_pin_clear(ckv); // remove gate drive
    fast_pin_set(le);    // pulse to latch row
    fast_pin_set(le);    // delay a tiny bit
    fast_pin_clear(le);
    fast_pin_clear(le); // delay a tiny bit
    esp_rom_delay_us(0);
    fast_pin_set(ckv); // apply gate drive to next row
}

void epd_vscan_end(const board_config_t *cfg)
{
    fast_pin_t sph = resolve_pin(cfg->pin_sph);
    fast_pin_t le = resolve_pin(cfg->pin_le);

    fast_pin_clear(sph);
    fast_pin_set(le);
    fast_pin_clear(le);
}

void epd_fill_screen(const board_config_t *cfg, uint32_t data)
{
    fast_pin_t cl = resolve_pin(cfg->pin_cl);
    fast_pin_t le = resolve_pin(cfg->pin_le);
    fast_pin_t ckv = resolve_pin(cfg->pin_ckv);
    fast_pin_t sph = resolve_pin(cfg->pin_sph);

    // Set the data output gpios. cfg->data_mask and `data` are both produced by the
    // byte2gpio table, which only ever sets bits for pins 0-31 on every Inkplate board
    // today, so a single low-word register write covers the whole data bus.
    // Routed through volatile pointers (not direct GPIO.out_w1tc/out_w1ts field writes)
    // so the compiler can't reorder these relative to each other or to fast_pin_clear(cl)
    // below -- writes to different objects have no ordering guarantee otherwise.
    volatile uint32_t *w1ts0 = &GPIO.out_w1ts;
    volatile uint32_t *w1tc0 = &GPIO.out_w1tc;
    *w1tc0 = cfg->data_mask;
    fast_pin_clear(cl);
    *w1ts0 = data;

    for (uint16_t row = 0; row < cfg->height; row++) {
        // Send first byte of row with start-row signal.
        fast_pin_clear(sph);
        fast_pin_set(cl);
        fast_pin_clear(cl);
        fast_pin_set(sph);

        // Send remaining bytes (we overshoot by one, which is OK).
        int i = cfg->width >> 3;
        while (i-- > 0) {
            fast_pin_set(cl);
            fast_pin_clear(cl);
            fast_pin_set(cl);
            fast_pin_clear(cl);
        }

        // Latch row and advance to the next (inlined epd_vscan_write -- this loop runs
        // 825x/frame, so it stays inlined rather than paying a real call per row; see
        // epd_vscan_write for the standalone version used by clean()/vscan_start callers).
        fast_pin_clear(ckv);
        fast_pin_set(le);
        fast_pin_set(le);
        fast_pin_clear(le);
        fast_pin_clear(le);
        esp_rom_delay_us(0);
        fast_pin_set(ckv);
    }
}
