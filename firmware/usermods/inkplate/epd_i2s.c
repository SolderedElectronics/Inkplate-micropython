#include "epd_i2s.h"

#include "epd_bitbang.h"
#include "driver/gpio.h"
#include "driver/periph_ctrl.h"
#include "esp_heap_caps.h"
#include "esp_rom_gpio.h"
#include "soc/gpio_sig_map.h"
#include "soc/gpio_struct.h"
#include "soc/i2s_reg.h"
#include "soc/i2s_struct.h"
#include "rom/lldesc.h"
#include <string.h>

// I2S1, not I2S0 -- I2S0 doesn't support 8-bit parallel/LCD mode on classic ESP32 (see
// epd_i2s_spike.c's history in git log for how this was confirmed against the Arduino
// reference driver in step 8).
// Placeholder from reference driver default; retune once waveform timing is confirmed on
// the logic analyzer.
#define I2S_CLOCK_DIVIDER 5

// Local fast-pin helper, same as epd_bitbang.c's -- kept local rather than shared for
// now (two ~15-line copies, not worth a shared header yet).
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

// Two internal-RAM (DMA-capable) row buffers, ping-ponged across rows. Classic-ESP32
// I2S DMA cannot reach PSRAM directly, so these stay small (width>>3 bytes) and fixed
// in internal RAM regardless of how large a future PSRAM-backed frame buffer gets.
typedef struct {
    uint8_t *buf[2];
    lldesc_t desc[2];
    size_t row_len;
    int in_flight; // index of the buffer with a DMA transfer currently running, -1 if none
} epd_i2s_state_t;

static epd_i2s_state_t s_state = {.in_flight = -1};

void epd_i2s_init(const board_config_t *cfg)
{
    // Wire D0-D7 -> I2S1 data-out signals, CL -> I2S1 BCK-out, straight 1:1 per
    // data_pins[i] -- confirmed sufficient (no byte2gpio remap needed) on real hardware
    // in step 8's spike.
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

    s_state.row_len = board_config_row_bytes(cfg);
    for (int i = 0; i < 2; i++) {
        s_state.buf[i] = heap_caps_malloc(s_state.row_len, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);

        s_state.desc[i].size = s_state.row_len;
        s_state.desc[i].length = s_state.row_len;
        s_state.desc[i].offset = 0;
        s_state.desc[i].sosf = 0;
        s_state.desc[i].eof = 1;
        s_state.desc[i].owner = 1;
        s_state.desc[i].buf = s_state.buf[i];
        s_state.desc[i].qe.stqe_next = NULL;
    }
    s_state.in_flight = -1;
}

void epd_i2s_deinit(const board_config_t *cfg)
{
    // Undo the matrix routing from epd_i2s_init() so epd_bitbang.c's direct GPIO writes
    // reach these pins again.
    for (int i = 0; i < 8; i++) {
        esp_rom_gpio_connect_out_signal(cfg->data_pins[i], SIG_GPIO_OUT_IDX, false, false);
    }
    esp_rom_gpio_connect_out_signal(cfg->pin_cl, SIG_GPIO_OUT_IDX, false, false);

    periph_module_disable(PERIPH_I2S1_MODULE);

    for (int i = 0; i < 2; i++) {
        if (s_state.buf[i] != NULL) {
            heap_caps_free(s_state.buf[i]);
            s_state.buf[i] = NULL;
        }
    }
    s_state.in_flight = -1;
}

// Kicks off a DMA transfer of s_state.buf[idx]/desc[idx] and returns immediately --
// does not wait for completion. SPH is dropped here (data starts shifting in) and only
// raised once epd_i2s_wait_row() observes the transfer has finished.
static void epd_i2s_start_row(const board_config_t *cfg, uint8_t idx)
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
    I2S1.out_link.addr = ((uint32_t)&s_state.desc[idx]) & 0x000FFFFF;
    I2S1.out_link.start = 1;

    // CKV is left as-is here (already high, held by epd_vscan_start/epd_vscan_write --
    // see epd_bitbang.c) -- only frame the data shift with SPH.
    fast_pin_clear(sph);
    I2S1.conf.tx_start = 1;

    s_state.in_flight = idx;
}

