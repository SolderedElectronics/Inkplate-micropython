// Throwaway Phase 3 de-risking spike (docs/REFACTOR-PLAN.md step 8): pushes one
// hardcoded row of data out over I2S1 DMA instead of bit-banging CL, framed by manual
// SPH/CKV pulses (ported from the Arduino reference driver's UtilI2S::I2SInit/
// sendDataI2S) plus the existing Phase 2 epd_vscan_start/write/end for SPV/LE/CKV frame
// context. Only proves the panel accepts I2S-driven data -- not meant to survive past
// the logic-analyzer verification step; step 9's real inkplate_i2s component replaces
// this entirely (double-buffered, PSRAM-aware, N rows/frame instead of one hardcoded row).
#ifndef INKPLATE_EPD_I2S_SPIKE_H
#define INKPLATE_EPD_I2S_SPIKE_H

#include "board_config.h"

// One-time I2S1 peripheral setup + GPIO matrix wiring (data_pins[0..7] -> I2S1 DATA_OUT0..7,
// pin_cl -> I2S1 BCK_OUT) for the given board. Call once before epd_i2s_spike_send_row().
void epd_i2s_spike_init(const board_config_t *cfg);

// Sends one hardcoded row (alternating byte pattern, width/8 bytes) via I2S1 DMA, framed
// by SPH_CLEAR before the transfer and SPH_SET after (matches sendDataI2S's SPH framing;
// CKV is left to the caller -- see epd_i2s_spike_send_frame()). Caller wraps a single
// call with epd_vscan_start()/epd_vscan_end() from epd_bitbang.h for a logic-analyzer
// capture of one row's waveform.
void epd_i2s_spike_send_row(const board_config_t *cfg);

// Full-frame visual check: epd_vscan_start(), then epd_i2s_spike_send_row() +
// epd_vscan_write() (latch + advance CKV) per row, then epd_vscan_end(). Same hardcoded
// pattern on every row -- comparable to Phase 2's epd_fill_screen, but data now shifted
// in via I2S DMA instead of bit-banged CL. Confirms I2S-driven data actually reaches the
// panel, visible on real hardware without a logic analyzer.
void epd_i2s_spike_send_frame(const board_config_t *cfg);

#endif // INKPLATE_EPD_I2S_SPIKE_H
