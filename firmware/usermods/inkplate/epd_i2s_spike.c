#include "epd_i2s_spike.h"

#include "epd_bitbang.h"
#include "driver/gpio.h"
#include "driver/periph_ctrl.h"
#include "esp_heap_caps.h"
#include "esp_rom_gpio.h"
#include "esp_rom_sys.h"
#include "soc/gpio_sig_map.h"
#include "soc/gpio_struct.h"
#include "soc/i2s_reg.h"
#include "soc/i2s_struct.h"
#include "rom/lldesc.h"

// Ported from the Arduino reference driver's UtilI2S::I2SInit/sendDataI2S. Uses I2S1,
// not I2S0 -- I2S0 doesn't support 8-bit parallel/LCD mode on classic ESP32 (per the
// reference driver's own comment), even though docs/REFACTOR-PLAN.md's Phase 3 intro
// says I2S0; trusting the working reference code over the plan doc's phrasing.
#define I2S_CLOCK_DIVIDER                                                                        \
    5   // placeholder from reference driver default; retune once
        // waveform timing is confirmed on the logic analyzer

// Minimal duplicate of epd_bitbang.c's fast-pin helper -- kept local rather than shared,
// since this whole file is throwaway (deleted once step 9's real component lands).
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

static const uint32_t data_out_sig[8] = {
    I2S1O_DATA_OUT0_IDX, I2S1O_DATA_OUT1_IDX, I2S1O_DATA_OUT2_IDX, I2S1O_DATA_OUT3_IDX,
    I2S1O_DATA_OUT4_IDX, I2S1O_DATA_OUT5_IDX, I2S1O_DATA_OUT6_IDX, I2S1O_DATA_OUT7_IDX,
};

static lldesc_t row_desc;
static uint8_t *row_buf;

