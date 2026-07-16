#include "epd_i2s.h"

#include "sdkconfig.h"

// This whole file only applies to classic ESP32 -- its I2S1.out_link/lc_conf/etc fields
// are the legacy descriptor-linked-list DMA register layout, which ESP32-S3 dropped in
// favor of GDMA (its i2s_dev_t has no out_link/lc_conf/conf/conf1/conf2/conf_chan/
// sample_rate_conf/clkm_conf/timing members at all -- confirmed the hard way: this file
// failed to compile at all for Inkplate13SPECTRA's ESP32-S3 target, discovered on its
// first real firmware build attempt, docs/REFACTOR-PLAN.md Phase 9 step 31). No board in
// this family that ships on ESP32-S3 (Inkplate13SPECTRA) uses the parallel-bus I2S
// transport at all -- it's SPI-only -- so on that target these functions are simply never
// called; stub them out rather than porting classic-ESP32-only DMA register code to
// hardware that doesn't have it.
#if CONFIG_IDF_TARGET_ESP32

#include "epd_bitbang.h"
#include "driver/gpio.h"
#include "esp_heap_caps.h"
#include "esp_private/periph_ctrl.h"
#include "esp_rom_gpio.h"
#include "esp_rom_sys.h"
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
    fast_pin_t sph = epd_resolve_pin(cfg->pin_sph);

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
    epd_fast_pin_clear(sph);
    I2S1.conf.tx_start = 1;

    s_state.in_flight = idx;
}