// Blocks until the in-flight transfer started by epd_i2s_start_row() completes, raises
// SPH, and leaves the I2S link stopped so the next epd_i2s_start_row() call can reset it.
static void epd_i2s_wait_row(const board_config_t *cfg)
{
    fast_pin_t sph = resolve_pin(cfg->pin_sph);

    while (!I2S1.int_raw.out_total_eof)
        ;
    fast_pin_set(sph);

    I2S1.int_clr.val = I2S1.int_raw.val;
    I2S1.out_link.stop = 1;
    I2S1.out_link.start = 0;
    s_state.in_flight = -1;
}

void epd_i2s_push_row(const board_config_t *cfg, uint8_t fill_byte)
{
    memset(s_state.buf[0], fill_byte, s_state.row_len);
    epd_i2s_start_row(cfg, 0);
    epd_i2s_wait_row(cfg);
}

void epd_i2s_push_frame(const board_config_t *cfg, uint8_t fill_byte)
{
    epd_vscan_start(cfg);

    memset(s_state.buf[0], fill_byte, s_state.row_len);
    uint8_t cur = 0;
    epd_i2s_start_row(cfg, cur);

    for (uint16_t row = 0; row < cfg->height; row++) {
        uint8_t next = cur ^ 1;
        if (row + 1 < cfg->height) {
            // Prepare the next row's buffer while this row's transfer is still running.
            // With today's constant fill_byte this is a redundant memset (both buffers
            // already hold the same bytes) -- it's the overlap window Phase 4's real
            // per-row waveform/LUT computation will use instead, without needing to
            // restructure this loop.
            memset(s_state.buf[next], fill_byte, s_state.row_len);
        }
        epd_i2s_wait_row(cfg);
        epd_vscan_write(cfg); // latches this row, advances CKV
        if (row + 1 < cfg->height) {
            epd_i2s_start_row(cfg, next);
        }
        cur = next;
    }

    epd_vscan_end(cfg);
}

// Rebuilds one framebuf row into row_buf as 2-bit wire codes for the given phase's LUT.
// Walks framebuf bytes from the end of the row, two at a time, and -- critically --
// emits the EARLIER byte of each pair before the LATER one (dram2 before dram1, in the
// naming of the Arduino Inkplate6 I2S reference driver's display1b(), which does the
// same swap). This is NOT a plain last-to-first walk (that's what the bit-bang
// _send_row used, correctly, since it writes one GPIO register per byte with no FIFO
// involved). I2S1's fifo_conf.tx_fifo_mod = 1 ("0A0B_0C0D packing, dual mono single
// data", see epd_i2s_init) reorders byte-pairs internally when reading the DMA buffer,
// so the source pair must be pre-swapped to compensate -- confirmed against the real
// Arduino driver after a plain reverse walk produced a visible column shift on real
// hardware with non-uniform content (invisible with epd_i2s_push_frame's constant
// fill_byte, since swapping two identical bytes is a no-op).
static void build_mono_row(const uint8_t *framebuf_row, uint16_t fb_row_bytes,
                           const uint8_t lut[16], uint8_t *row_buf)
{
    uint16_t out = 0;
    for (int16_t i = (int16_t)fb_row_bytes - 1; i > 0; i -= 2) {
        uint8_t dram1 = framebuf_row[i];     // later byte
        uint8_t dram2 = framebuf_row[i - 1]; // earlier byte
        row_buf[out++] = lut[dram2 >> 4];
        row_buf[out++] = lut[dram2 & 0x0F];
        row_buf[out++] = lut[dram1 >> 4];
        row_buf[out++] = lut[dram1 & 0x0F];
    }
}