void epd_i2s_spike_init(const board_config_t *cfg)
{
    // Wire D0-D7 -> I2S1 data-out signals, CL -> I2S1 BCK-out, straight 1:1 per
    // data_pins[i] (this IS what step 8 verifies -- confirms whether the existing
    // byte2gpio scatter/gather remap is still needed once GPIO-matrix routing is in play).
    for (int i = 0; i < 8; i++) {
        gpio_set_direction(cfg->data_pins[i], GPIO_MODE_OUTPUT);
        gpio_set_drive_capability(cfg->data_pins[i], GPIO_DRIVE_CAP_3);
        esp_rom_gpio_connect_out_signal(cfg->data_pins[i], data_out_sig[i], false, false);
    }
    gpio_set_direction(cfg->pin_cl, GPIO_MODE_OUTPUT);
    gpio_set_drive_capability(cfg->pin_cl, GPIO_DRIVE_CAP_3);
    esp_rom_gpio_connect_out_signal(cfg->pin_cl, I2S1O_BCK_OUT_IDX, false, false);

    periph_module_enable(PERIPH_I2S1_MODULE);
    periph_module_reset(PERIPH_I2S1_MODULE);

    I2S1.conf.rx_fifo_reset = 1;
    I2S1.conf.rx_fifo_reset = 0;
    I2S1.conf.tx_fifo_reset = 1;
    I2S1.conf.tx_fifo_reset = 0;

    I2S1.lc_conf.in_rst = 1;
    I2S1.lc_conf.in_rst = 0;
    I2S1.lc_conf.out_rst = 1;
    I2S1.lc_conf.out_rst = 0;

    I2S1.conf.rx_reset = 1;
    I2S1.conf.tx_reset = 1;
    I2S1.conf.rx_reset = 0;
    I2S1.conf.tx_reset = 0;

    I2S1.conf2.val = 0;
    I2S1.conf2.lcd_en = 1;
    I2S1.conf2.lcd_tx_wrx2_en = 1;
    I2S1.conf2.lcd_tx_sdx2_en = 0;

    I2S1.sample_rate_conf.val = 0;
    I2S1.sample_rate_conf.rx_bits_mod = 8;
    I2S1.sample_rate_conf.tx_bits_mod = 8;
    I2S1.sample_rate_conf.rx_bck_div_num = 2;
    I2S1.sample_rate_conf.tx_bck_div_num = 2;

    I2S1.clkm_conf.val = 0;
    I2S1.clkm_conf.clka_en = 0;
    I2S1.clkm_conf.clkm_div_b = 0;
    I2S1.clkm_conf.clkm_div_a = 1;
    I2S1.clkm_conf.clkm_div_num = I2S_CLOCK_DIVIDER;

    I2S1.fifo_conf.val = 0;
    I2S1.fifo_conf.rx_fifo_mod_force_en = 1;
    I2S1.fifo_conf.tx_fifo_mod_force_en = 1;
    I2S1.fifo_conf.tx_fifo_mod = 1; // 0A0B_0C0D packing, dual mono single data
    I2S1.fifo_conf.rx_data_num = 1;
    I2S1.fifo_conf.tx_data_num = 1;
    I2S1.fifo_conf.dscr_en = 1;

    I2S1.conf1.val = 0;
    I2S1.conf1.tx_stop_en = 0;
    I2S1.conf1.tx_pcm_bypass = 1;

    I2S1.conf_chan.val = 0;
    I2S1.conf_chan.tx_chan_mod = 1;
    I2S1.conf_chan.rx_chan_mod = 1;

    I2S1.conf.tx_right_first = 0;
    I2S1.conf.rx_right_first = 0;

    I2S1.timing.val = 0;

    // One hardcoded row's worth of bytes (width/8, matching epd_fill_screen's
    // width>>3 CL-pulse count) -- alternating pattern so every data line toggles at
    // least once per row on the analyzer capture. Must be internal RAM: classic-ESP32
    // I2S DMA cannot reach PSRAM directly (step 9 needs a per-row copy out of the PSRAM
    // framebuffer for this reason).
    size_t row_len = cfg->width >> 3;
    row_buf = heap_caps_malloc(row_len, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    for (size_t i = 0; i < row_len; i++) {
        row_buf[i] = (i & 1) ? 0xAA : 0x55;
    }

    row_desc.size = row_len;
    row_desc.length = row_len;
    row_desc.offset = 0;
    row_desc.sosf = 0;
    row_desc.eof = 1;
    row_desc.owner = 1;
    row_desc.buf = row_buf;
    row_desc.qe.stqe_next = NULL;
}

void epd_i2s_spike_send_row(const board_config_t *cfg)
{
    fast_pin_t sph = resolve_pin(cfg->pin_sph);

    I2S1.out_link.stop = 1;
    I2S1.out_link.start = 0;
    I2S1.conf.tx_start = 0;

    I2S1.conf.tx_fifo_reset = 1;
    I2S1.conf.tx_fifo_reset = 0;

    I2S1.lc_conf.out_rst = 1;
    I2S1.lc_conf.out_rst = 0;

    I2S1.conf.tx_reset = 1;
    I2S1.conf.tx_reset = 0;

    I2S1.lc_conf.val = I2S_OUT_DATA_BURST_EN | I2S_OUTDSCR_BURST_EN;
    I2S1.out_link.addr = ((uint32_t)&row_desc) & 0x000FFFFF;

    I2S1.out_link.start = 1;

    // CKV is left as-is here (already high, held by epd_vscan_start/epd_vscan_write --
    // see epd_bitbang.c) -- only frame the data shift with SPH, matching how
    // epd_fill_screen keeps CKV constant across a row's data shift and only pulses it
    // at the latch/advance step, not per data transfer.
    fast_pin_clear(sph); // start pushing data into the row

    I2S1.conf.tx_start = 1;

    while (!I2S1.int_raw.out_total_eof)
        ;

    fast_pin_set(sph);

    I2S1.int_clr.val = I2S1.int_raw.val;
    I2S1.out_link.stop = 1;
    I2S1.out_link.start = 0;
}

// Settle-delay experiment (30us, then 1000us/row) showed no change in the frame-tail
// white band -- ruled out as a per-row timing margin issue. Reference Arduino driver
// (UtilI2S/EPDDriver) never does a single raw pass either -- every real update repeats
// the full vscan_start->rows->vscan_end cycle 4-18x per waveform phase with
// GLUT-encoded data, not one pass of raw bytes. Back to 0 here; repetition is now
// driven by the caller (see i2s_spike_test.py), not this delay.
#define ROW_SETTLE_DELAY_US 0

void epd_i2s_spike_send_frame(const board_config_t *cfg)
{
    epd_vscan_start(cfg);
    for (uint16_t row = 0; row < cfg->height; row++) {
        epd_i2s_spike_send_row(cfg);
        epd_vscan_write(cfg); // latches row, advances CKV to the next one
        esp_rom_delay_us(ROW_SETTLE_DELAY_US);
    }
    epd_vscan_end(cfg);
}
