// Generic SPI transport for the SPI-controller-panel family (docs/REFACTOR-PLAN.md
// Phase 9 step 30). Shared by every single-chip panel in this family (Inkplate6COLOR
// now, Inkplate2 later) -- only spi_panel_config_t's pin/timing/resolution values differ
// per board, the transport itself (reset/command/data framing) is identical because
// every panel in this family uses the same CS+DC-framed SPI protocol shape.
//
// Inkplate13SPECTRA (2 SPI-controller chips, one per panel half) is NOT supported by
// this file yet -- every function here assumes spi_panel_config_t.chip_count == 1.
// Wiring a second chip needs a second CS line selected per half-frame, deferred to a
// later pass rather than guessed here (docs/REFACTOR-PLAN.md Phase 9 step 31).
#ifndef INKPLATE_EPD_SPI_H
#define INKPLATE_EPD_SPI_H

#include "spi_panel_config.h"
#include <stddef.h>
#include <stdint.h>

// One-time SPI peripheral (VSPI/SPI3_HOST) + GPIO setup (RST/DC/CS as outputs, BUSY as
// input) for the given panel. Call once before any other epd_spi_* call.
void epd_spi_init(const spi_panel_config_t *cfg);

// Tears down the SPI peripheral/device claimed by epd_spi_init.
void epd_spi_deinit(const spi_panel_config_t *cfg);

// Hardware reset pulse: RST low, then high -- matches the real Arduino reference
// driver's resetPanel() (1ms low, 200ms recovery before the panel's BUSY line is
// trusted).
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

#endif // INKPLATE_EPD_SPI_H
