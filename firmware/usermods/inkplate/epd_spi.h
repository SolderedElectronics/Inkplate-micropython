// Generic SPI transport for the SPI-controller-panel family (docs/REFACTOR-PLAN.md
// Phase 9 step 30). Shared by every single-chip panel in this family (Inkplate6COLOR,
// Inkplate2) -- only spi_panel_config_t's pin/timing/resolution values differ per board,
// the transport itself (reset/command/data framing) is identical because every panel in
// this family uses the same CS+DC-framed SPI protocol shape.
//
// Inkplate13SPECTRA (2 SPI-controller chips, one per panel half) does NOT use the
// functions below except epd_spi_reset/epd_spi_set_rst/epd_spi_wait_busy (RST/BUSY are
// single shared lines, the framing is identical either way). Its own protocol has no DC
// phase at all (confirmed against the real Arduino reference driver -- sendCommand()
// never touches DC) and needs a per-call chip selection (master/slave/both), so it gets
// its own epd_spi_dual_* functions further down rather than being force-fit onto
// epd_spi_send_command/send_data's DC-framed shape (docs/REFACTOR-PLAN.md Phase 9 step 31).
#ifndef INKPLATE_EPD_SPI_H
#define INKPLATE_EPD_SPI_H

#include "spi_panel_config.h"
#include <stddef.h>
#include <stdint.h>

// One-time SPI peripheral (VSPI/SPI3_HOST) + GPIO setup (RST/DC/CS as outputs, BUSY as
// pulled-up input -- matches Inkplate2's real Arduino reference driver's
// INPUT_PULLUP) for the given panel. Call once before any other epd_spi_* call.
void epd_spi_init(const spi_panel_config_t *cfg);

// Tears down the SPI peripheral/device claimed by epd_spi_init.
void epd_spi_deinit(const spi_panel_config_t *cfg);

// Hardware reset pulse: RST low, then high -- 100ms low pulse, 200ms recovery before
// the panel's BUSY line is trusted. Matches Inkplate2's real Arduino reference driver's
// resetPanel() (100ms low, 100ms recovery) -- bumped up from this function's original
// 1ms low pulse (calibrated only against Inkplate6COLOR's own resetPanel() spec,
// docs/REFACTOR-PLAN.md Phase 9 step 30) since a longer low pulse can't hurt a panel
// that only needed 1ms, but 1ms could plausibly be too short for one (Inkplate2) whose
// own spec asks for 100ms. Recovery delay kept at 200ms (already >= both panels'
// real specs) rather than also raised, since neither reference driver asks for more.
// Not independently re-verified via HIL on Inkplate6COLOR after this change -- flag if
// regression suspected there.
void epd_spi_reset(const spi_panel_config_t *cfg);

// Directly drives RST -- used to hold it low while the panel is in deep sleep (matches
// the real Arduino reference driver's setPanelDeepSleep(true), which leaves RST asserted
// low rather than floating/high while asleep to save power). Not needed for the normal
// reset/wake path, which is epd_spi_reset() above.
void epd_spi_set_rst(const spi_panel_config_t *cfg, int level);

// Blocks until BUSY reads `level`, or timeout_ms elapses; timeout_ms == 0 means wait
// forever (matches the real Arduino reference driver's display()/clean(), which busy-
// wait with no timeout -- only the init/wake paths use a bounded timeout). Returns 1 if
// the level was observed, 0 on timeout -- callers should treat 0 as an init/wake
// failure, same as the existing Python driver's timeout loops.
int epd_spi_wait_busy(const spi_panel_config_t *cfg, int level, uint32_t timeout_ms);

// Sends a single command byte: CS low, DC low, a 10us settle delay, transfer the byte,
// CS high, then a 1ms settle delay -- transcribed from the real Arduino reference
// driver's sendCommand(), which the pre-refactor MicroPython driver's Python-interpreter
// call overhead had been standing in for (no explicit delay in that version). Restoring
// the explicit delays here follows this project's own established lesson from porting
// the parallel-bus bit-bang path (docs/REFACTOR-PLAN.md Phase 2 step 7): C is fast enough
// that timing margin Python used to provide "for free" must be made explicit, not
// dropped.
void epd_spi_send_command(const spi_panel_config_t *cfg, uint8_t command);

