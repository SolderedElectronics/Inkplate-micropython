/**
 * @file epd_i2s.h
 * @brief Real I2S1 parallel-transport component.
 *
 * Config-driven, double-buffered: two internal-RAM DMA buffers alternate so the next
 * row's content can be prepared while the previous row's DMA transfer is still in
 * flight. The transfer/latch sequencing is fixed by hardware -- a row's DMA transfer
 * must complete and be latched via epd_vscan_write() before the next row's transfer can
 * start, since the shift register and data lines are shared -- so only the CPU-side
 * row-content prep can overlap, never the transfers themselves. This buffering lets
 * per-row waveform/LUT computation be dropped into the row loop later without
 * restructuring that sequencing.
 */
#ifndef INKPLATE_EPD_I2S_H
#define INKPLATE_EPD_I2S_H

#include "board_config.h"
#include <stdint.h>

/**
 * @brief Performs one-time I2S1 peripheral setup, GPIO-matrix wiring, and DMA row-buffer allocation.
 *
 * Wires data_pins[0..7] to I2S1 DATA_OUT0..7 and pin_cl to I2S1 BCK_OUT, and allocates the
 * two internal-RAM DMA row buffers (sized to board_config_row_bytes(cfg) bytes each). Call
 * once before any push_row/push_frame call for this board.
 * @param cfg Board configuration to initialize I2S1 for.
 */
void epd_i2s_init(const board_config_t *cfg);

/**
 * @brief Reconnects data pins to plain GPIO output and tears down the I2S1 peripheral and DMA buffers.
 *
 * Undoes the GPIO-matrix routing from epd_i2s_init() so epd_control.c's bit-bang path is
 * usable again afterward.
 * @param cfg Board configuration whose data_pins[0..7] and pin_cl are restored to GPIO mode.
 */
void epd_i2s_deinit(const board_config_t *cfg);

/**
 * @brief Sends one row of fill_byte bytes via I2S1 DMA, framed by SPH; blocks until complete.
 *
 * Standalone single-row primitive for logic-analyzer checks; epd_i2s_push_frame() does not
 * call this directly, it inlines the same start/wait sequence so it can overlap the next
 * row's buffer prep with the current row's transfer.
 * @param cfg Board configuration; determines row length (width>>3 bytes).
 * @param fill_byte Byte value written to every byte of the row.
 */
void epd_i2s_push_row(const board_config_t *cfg, uint8_t fill_byte);

/**
 * @brief Sends a full frame with the same fill_byte on every row, via double-buffered I2S1 DMA.
 *
 * Per row: starts this row's DMA transfer, prepares the other buffer for the next row while
 * this one is in flight, waits for the transfer to finish, then epd_vscan_write() latches it
 * and advances CKV. Same fill_byte on every row matches epd_fill_screen's contract.
 * @param cfg Board configuration.
 * @param fill_byte Byte value written to every row of the frame.
 */
void epd_i2s_push_frame(const board_config_t *cfg, uint8_t fill_byte);

/**
 * @brief Drives a full 1bpp mono display update over num_phases waveform phases via I2S1 DMA.
 *
 * Each phase writes every row, framed by epd_vscan_start/epd_vscan_write/epd_vscan_end. Each
 * row is rebuilt last-byte-first, high-nibble-first, matching the bit-bang path's shift order
 * so the physical pixel-to-shift-register mapping stays identical.
 * @param cfg Board configuration.
 * @param framebuf 1bpp MONO_HMSB source buffer: cfg->height rows of cfg->width>>3 bytes each, MSB-first.
 * @param luts Per-phase LUT table; luts[phase] is a 16-entry nibble-to-wire-code lookup (see
 *             waveform.h's inkplate_gen_mono_wave).
 * @param num_phases Number of waveform phases to drive.
 */
void epd_i2s_push_mono_frame(const board_config_t *cfg, const uint8_t *framebuf,
                             const uint8_t (*luts)[16], uint8_t num_phases);

/**
 * @brief Drives a full grayscale display update over num_phases waveform phases via I2S1 DMA.
 *
 * Each phase writes every row, framed by epd_vscan_start/epd_vscan_write/epd_vscan_end, with
 * a 230us gap after each phase. Reads the GS4_HMSB framebuf directly (native 3-bit/8-level,
 * no intermediate fold).
 * @param cfg Board configuration.
 * @param framebuf GS4_HMSB source buffer: cfg->height rows of cfg->width>>1 bytes each, 2
 *                 pixels/byte, raw levels 0-7.
 * @param luts Per-phase LUT table; luts[phase] is a 16-entry nibble-to-wire-code lookup (see
 *             waveform.h's inkplate_gen_wave_3bit / cfg->waveform).
 * @param num_phases Number of waveform phases to drive.
 */
void epd_i2s_push_gs_frame(const board_config_t *cfg, const uint8_t *framebuf,
                           const uint8_t (*luts)[16], uint8_t num_phases);

/**
 * @brief Sends a mono partial-update frame: diffs old_fb against new_fb and pushes the
 *        result over I2S1 DMA cfg->partial_reps times.
 *
 * Sends the same wire codes on every repeat -- a fixed pulse train, not a multi-phase
 * waveform -- with a 230us gap after each repeat. Each row's diff is recomputed from
 * old_fb/new_fb on the fly per repeat rather than built once into a precomputed buffer.
 * @param cfg Board configuration.
 * @param old_fb Previous 1bpp MONO_HMSB framebuffer (same layout as epd_i2s_push_mono_frame's framebuf).
 * @param new_fb New 1bpp MONO_HMSB framebuffer to diff against old_fb.
 * @param lut 256-entry diff lookup table, indexed by (old_nibble<<4|new_nibble) (see
 *            epd_partial_lut.h's inkplate_gen_partial_diff_lut).
 */
void epd_i2s_push_partial_frame(const board_config_t *cfg, const uint8_t *old_fb,
                                const uint8_t *new_fb, const uint8_t lut[256]);

#endif // INKPLATE_EPD_I2S_H