// Blocks until the in-flight transfer started by epd_i2s_start_row() completes, raises
// SPH, and leaves the I2S link stopped so the next epd_i2s_start_row() call can reset it.
static void epd_i2s_wait_row(const board_config_t *cfg)
{
    fast_pin_t sph = epd_resolve_pin(cfg->pin_sph);

    while (!I2S1.int_raw.out_total_eof)
        ;
    epd_fast_pin_set(sph);

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

// Rebuilds one row's diff between old_fb and new_fb into row_buf as 2-bit wire codes,
// via `lut` (epd_partial_lut.h's inkplate_gen_partial_diff_lut). Same byte-pair swap as
// build_mono_row (earlier byte's pair emitted first) for the same I2S1
// fifo_conf.tx_fifo_mod=1 reason -- this function differs from build_mono_row only in
// that each output byte comes from combining an (old,new) nibble pair through `lut`
// instead of looking a single framebuf nibble up in a 16-entry table.
static void build_partial_row(const uint8_t *old_row, const uint8_t *new_row,
                              uint16_t fb_row_bytes, const uint8_t lut[256], uint8_t *row_buf)
{
    uint16_t out = 0;
    for (int16_t i = (int16_t)fb_row_bytes - 1; i > 0; i -= 2) {
        uint8_t old1 = old_row[i]; // later byte
        uint8_t new1 = new_row[i];
        uint8_t old2 = old_row[i - 1]; // earlier byte
        uint8_t new2 = new_row[i - 1];
        row_buf[out++] = lut[((old2 & 0xF0) | (new2 >> 4))];
        row_buf[out++] = lut[((old2 & 0x0F) << 4) | (new2 & 0x0F)];
        row_buf[out++] = lut[((old1 & 0xF0) | (new1 >> 4))];
        row_buf[out++] = lut[((old1 & 0x0F) << 4) | (new1 & 0x0F)];
    }
}

void epd_i2s_push_partial_frame(const board_config_t *cfg, const uint8_t *old_fb,
                                const uint8_t *new_fb, const uint8_t lut[256])
{
    uint16_t fb_row_bytes = cfg->width >> 3;

    for (uint8_t rep = 0; rep < cfg->partial_reps; rep++) {
        epd_vscan_start(cfg);

        uint8_t cur = 0;
        int32_t row = (int32_t)cfg->height - 1;
        build_partial_row(old_fb + row * fb_row_bytes, new_fb + row * fb_row_bytes, fb_row_bytes,
                          lut, s_state.buf[cur]);
        epd_i2s_start_row(cfg, cur);

        while (row >= 0) {
            uint8_t next = cur ^ 1;
            if (row > 0) {
                build_partial_row(old_fb + (row - 1) * fb_row_bytes,
                                  new_fb + (row - 1) * fb_row_bytes, fb_row_bytes, lut,
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
        // Matches the real Arduino partialUpdate()'s inter-repeat gap.
        esp_rom_delay_us(230);
    }
}

// Combines 2 native GS4_HMSB bytes (4 raw-0..7 pixels) into 1 wire/output byte of four
// 2-bit op-codes, using lut[16] from inkplate_gen_wave_3bit (lut[nibble] = op-code for
// that raw pixel value, entries 8-15 unused). Bit layout matches the real Arduino driver's
// calculateLUTs()/GLUT|GLUT2 combine (Inkplate10Driver.cpp), which assigns by pixel
// *position* (even-x/left vs odd-x/right within a byte), not by nibble literally -- this
// project's write_pixel_viper (inkplate10.py) packs the opposite nibble convention from
// Arduino's DMemory4Bit (even-x -> low nibble here, vs. high nibble there), so the
// low/high nibble reads below are swapped relative to a literal port of the Arduino
// formula, to land the correct *pixel* in the position Arduino's bit-scatter expects.
// byte1 (first/higher-address byte consumed) lands in the output's upper nibble (its
// odd-x/right pixel in bits 7:6, even-x/left pixel in bits 5:4), byte2 (second/lower-
// address byte) lands in the lower nibble (bits 3:2 / 1:0) the same way. The first,
// unswapped version of this function produced a one-pixel shift at every gray-level
// boundary in an 8-bar ramp on real hardware (invisible inside a solid-color bar, since
// swapping two equal values is a no-op) -- this swap fixes that; pending re-verification
// on the panel.
static inline uint8_t gs3_combine(const uint8_t lut[16], uint8_t byte1, uint8_t byte2)
{
    return (uint8_t)((lut[(byte1 >> 4) & 0x0F] << 6) | (lut[byte1 & 0x0F] << 4) |
                     (lut[(byte2 >> 4) & 0x0F] << 2) | lut[byte2 & 0x0F]);
}

// Native 3-bit/8-level row builder (docs/REFACTOR-PLAN.md Phase 5 step 15), replacing the
// interim GS4->GS2 fold (gs_pack.h, deleted). Reads the GS4_HMSB framebuf row directly, no
// intermediate 4-level shape.
//
// Byte ordering: gs3_combine() reproduces the Arduino driver's electrically-correct
// per-row op-code sequence (bit-banged, no FIFO involved on that hardware). Our transport
// is I2S1 DMA with fifo_conf.tx_fifo_mod=1, which reorders every 4 consecutive *output*
// bytes as [pos2,pos3,pos0,pos1] on the wire (confirmed empirically for build_mono_row and
// the now-removed build_gs_row against real hardware) -- so the 4 "logical"
// (Arduino-equivalent) combined bytes per chunk are written pre-swapped into row_buf here,
// same rule, applied one level up (per-combined-byte instead of per-input-byte, since
// gs3_combine already reduces 2 input bytes to 1 logical output byte, same shape
// build_gs_row's input was in). Requires gs4_row_bytes % 8 == 0 (true for Inkplate10:
// 1200>>1 = 600).
//
// UNVERIFIED on real hardware: every prior swap rule in this driver needed a HIL
// correction the first time non-uniform content exercised it (see build_mono_row's and
// the removed build_gs_row's history) -- this is a reasoned derivation, not yet confirmed
// against a real gray ramp on the panel.
static void build_gs3_row(const uint8_t *gs4_row, uint16_t gs4_row_bytes, const uint8_t lut[16],
                          uint8_t *row_buf)
{
    uint16_t out = 0;
    for (int32_t i = (int32_t)gs4_row_bytes - 1; i >= 7; i -= 8) {
        uint8_t l0 = gs3_combine(lut, gs4_row[i], gs4_row[i - 1]);
        uint8_t l1 = gs3_combine(lut, gs4_row[i - 2], gs4_row[i - 3]);
        uint8_t l2 = gs3_combine(lut, gs4_row[i - 4], gs4_row[i - 5]);
        uint8_t l3 = gs3_combine(lut, gs4_row[i - 6], gs4_row[i - 7]);
        row_buf[out++] = l2;
        row_buf[out++] = l3;
        row_buf[out++] = l0;
        row_buf[out++] = l1;
    }
}

void epd_i2s_push_gs_frame(const board_config_t *cfg, const uint8_t *framebuf,
                           const uint8_t (*luts)[16], uint8_t num_phases)
{
    uint16_t gs4_row_bytes = cfg->width >> 1; // GS4_HMSB framebuf row bytes (2 px/byte)

    for (uint8_t phase = 0; phase < num_phases; phase++) {
        const uint8_t *lut = luts[phase];
        epd_vscan_start(cfg);

        uint8_t cur = 0;
        int32_t row = (int32_t)cfg->height - 1;
        build_gs3_row(framebuf + row * gs4_row_bytes, gs4_row_bytes, lut, s_state.buf[cur]);
        epd_i2s_start_row(cfg, cur);

        while (row >= 0) {
            uint8_t next = cur ^ 1;
            if (row > 0) {
                build_gs3_row(framebuf + (row - 1) * gs4_row_bytes, gs4_row_bytes, lut,
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
        // Matches the real Arduino display3b()'s inter-phase gap (Inkplate10Driver.cpp).
        esp_rom_delay_us(230);
    }
}

#else // !CONFIG_IDF_TARGET_ESP32

// Unreachable on this target: no ESP32-S3 board in this repo selects a parallel-bus
// board_config_t (select_board()), so nothing ever calls these. Bodies exist purely so
// the usermod still links -- see this file's top comment.
void epd_i2s_init(const board_config_t *cfg)
{
    (void)cfg;
}

void epd_i2s_deinit(const board_config_t *cfg)
{
    (void)cfg;
}

void epd_i2s_push_row(const board_config_t *cfg, uint8_t fill_byte)
{
    (void)cfg;
    (void)fill_byte;
}

void epd_i2s_push_frame(const board_config_t *cfg, uint8_t fill_byte)
{
    (void)cfg;
    (void)fill_byte;
}

void epd_i2s_push_mono_frame(const board_config_t *cfg, const uint8_t *framebuf,
                             const uint8_t (*luts)[16], uint8_t num_phases)
{
    (void)cfg;
    (void)framebuf;
    (void)luts;
    (void)num_phases;
}

void epd_i2s_push_gs_frame(const board_config_t *cfg, const uint8_t *framebuf,
                           const uint8_t (*luts)[16], uint8_t num_phases)
{
    (void)cfg;
    (void)framebuf;
    (void)luts;
    (void)num_phases;
}

void epd_i2s_push_partial_frame(const board_config_t *cfg, const uint8_t *old_fb,
                                const uint8_t *new_fb, const uint8_t lut[256])
{
    (void)cfg;
    (void)old_fb;
    (void)new_fb;
    (void)lut;
}

#endif // CONFIG_IDF_TARGET_ESP32
