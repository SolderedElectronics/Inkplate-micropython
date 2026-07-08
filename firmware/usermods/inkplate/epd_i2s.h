// Real I2S1 parallel-transport component (Phase 3 step 9 of docs/REFACTOR-PLAN.md).
// Replaces the throwaway epd_i2s_spike.{h,c} (deleted -- see that file's own header for
// what it proved: GPIO-matrix routing needs no byte2gpio remap, confirmed on real
// hardware in step 8). Config-driven, double-buffered: two internal-RAM DMA buffers
// alternate so the next row can be prepared (memset today, real waveform/LUT output
// once Phase 4 lands) while the previous row's DMA transfer is still in flight.
//
// Note: with today's fill-byte-only content (same byte repeated on every row), there is
// nothing to gain from overlap -- both buffers hold identical bytes. The point of
// building the ping-pong pipeline now is so Phase 4 can drop real per-row computation
// into epd_i2s_push_frame()'s row loop without restructuring the transfer/latch
// sequencing, which is fixed by hardware (a row's DMA transfer must complete and be
// latched via epd_vscan_write() before the next row's transfer can start -- the shift
// register and data lines are shared, so this part can never be pipelined, only the
// CPU-side row-content prep can).
#ifndef INKPLATE_EPD_I2S_H
#define INKPLATE_EPD_I2S_H

#include "board_config.h"
#include <stdint.h>

// One-time I2S1 peripheral setup + GPIO matrix wiring (data_pins[0..7] -> I2S1
// DATA_OUT0..7, pin_cl -> I2S1 BCK_OUT) for the given board, plus the two internal-RAM
// DMA row buffers (sized board_config_row_bytes(cfg) bytes each). Call once before any
// push_row/push_frame call for this board.
void epd_i2s_init(const board_config_t *cfg);

// Reconnects data_pins[0..7]/pin_cl back to plain GPIO output (undoes the matrix
// routing from epd_i2s_init) and tears down the I2S1 peripheral + DMA buffers, so
// epd_bitbang.c's bit-bang path is usable again afterward.
void epd_i2s_deinit(const board_config_t *cfg);

// Sends one row (width>>3 bytes, all set to fill_byte) via I2S1 DMA, framed by SPH
// (clear before the transfer, set after) -- blocks until the transfer completes.
// Standalone single-row primitive for HIL/logic-analyzer checks; epd_i2s_push_frame()
// below doesn't call this directly, it inlines the same start/wait sequence so it can
// overlap the next row's buffer prep with the current row's transfer.
void epd_i2s_push_row(const board_config_t *cfg, uint8_t fill_byte);

// Full-frame send: epd_vscan_start(), then per row -- start this row's DMA transfer,
// prepare the *other* buffer for the next row while this one is in flight, wait for
// this row's transfer to finish, epd_vscan_write() (latch + advance CKV) -- then
// epd_vscan_end(). Same fill_byte on every row (matches epd_fill_screen's contract) for
// the Phase 3 HIL check against Phase 2's bit-bang fill_screen.
void epd_i2s_push_frame(const board_config_t *cfg, uint8_t fill_byte);

// Full 1bpp display update: drives num_phases phases (see waveform.h's
// inkplate_gen_mono_wave), each phase writing every row via I2S DMA, framed by
// epd_vscan_start/epd_vscan_write/epd_vscan_end -- the DMA-driven equivalent of
// InkplateMono.display()'s per-phase bit-banged loop, replacing _send_row(). framebuf
// is the 1bpp MONO_HMSB source buffer (cfg->height rows of cfg->width>>3 bytes each,
// MSB-first). Each row is rebuilt last-byte-first, high-nibble-first -- the same shift
// order _send_row used -- so the physical pixel-to-shift-register mapping stays
// identical to the already-hardware-verified bit-bang path.
void epd_i2s_push_mono_frame(const board_config_t *cfg, const uint8_t *framebuf,
                             const uint8_t (*luts)[16], uint8_t num_phases);

// Full grayscale display update: drives num_phases phases (see waveform.h's
// inkplate_gen_wave_2bit / cfg->waveform), each phase writing every row via I2S DMA,
// framed by epd_vscan_start/epd_vscan_write/epd_vscan_end -- the DMA-driven equivalent of
// InkplateGS2.display()'s per-phase bit-banged loop, replacing _send_row(). framebuf is
// the GS4_HMSB source buffer (cfg->height rows of cfg->width>>1 bytes each, 2 pixels/byte,
// raw levels 0-7 -- Phase 5 step 14's 8-level-ready storage). Each row is folded down to
// the legacy 4-level GS2_HMSB shape (gs_pack.h, raw>>1) before the same last-byte-first
// chunk-of-4 half-swap epd_i2s.c's build_gs_row already applies -- interim until step 15
// wires the real 8-level waveform table in and this fold is replaced with direct 4bpp
// handling.
void epd_i2s_push_gs_frame(const board_config_t *cfg, const uint8_t *framebuf,
                           const uint8_t (*luts)[16], uint8_t num_phases);

#endif // INKPLATE_EPD_I2S_H