// Sends a data payload (register data, or a full framebuffer): CS low, DC high, a 10us
// settle delay, transfer len bytes, CS high, then a 1ms settle delay -- same framing/
// delay rationale as epd_spi_send_command(). Used for both short register-data writes
// and the one large per-display() framebuffer write (the real hot path this port is
// for); the 1ms trailing delay is negligible next to a multi-KB transfer.
void epd_spi_send_data(const spi_panel_config_t *cfg, const uint8_t *data, size_t len);

// --- Inkplate13SPECTRA dual-chip transport (docs/REFACTOR-PLAN.md Phase 9 step 31) ---
// Only valid when cfg->chip_count == 2. epd_spi_reset/epd_spi_set_rst/epd_spi_wait_busy
// above are reused unchanged (RST/BUSY are single shared lines on this panel too).

// Chip-select target for the two-chip panel's per-command addressing -- mirrors the real
// Arduino reference driver's eChipIdMaster/eChipIdSlave/eChipIdBoth bitmask exactly (both
// CS lines share the same SCK/MOSI, so asserting both together clocks identical bytes
// into both chips at once -- this is how "send to both" works).
typedef enum {
    EPD_SPI_CHIP_MASTER = 1,
    EPD_SPI_CHIP_SLAVE = 2,
    EPD_SPI_CHIP_BOTH = 3,
} epd_spi_chip_t;

// Drives DC/CS(both)/RST/BUSY/PWR_EN/BS0/BS1 all low as GPIO outputs -- matches the real
// Arduino reference driver's setPanelPinsToLow(), which discharges the panel's input
// capacitors before every power-state transition (its own comment: "without this
// sometimes the panel refuses to refresh").
void epd_spi_dual_pins_low(const spi_panel_config_t *cfg);

// Configures pins to their functional power-on modes (DC/CS_M/CS_S/RST/PWR_EN/BS0/BS1 as
// outputs at the reference driver's setIO() idle levels, BUSY as pulled-up input) and
// (re)initializes the SPI bus+device at cfg->spi_freq_hz. Matches the reference driver's
// setIO(), which reconstructs its SPI object on every power-on -- idempotent here (tears
// down a previously-added device/bus first) since this runs once per display()-triggered
// power cycle, not just once at boot.
void epd_spi_dual_power_up_io(const spi_panel_config_t *cfg);

// Floats DC/CS_M/CS_S/RST/BUSY/PWR_EN (GPIO input, no pull) to save power -- matches the
// reference driver's setPanelState(false) pin-float step. BS0/BS1 are deliberately left
// untouched (still driven from the last power_up_io() call), matching the reference,
// which never touches them on power-down -- they're an interface-select strap, not part
// of the power sequence.
void epd_spi_dual_power_down_io(const spi_panel_config_t *cfg);

// Drives PWR_EN directly -- matches the reference driver's digitalWrite(PWR_EN, ...)
// calls bracketing the reset/init sequence in setPanelState(true) and the power-down tail
// of setPanelState(false).
void epd_spi_dual_set_power(const spi_panel_config_t *cfg, int level);

// Asserts CS for the chip(s) in chip_mask -- slave then master, matching the real Arduino
// reference driver's sendCommand() assert order exactly (both lines share SCK/MOSI, so
// order only matters for oscilloscope-level timing, not correctness, but this is ported
// byte-for-byte rather than reordered).
void epd_spi_dual_select(const spi_panel_config_t *cfg, int chip_mask);

// Releases CS for the chip(s) in chip_mask -- same slave-then-master order as
// epd_spi_dual_select, matching the reference driver's release order.
void epd_spi_dual_deselect(const spi_panel_config_t *cfg, int chip_mask);

// Raw SPI write with no CS/DC framing of its own -- the caller brackets one or more of
// these calls with epd_spi_dual_select/deselect (this is how the reference driver's
// sendCommand() and display()'s per-row framebuffer loop both work: one CS-low window,
// several back-to-back SPI.write()/writeBytes() calls inside it). Chunks payloads larger
// than the SPI driver's per-transaction limit the same way epd_spi_send_data does.
void epd_spi_dual_write(const uint8_t *data, size_t len);

#endif // INKPLATE_EPD_SPI_H