void epd_i2s_push_mono_frame(const board_config_t *cfg, const uint8_t *framebuf,
                             const uint8_t (*luts)[16], uint8_t num_phases)
{
    uint16_t fb_row_bytes = cfg->width >> 3;

    for (uint8_t phase = 0; phase < num_phases; phase++) {
        const uint8_t *lut = luts[phase];
        epd_vscan_start(cfg);

        uint8_t cur = 0;
        int32_t row = (int32_t)cfg->height - 1;
        build_mono_row(framebuf + row * fb_row_bytes, fb_row_bytes, lut, s_state.buf[cur]);
        epd_i2s_start_row(cfg, cur);

        while (row >= 0) {
            uint8_t next = cur ^ 1;
            if (row > 0) {
                build_mono_row(framebuf + (row - 1) * fb_row_bytes, fb_row_bytes, lut,
                               s_state.buf[next]);
            }
            epd_i2s_wait_row(cfg);
            epd_vscan_write(cfg);
            if (row > 0) {
                epd_i2s_start_row(cfg, next);
            }
            cur = next;
            row--;
        }

        epd_vscan_end(cfg);
    }
}

// GS2's row is 2 bits/pixel packed 4-per-byte (GS2_HMSB), same as the wire format itself
// -- unlike mono, one framebuf byte maps to exactly one output byte (no 1:4 expansion).
// I2S1's fifo_conf.tx_fifo_mod=1 reordering was confirmed (by cross-referencing the real
// Arduino Inkplate6 I2S driver's display1b()/display3b(), Inkplate6Driver.cpp) to swap
// the first half against the second half of every 4-output-byte chunk -- this is what
// build_mono_row's dram2-before-dram1 pattern reduces to (its 4-output chunk is one
// input-byte-pair's 2+2 nibble codes). GS2 has no nibble split (1 input byte = 1 output
// byte), so the same chunk-of-4 half-swap applies directly to input bytes instead: for
// descending block {i, i-1, i-2, i-3}, transmit codes in order i-2, i-3, i, i-1. Requires
// fb_row_bytes % 4 == 0 (true for every board on docs/REFACTOR-PLAN.md: 300/200/320/256).
static void build_gs_row(const uint8_t *framebuf_row, uint16_t fb_row_bytes,
                         const uint8_t lut[16], uint8_t *row_buf)
{
    uint16_t out = 0;
    for (int32_t i = (int32_t)fb_row_bytes - 1; i >= 3; i -= 4) {
        uint8_t b0 = framebuf_row[i]; // highest index in this 4-block
        uint8_t b1 = framebuf_row[i - 1];
        uint8_t b2 = framebuf_row[i - 2];
        uint8_t b3 = framebuf_row[i - 3]; // lowest index in this 4-block
        row_buf[out++] = (uint8_t)((lut[b2 >> 4] << 4) | lut[b2 & 0x0F]);
        row_buf[out++] = (uint8_t)((lut[b3 >> 4] << 4) | lut[b3 & 0x0F]);
        row_buf[out++] = (uint8_t)((lut[b0 >> 4] << 4) | lut[b0 & 0x0F]);
        row_buf[out++] = (uint8_t)((lut[b1 >> 4] << 4) | lut[b1 & 0x0F]);
    }
}

void epd_i2s_push_gs_frame(const board_config_t *cfg, const uint8_t *framebuf,
                           const uint8_t (*luts)[16], uint8_t num_phases)
{
    uint16_t fb_row_bytes = cfg->width >> 2;

    for (uint8_t phase = 0; phase < num_phases; phase++) {
        const uint8_t *lut = luts[phase];
        epd_vscan_start(cfg);

        uint8_t cur = 0;
        int32_t row = (int32_t)cfg->height - 1;
        build_gs_row(framebuf + row * fb_row_bytes, fb_row_bytes, lut, s_state.buf[cur]);
        epd_i2s_start_row(cfg, cur);

        while (row >= 0) {
            uint8_t next = cur ^ 1;
            if (row > 0) {
                build_gs_row(framebuf + (row - 1) * fb_row_bytes, fb_row_bytes, lut,
                             s_state.buf[next]);
            }
            epd_i2s_wait_row(cfg);
            epd_vscan_write(cfg);
            if (row > 0) {
                epd_i2s_start_row(cfg, next);
            }
            cur = next;
            row--;
        }

        epd_vscan_end(cfg);
    }
}
