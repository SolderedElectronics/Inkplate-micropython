/**
 * @file epd_spi.h
 * @brief Generic SPI transport shared by every single-chip panel in this family
 *        (Inkplate6COLOR, Inkplate2).
 *
 * Only spi_panel_config_t's pin/timing/resolution values differ per board; the
 * transport itself (reset/command/data framing) is identical because every panel in
 * this family uses the same CS+DC-framed SPI protocol shape.
 *
 * Inkplate13SPECTRA (2 SPI-controller chips, one per panel half) does NOT use the
 * functions below except epd_spi_reset/epd_spi_set_rst/epd_spi_wait_busy (RST/BUSY are
 * single shared lines, the framing is identical either way). Its own protocol has no DC
 * phase at all and needs a per-call chip selection (master/slave/both), so it gets its
 * own epd_spi_dual_* functions further down rather than being force-fit onto
 * epd_spi_send_command/send_data's DC-framed shape.
 */
#ifndef INKPLATE_EPD_SPI_H
#define INKPLATE_EPD_SPI_H

#include "spi_panel_config.h"
#include <stddef.h>
#include <stdint.h>

/**
 * @brief One-time SPI peripheral (VSPI/SPI3_HOST) and GPIO setup (RST/DC/CS as outputs,
 * BUSY as pulled-up input) for the given panel. Call once before any other epd_spi_*
 * call.
 * @param cfg Panel pin/timing/resolution configuration.
 */
void epd_spi_init(const spi_panel_config_t *cfg);

/**
 * @brief Tears down the SPI peripheral/device claimed by epd_spi_init.
 * @param cfg Panel configuration (unused beyond call symmetry with epd_spi_init).
 */
void epd_spi_deinit(const spi_panel_config_t *cfg);

/**
 * @brief Hardware reset pulse: RST low, then high -- 100ms low pulse, 200ms recovery
 * before the panel's BUSY line is trusted. The 100ms low pulse covers Inkplate2, which
 * requires it; Inkplate6COLOR only needs 1ms but a longer pulse doesn't hurt it. The
 * 200ms recovery is already above both panels' requirements.
 * @param cfg Panel configuration providing pin_rst.
 */
void epd_spi_reset(const spi_panel_config_t *cfg);

/**
 * @brief Directly drives RST -- used to hold it low while the panel is in deep sleep,
 * which saves power versus leaving it floating/high. Not needed for the normal
 * reset/wake path, which is epd_spi_reset() above.
 * @param cfg Panel configuration providing pin_rst.
 * @param level 0 to hold RST low, 1 to release it.
 */
void epd_spi_set_rst(const spi_panel_config_t *cfg, int level);

/**
 * @brief Blocks until BUSY reads `level`, or timeout_ms elapses. timeout_ms == 0 waits
 * forever, matching long operations (e.g. display()/clean()) that have no timeout --
 * only init/wake paths use a bounded timeout.
 * @param cfg Panel configuration providing pin_busy.
 * @param level Target BUSY level to wait for (0 or 1).
 * @param timeout_ms Maximum time to wait in milliseconds; 0 waits forever.
 * @return 1 if the level was observed, 0 on timeout -- callers should treat 0 as an
 * init/wake failure.
 */
int epd_spi_wait_busy(const spi_panel_config_t *cfg, int level, uint32_t timeout_ms);

/**
 * @brief Sends a single command byte: CS low, DC low, a 10us settle delay, transfer the
 * byte, CS high, then a 1ms settle delay. Delays are explicit since C has no implicit
 * pacing to rely on for SPI timing margin.
 * @param cfg Panel configuration providing pin_cs/pin_dc.
 * @param command Command byte to send.
 */
void epd_spi_send_command(const spi_panel_config_t *cfg, uint8_t command);

/**
 * @brief Sends a data payload (register data, or a full framebuffer): CS low, DC high, a
 * 10us settle delay, transfer len bytes, CS high, then a 1ms settle delay -- same
 * framing/delay rationale as epd_spi_send_command(). The 1ms trailing delay is negligible
 * next to a multi-KB framebuffer transfer.
 * @param cfg Panel configuration providing pin_cs/pin_dc.
 * @param data Bytes to send.
 * @param len Number of bytes in data.
 */
void epd_spi_send_data(const spi_panel_config_t *cfg, const uint8_t *data, size_t len);

// --- Inkplate13SPECTRA dual-chip transport ---
// Only valid when cfg->chip_count == 2. epd_spi_reset/epd_spi_set_rst/epd_spi_wait_busy
// above are reused unchanged (RST/BUSY are single shared lines on this panel too).

// Chip-select target for the two-chip panel's per-command addressing. Both CS lines
// share the same SCK/MOSI, so asserting both together (BOTH = MASTER|SLAVE) clocks
// identical bytes into both chips at once.
typedef enum {
    EPD_SPI_CHIP_MASTER = 1,
    EPD_SPI_CHIP_SLAVE = 2,
    EPD_SPI_CHIP_BOTH = 3,
} epd_spi_chip_t;

/**
 * @brief Drives DC/CS(both)/RST/BUSY/PWR_EN/BS0/BS1 all low as GPIO outputs. Discharges
 * the panel's input capacitors before a power-state transition -- skipping this can make
 * the panel refuse to refresh.
 * @param cfg Panel configuration providing the dual-chip transport pins.
 */
void epd_spi_dual_pins_low(const spi_panel_config_t *cfg);

/**
 * @brief Configures pins to their functional power-on modes (DC/CS_M/CS_S/RST/PWR_EN/
 * BS0/BS1 as outputs at their idle levels, BUSY as pulled-up input) and (re)initializes
 * the SPI bus+device at cfg->spi_freq_hz. Runs once per display()-triggered power cycle,
 * not just once at boot, so it tears down a previously-added device/bus first to stay
 * idempotent.
 * @param cfg Panel configuration providing the dual-chip transport pins and spi_freq_hz.
 */
void epd_spi_dual_power_up_io(const spi_panel_config_t *cfg);

/**
 * @brief Floats DC/CS_M/CS_S/RST/BUSY/PWR_EN (GPIO input, no pull) to save power. BS0/BS1
 * are deliberately left untouched (still driven from the last power_up_io() call) --
 * they're an interface-select strap, not part of the power sequence.
 * @param cfg Panel configuration providing the dual-chip transport pins.
 */
void epd_spi_dual_power_down_io(const spi_panel_config_t *cfg);

/**
 * @brief Drives PWR_EN directly -- used to bracket the reset/init sequence on power-up
 * and the tail of the power-down sequence.
 * @param cfg Panel configuration providing pin_pwr_en.
 * @param level 0 or 1, the level to drive PWR_EN to.
 */
void epd_spi_dual_set_power(const spi_panel_config_t *cfg, int level);

/**
 * @brief Asserts CS for the chip(s) in chip_mask -- slave then master. Both lines share
 * SCK/MOSI so the order only affects oscilloscope-level timing, not correctness; kept
 * fixed for consistency with epd_spi_dual_deselect.
 * @param cfg Panel configuration providing pin_cs/pin_cs2.
 * @param chip_mask Bitmask of epd_spi_chip_t values (MASTER, SLAVE, or BOTH).
 */
void epd_spi_dual_select(const spi_panel_config_t *cfg, int chip_mask);

/**
 * @brief Releases CS for the chip(s) in chip_mask -- same slave-then-master order as
 * epd_spi_dual_select.
 * @param cfg Panel configuration providing pin_cs/pin_cs2.
 * @param chip_mask Bitmask of epd_spi_chip_t values (MASTER, SLAVE, or BOTH).
 */
void epd_spi_dual_deselect(const spi_panel_config_t *cfg, int chip_mask);

/**
 * @brief Raw SPI write with no CS/DC framing of its own -- the caller brackets one or
 * more of these calls with epd_spi_dual_select/deselect, allowing one CS-low window to
 * contain several back-to-back writes. Chunks payloads larger than the SPI driver's
 * per-transaction limit the same way epd_spi_send_data does.
 * @param data Bytes to write.
 * @param len Number of bytes in data.
 */
void epd_spi_dual_write(const uint8_t *data, size_t len);

#endif // INKPLATE_EPD_SPI_H
