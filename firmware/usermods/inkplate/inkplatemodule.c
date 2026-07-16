#include "py/runtime.h"
#include "py/obj.h"
#include "display/expander_bridge.h"
#include "display/board_config.h"
#include "display/epd_control.h"
#include "display/epd_i2s.h"
#include "display/epd_partial_lut.h"
#include "display/waveform.h"
#include "display/gfx.h"
#include "image/jpeg_draw.h"
#include "image/png_draw.h"
#include "image/bmp_draw.h"
#include "display/spi_panel_config.h"
#include "image/spi_panel_palette.h"
#include "display/epd_spi.h"
#include <stdbool.h>
#include <string.h>

static mp_obj_t inkplate_version(void)
{
    return mp_obj_new_str("0.0.1", 5);
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_version_obj, inkplate_version);

// Registers the Python callable used to reach PCAL6416A-controlled lines.
// See expander_bridge.h for why the I2C transaction itself stays in Python.
static mp_obj_t inkplate_set_expander_write_cb(mp_obj_t cb)
{
    expander_bridge_set_callback(cb);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_set_expander_write_cb_obj,
                                 inkplate_set_expander_write_cb);

// HIL test hook: toggles one expander pin through the bridge.
// Use an unused/free expander pin for verification — OE/GMODE/SPV are wired to the
// panel and can't be probed directly (see docs/REFACTOR-PLAN.md Phase 1 step 6).
static mp_obj_t inkplate_test_expander_write(mp_obj_t addr, mp_obj_t pin, mp_obj_t value)
{
    expander_bridge_write(mp_obj_get_int(addr), mp_obj_get_int(pin), mp_obj_get_int(value));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(inkplate_test_expander_write_obj, inkplate_test_expander_write);

// Active board, set once via select_board() before any epd_* call. mp function arity
// is fixed, so board_config_t* can't be threaded through the Python-facing calls the
// way it is through the C-internal epd_control API -- this is the one place that holds
// it as static state instead.
static const board_config_t *active_board = NULL;

static mp_obj_t inkplate_select_board(mp_obj_t name_obj)
{
    const char *name = mp_obj_str_get_str(name_obj);
    if (strcmp(name, "inkplate10v1") == 0) {
        active_board = &board_config_inkplate10v1;
    } else if (strcmp(name, "inkplate10v2") == 0) {
        active_board = &board_config_inkplate10v2;
    } else if (strcmp(name, "inkplate6v1") == 0) {
        active_board = &board_config_inkplate6v1;
    } else if (strcmp(name, "inkplate6v2") == 0) {
        active_board = &board_config_inkplate6v2;
    } else if (strcmp(name, "inkplate5v2") == 0) {
        active_board = &board_config_inkplate5v2;
    } else if (strcmp(name, "inkplate6flick") == 0) {
        active_board = &board_config_inkplate6flick;
    } else if (strcmp(name, "inkplate6plusv2") == 0) {
        active_board = &board_config_inkplate6plusv2;
    } else if (strcmp(name, "inkplate4tempera") == 0) {
        active_board = &board_config_inkplate4tempera;
    } else {
        mp_raise_ValueError(MP_ERROR_TEXT("unknown board"));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_select_board_obj, inkplate_select_board);

static const board_config_t *require_board(void)
{
    if (active_board == NULL) {
        mp_raise_msg(&mp_type_RuntimeError,
                     MP_ERROR_TEXT("no board selected, call select_board() first"));
    }
    return active_board;
}

static mp_obj_t inkplate_vscan_start(void)
{
    epd_vscan_start(require_board());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_vscan_start_obj, inkplate_vscan_start);

static mp_obj_t inkplate_vscan_write(void)
{
    epd_vscan_write(require_board());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_vscan_write_obj, inkplate_vscan_write);

static mp_obj_t inkplate_vscan_end(void)
{
    epd_vscan_end(require_board());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_vscan_end_obj, inkplate_vscan_end);

static mp_obj_t inkplate_fill_screen(mp_obj_t data_obj)
{
    epd_fill_screen(require_board(), (uint32_t)mp_obj_get_int_truncated(data_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_fill_screen_obj, inkplate_fill_screen);

static mp_obj_t inkplate_i2s_init(void)
{
    epd_i2s_init(require_board());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_i2s_init_obj, inkplate_i2s_init);

static mp_obj_t inkplate_i2s_deinit(void)
{
    epd_i2s_deinit(require_board());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_i2s_deinit_obj, inkplate_i2s_deinit);

static mp_obj_t inkplate_i2s_push_row(mp_obj_t fill_byte_obj)
{
    epd_i2s_push_row(require_board(), (uint8_t)mp_obj_get_int(fill_byte_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_i2s_push_row_obj, inkplate_i2s_push_row);

static mp_obj_t inkplate_i2s_push_frame(mp_obj_t fill_byte_obj)
{
    epd_i2s_push_frame(require_board(), (uint8_t)mp_obj_get_int(fill_byte_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_i2s_push_frame_obj, inkplate_i2s_push_frame);

static mp_obj_t inkplate_mono_display(mp_obj_t framebuf_obj)
{
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(framebuf_obj, &bufinfo, MP_BUFFER_READ);

    const board_config_t *cfg = require_board();
    if (bufinfo.len < (size_t)cfg->height * (size_t)(cfg->width >> 3)) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuf too small for this board's mono resolution"));
    }

    // Inkplate6FLICK's Arduino reference driver (display1b()) uses 4 black-push phases
    // instead of the 5 every other wired board uses, followed by its own discharge pass
    // (pushed separately from Python via clean(2, ...)/i2s_push_frame(0), matching the
    // Arduino driver's discharge loop) -- see docs/REFACTOR-PLAN.md Phase 8 step 24.
    // Regenerated per call (board never changes after select_board(), and the LUT gen
    // itself is a handful of nibble-lookup loops -- not worth caching across boards).
    uint8_t mono_luts[INKPLATE_MONO_WAVE_MAX_PHASES][16];
    uint8_t num_phases;

    if (cfg == &board_config_inkplate6plusv2) {
        // Inkplate6PLUSV2's real display1b() also loops for(k<4), but HIL testing (a
        // uniformly dark/washed panel, unchanged by bumping the repeat count to 5) plus
        // decoding this board's own GraphicsDefs.h LUTW/LUTB against its ~dram/dram
        // indexing scheme showed its phase *roles* are the mirror image of every other
        // wired board's: repeated phases push white (black skips), one final phase pushes
        // black (white skips) -- the opposite of inkplate_gen_mono_wave's scheme. Confirmed
        // NOT a generic-engine bug (Inkplate6/10/5v2/6FLICK are independently HIL-verified
        // correct on the original scheme) -- scoped to this board only via
        // inkplate_gen_mono_wave_white_first (waveform.c).
        uint8_t repeat_phases = 4;
        inkplate_gen_mono_wave_white_first(repeat_phases, mono_luts);
        num_phases = repeat_phases + 1;
    } else {
        // Inkplate4TEMPERA's real display1b() uses 10 black-push phases, not the usual 5
        // -- confirmed NOT a copy-paste artifact: its own GraphicsDefs.h LUTB/LUT2 arrays
        // are byte-for-byte identical to this function's standard op_blk/op_bw output
        // (test_waveform.c's expected_blk/expected_bw), so it's the standard scheme run
        // 10 times, not a reversed-role variant like Inkplate6PLUSV2 (docs/REFACTOR-PLAN.md
        // Phase 8 step 26).
        uint8_t black_phases = (cfg == &board_config_inkplate6flick)     ? 4
                               : (cfg == &board_config_inkplate4tempera) ? 10
                                                                         : 5;
        inkplate_gen_mono_wave(black_phases, mono_luts);
        num_phases = black_phases + 1;
    }

    epd_i2s_push_mono_frame(cfg, (const uint8_t *)bufinfo.buf, mono_luts, num_phases);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_mono_display_obj, inkplate_mono_display);

static mp_obj_t inkplate_gs_display(mp_obj_t framebuf_obj)
{
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(framebuf_obj, &bufinfo, MP_BUFFER_READ);

    const board_config_t *cfg = require_board();
    if (bufinfo.len < (size_t)cfg->height * (size_t)(cfg->width >> 1)) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuf too small for this board's GS4 resolution"));
    }

    // Keyed by which board's waveform generated it, not just a ready flag -- cfg->waveform
    // is board-specific, so a stale cache would silently serve one board's LUTs to another
    // if select_board() is ever called again with a different board mid-process (unlike
    // partial_lut below, whose LUT is genuinely board-independent, this one isn't).
    static uint8_t gs_luts[MAX_WAVE_PHASES][16];
    static const board_config_t *gs_luts_board = NULL;
    if (gs_luts_board != cfg) {
        inkplate_gen_wave_3bit(&cfg->waveform->table[0][0], MAX_WAVE_LEVELS,
                               cfg->waveform->phases, gs_luts);
        gs_luts_board = cfg;
    }

    epd_i2s_push_gs_frame(cfg, (const uint8_t *)bufinfo.buf, gs_luts, cfg->waveform->phases);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_gs_display_obj, inkplate_gs_display);

// spi_panel_* bindings (docs/REFACTOR-PLAN.md Phase 9 steps 30-31): the SPI-controller-
// panel family (Inkplate6COLOR, Inkplate2 now, Inkplate13SPECTRA later) is
// architecturally separate from the parallel-bus board_config_t/active_board above -- a
// different static selection slot, mirroring the same select-once-then-call-by-name
// pattern.
static const spi_panel_config_t *active_spi_panel = NULL;

static mp_obj_t inkplate_select_spi_panel(mp_obj_t name_obj)
{
    const char *name = mp_obj_str_get_str(name_obj);
    if (strcmp(name, "inkplate6color") == 0) {
        active_spi_panel = &spi_panel_config_inkplate6color;
    } else if (strcmp(name, "inkplate2") == 0) {
        active_spi_panel = &spi_panel_config_inkplate2;
    } else if (strcmp(name, "inkplate13spectra") == 0) {
        active_spi_panel = &spi_panel_config_inkplate13spectra;
    } else {
        mp_raise_ValueError(MP_ERROR_TEXT("unknown spi panel"));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_select_spi_panel_obj, inkplate_select_spi_panel);

static const spi_panel_config_t *require_spi_panel(void)
{
    if (active_spi_panel == NULL) {
        mp_raise_msg(&mp_type_RuntimeError,
                     MP_ERROR_TEXT("no spi panel selected, call select_spi_panel() first"));
    }
    return active_spi_panel;
}

static mp_obj_t inkplate_spi_panel_init(void)
{
    epd_spi_init(require_spi_panel());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_spi_panel_init_obj, inkplate_spi_panel_init);

static mp_obj_t inkplate_spi_panel_deinit(void)
{
    epd_spi_deinit(require_spi_panel());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_spi_panel_deinit_obj, inkplate_spi_panel_deinit);

static mp_obj_t inkplate_spi_panel_reset(void)
{
    epd_spi_reset(require_spi_panel());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_spi_panel_reset_obj, inkplate_spi_panel_reset);

static mp_obj_t inkplate_spi_panel_set_rst(mp_obj_t level_obj)
{
    epd_spi_set_rst(require_spi_panel(), mp_obj_get_int(level_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_panel_set_rst_obj, inkplate_spi_panel_set_rst);

static mp_obj_t inkplate_spi_panel_wait_busy(mp_obj_t level_obj, mp_obj_t timeout_ms_obj)
{
    int observed = epd_spi_wait_busy(require_spi_panel(), mp_obj_get_int(level_obj),
                                     (uint32_t)mp_obj_get_int(timeout_ms_obj));
    return mp_obj_new_bool(observed);
}
static MP_DEFINE_CONST_FUN_OBJ_2(inkplate_spi_panel_wait_busy_obj, inkplate_spi_panel_wait_busy);

static mp_obj_t inkplate_spi_panel_send_command(mp_obj_t command_obj)
{
    epd_spi_send_command(require_spi_panel(), (uint8_t)mp_obj_get_int(command_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_panel_send_command_obj,
                                 inkplate_spi_panel_send_command);

static mp_obj_t inkplate_spi_panel_send_data(mp_obj_t data_obj)
{
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(data_obj, &bufinfo, MP_BUFFER_READ);
    epd_spi_send_data(require_spi_panel(), (const uint8_t *)bufinfo.buf, bufinfo.len);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_panel_send_data_obj, inkplate_spi_panel_send_data);

// spi_dual_* bindings (docs/REFACTOR-PLAN.md Phase 9 step 31): Inkplate13SPECTRA's
// dual-SPI-controller-chip transport -- distinct from the spi_panel_* bindings above
// because this panel's protocol has no DC phase and needs a per-call chip selection
// (master/slave/both), see epd_spi.h's own comment on why it isn't force-fit onto
// epd_spi_send_command/send_data. Still goes through the same active_spi_panel/
// require_spi_panel() selection slot as spi_panel_* above -- select_spi_panel() is shared.

static mp_obj_t inkplate_spi_dual_pins_low(void)
{
    epd_spi_dual_pins_low(require_spi_panel());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_spi_dual_pins_low_obj, inkplate_spi_dual_pins_low);

static mp_obj_t inkplate_spi_dual_power_up_io(void)
{
    epd_spi_dual_power_up_io(require_spi_panel());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_spi_dual_power_up_io_obj,
                                 inkplate_spi_dual_power_up_io);

static mp_obj_t inkplate_spi_dual_power_down_io(void)
{
    epd_spi_dual_power_down_io(require_spi_panel());
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_spi_dual_power_down_io_obj,
                                 inkplate_spi_dual_power_down_io);

static mp_obj_t inkplate_spi_dual_set_power(mp_obj_t level_obj)
{
    epd_spi_dual_set_power(require_spi_panel(), mp_obj_get_int(level_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_dual_set_power_obj, inkplate_spi_dual_set_power);

static mp_obj_t inkplate_spi_dual_select(mp_obj_t mask_obj)
{
    epd_spi_dual_select(require_spi_panel(), mp_obj_get_int(mask_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_dual_select_obj, inkplate_spi_dual_select);

static mp_obj_t inkplate_spi_dual_deselect(mp_obj_t mask_obj)
{
    epd_spi_dual_deselect(require_spi_panel(), mp_obj_get_int(mask_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_dual_deselect_obj, inkplate_spi_dual_deselect);

static mp_obj_t inkplate_spi_dual_write(mp_obj_t data_obj)
{
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(data_obj, &bufinfo, MP_BUFFER_READ);
    epd_spi_dual_write((const uint8_t *)bufinfo.buf, bufinfo.len);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_spi_dual_write_obj, inkplate_spi_dual_write);

static mp_obj_t inkplate_partial_display(mp_obj_t old_fb_obj, mp_obj_t new_fb_obj)
{
    mp_buffer_info_t old_info, new_info;
    mp_get_buffer_raise(old_fb_obj, &old_info, MP_BUFFER_READ);
    mp_get_buffer_raise(new_fb_obj, &new_info, MP_BUFFER_READ);

    const board_config_t *cfg = require_board();
    size_t partial_needed = (size_t)cfg->height * (size_t)(cfg->width >> 3);
    if (old_info.len < partial_needed || new_info.len < partial_needed) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuf too small for this board's mono resolution"));
    }

    static uint8_t partial_lut[256];
    static bool partial_lut_ready = false;
    if (!partial_lut_ready) {
        inkplate_gen_partial_diff_lut(partial_lut);
        partial_lut_ready = true;
    }

    epd_i2s_push_partial_frame(cfg, (const uint8_t *)old_info.buf, (const uint8_t *)new_info.buf,
                               partial_lut);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(inkplate_partial_display_obj, inkplate_partial_display);

// gfx_* bindings (docs/REFACTOR-PLAN.md Phase 7 step 17): each call is self-contained --
// framebuf + phys dims + rotation + display_mode + shape params -- rather than threaded
// through static state like active_board, since rotation/display_mode/which framebuf
// genuinely vary call to call (unlike the board selection, which is a session constant).
static uint8_t *gfx_writable_buf(mp_obj_t fb_obj, mp_buffer_info_t *bufinfo)
{
    mp_get_buffer_raise(fb_obj, bufinfo, MP_BUFFER_WRITE);
    return (uint8_t *)bufinfo->buf;
}

// Minimum framebuffer bytes gfx_set_pixel's own packing needs for a phys_w x phys_h buffer
// at this display_mode. Rotation doesn't change this -- rotation only remaps logical into
// physical (px, py) coordinates (gfx.c), the buffer's own byte layout is always phys_w x
// phys_h. Mirrors gfx.c's indexing exactly: mono is 1bpp row-major (`(py*w+px)>>3`), GS4 is
// 4bpp/2px-per-byte using truncating `w/2` row stride (`py*(w/2)+(px>>1)`) -- same
// assumption every other GS4 caller in this codebase already makes about even widths, not
// a new one introduced here.
static size_t gfx_min_buf_len(int phys_w, int phys_h, int display_mode)
{
    if (phys_w <= 0 || phys_h <= 0) {
        return 0;
    }
    if (display_mode == 0) {
        return ((size_t)phys_w * (size_t)phys_h + 7) / 8;
    }
    return (size_t)phys_h * (size_t)(phys_w / 2);
}

// Same as gfx_writable_buf, but raises a clean ValueError instead of an out-of-bounds
// write/read when the caller's buffer is smaller than phys_w/phys_h/display_mode implies
// (e.g. a board/buffer size mismatch) -- every gfx_* primitive and the jpeg/png/bmp_draw_gs4
// image loaders share this same (fb, phys_w, phys_h, rotation, display_mode, ...) arg shape.
static uint8_t *gfx_writable_buf_checked(mp_obj_t fb_obj, mp_buffer_info_t *bufinfo, int phys_w,
                                         int phys_h, int display_mode)
{
    mp_get_buffer_raise(fb_obj, bufinfo, MP_BUFFER_WRITE);
    if (bufinfo->len < gfx_min_buf_len(phys_w, phys_h, display_mode)) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuf too small for phys_w/phys_h/display_mode"));
    }
    return (uint8_t *)bufinfo->buf;
}

// Validates a 1bpp source bitmap (gfx_draw_bitmap's bitmap arg, gfx_draw_char's char_data
// arg -- both row_bytes = ceil(w/8), h rows, per gfx.h's own documented format) has enough
// bytes for its own caller-supplied w/h before gfx.c walks it.
static void gfx_check_1bpp_len(const mp_buffer_info_t *bufinfo, int w, int h)
{
    if (w <= 0 || h <= 0) {
        return;
    }
    size_t needed = (size_t)((w + 7) / 8) * (size_t)h;
    if (bufinfo->len < needed) {
        mp_raise_ValueError(MP_ERROR_TEXT("bitmap buffer too small for its own w/h"));
    }
}

static mp_obj_t inkplate_gfx_set_mirror_x(mp_obj_t enable_obj)
{
    gfx_set_mirror_x(mp_obj_is_true(enable_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_gfx_set_mirror_x_obj, inkplate_gfx_set_mirror_x);

static mp_obj_t inkplate_gfx_set_gs4_nibble_swap(mp_obj_t enable_obj)
{
    gfx_set_gs4_nibble_swap(mp_obj_is_true(enable_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_gfx_set_gs4_nibble_swap_obj,
                                 inkplate_gfx_set_gs4_nibble_swap);

// args: framebuf, phys_w, phys_h, rotation, display_mode, x, y, color.
static mp_obj_t inkplate_gfx_set_pixel(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_set_pixel(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
                  phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
                  mp_obj_get_int(args[6]), mp_obj_get_int(args[7]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_set_pixel_obj, 8, 8,
                                           inkplate_gfx_set_pixel);

// args: framebuf, value. Fills the whole buffer -- length comes from the buffer itself,
// not a separate arg, so a caller can't accidentally overrun it with a mismatched size.
static mp_obj_t inkplate_gfx_buf_fill(mp_obj_t fb_obj, mp_obj_t value_obj)
{
    mp_buffer_info_t buf;
    gfx_buf_fill(gfx_writable_buf(fb_obj, &buf), (int)buf.len,
                 (uint8_t)mp_obj_get_int(value_obj));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(inkplate_gfx_buf_fill_obj, inkplate_gfx_buf_fill);

// args: framebuf, phys_w, phys_h, rotation, display_mode, x0, y0, bitmap(bytes-like), bmp_w,
// bmp_h, color.
static mp_obj_t inkplate_gfx_draw_bitmap(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf, bmp_buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    uint8_t *fb = gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode);
    mp_get_buffer_raise(args[7], &bmp_buf, MP_BUFFER_READ);
    int bmp_w = mp_obj_get_int(args[8]), bmp_h = mp_obj_get_int(args[9]);
    gfx_check_1bpp_len(&bmp_buf, bmp_w, bmp_h);

    gfx_draw_bitmap(fb, phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                    mp_obj_get_int(args[5]), mp_obj_get_int(args[6]),
                    (const uint8_t *)bmp_buf.buf, bmp_w, bmp_h, mp_obj_get_int(args[10]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_draw_bitmap_obj, 11, 11,
                                           inkplate_gfx_draw_bitmap);

static mp_obj_t inkplate_gfx_hline(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_hline(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
              phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
              mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_hline_obj, 9, 9, inkplate_gfx_hline);

static mp_obj_t inkplate_gfx_vline(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_vline(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
              phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
              mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_vline_obj, 9, 9, inkplate_gfx_vline);

static mp_obj_t inkplate_gfx_line(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_line(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
             phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
             mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
             mp_obj_get_int(args[9]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_line_obj, 10, 10, inkplate_gfx_line);

static mp_obj_t inkplate_gfx_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_rect(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
             phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
             mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
             mp_obj_get_int(args[9]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_rect_obj, 10, 10, inkplate_gfx_rect);

static mp_obj_t inkplate_gfx_fill_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_fill_rect(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
                  phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
                  mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
                  mp_obj_get_int(args[9]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_fill_rect_obj, 10, 10,
                                           inkplate_gfx_fill_rect);

static mp_obj_t inkplate_gfx_circle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_circle(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
               phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
               mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_circle_obj, 9, 9, inkplate_gfx_circle);

static mp_obj_t inkplate_gfx_fill_circle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_fill_circle(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
                    phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
                    mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_fill_circle_obj, 9, 9,
                                           inkplate_gfx_fill_circle);

static mp_obj_t inkplate_gfx_triangle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_triangle(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
                 phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
                 mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
                 mp_obj_get_int(args[9]), mp_obj_get_int(args[10]), mp_obj_get_int(args[11]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_triangle_obj, 12, 12,
                                           inkplate_gfx_triangle);

static mp_obj_t inkplate_gfx_fill_triangle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_fill_triangle(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode),
                      phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                      mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), mp_obj_get_int(args[7]),
                      mp_obj_get_int(args[8]), mp_obj_get_int(args[9]), mp_obj_get_int(args[10]),
                      mp_obj_get_int(args[11]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_fill_triangle_obj, 12, 12,
                                           inkplate_gfx_fill_triangle);

static mp_obj_t inkplate_gfx_round_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_round_rect(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode), phys_w,
                   phys_h, mp_obj_get_int(args[3]), display_mode, mp_obj_get_int(args[5]),
                   mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
                   mp_obj_get_int(args[9]), mp_obj_get_int(args[10]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_round_rect_obj, 11, 11,
                                           inkplate_gfx_round_rect);

static mp_obj_t inkplate_gfx_fill_round_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    gfx_fill_round_rect(gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode),
                        phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                        mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), mp_obj_get_int(args[7]),
                        mp_obj_get_int(args[8]), mp_obj_get_int(args[9]),
                        mp_obj_get_int(args[10]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_fill_round_rect_obj, 11, 11,
                                           inkplate_gfx_fill_round_rect);

// args: framebuf, phys_w, phys_h, rotation, display_mode, x0, y0, char_data(bytes-like),
// char_w, char_h, size, color.
static mp_obj_t inkplate_gfx_draw_char(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf, char_buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    uint8_t *fb = gfx_writable_buf_checked(args[0], &buf, phys_w, phys_h, display_mode);
    mp_get_buffer_raise(args[7], &char_buf, MP_BUFFER_READ);
    int char_w = mp_obj_get_int(args[8]), char_h = mp_obj_get_int(args[9]);
    gfx_check_1bpp_len(&char_buf, char_w, char_h);

    gfx_draw_char(fb, phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                  mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), (const uint8_t *)char_buf.buf,
                  char_w, char_h, mp_obj_get_int(args[10]), mp_obj_get_int(args[11]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_draw_char_obj, 12, 12,
                                           inkplate_gfx_draw_char);

// Decodes+draws a JPEG straight into a framebuffer, with optional scalar
// Floyd-Steinberg/JJN/Stucki/Burkes error diffusion -- see jpeg_draw.h,
// docs/REFACTOR-PLAN.md step 21. args: framebuf, phys_w, phys_h, rotation,
// display_mode, x0, y0, jpeg_bytes, invert, dither, kernel_type. Returns (width,
// height) of the decoded JPEG.
static mp_obj_t inkplate_jpeg_draw_gs4(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, jpg_buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    uint8_t *fb = gfx_writable_buf_checked(args[0], &fb_buf, phys_w, phys_h, display_mode);
    mp_get_buffer_raise(args[7], &jpg_buf, MP_BUFFER_READ);

    uint32_t width = 0, height = 0;
    int res = jpeg_draw_gs4(fb, phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                            mp_obj_get_int(args[5]), mp_obj_get_int(args[6]),
                            (const uint8_t *)jpg_buf.buf, jpg_buf.len, mp_obj_is_true(args[8]),
                            mp_obj_is_true(args[9]), mp_obj_get_int(args[10]), &width, &height);
    if (res == -2) {
        mp_raise_ValueError(MP_ERROR_TEXT("Image too wide to dither -- try a "
                                          "smaller/downscaled image, or draw with dither=False"));
    }
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("JPEG decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_jpeg_draw_gs4_obj, 11, 11,
                                           inkplate_jpeg_draw_gs4);

// Decodes+draws a PNG straight into a framebuffer, with optional scalar
// Floyd-Steinberg/JJN/Stucki/Burkes error diffusion -- see png_draw.h,
// docs/REFACTOR-PLAN.md step 21. args: framebuf, phys_w, phys_h, rotation,
// display_mode, x0, y0, png_bytes, invert, dither, kernel_type. Returns (width,
// height) of the decoded PNG.
static mp_obj_t inkplate_png_draw_gs4(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, png_buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    uint8_t *fb = gfx_writable_buf_checked(args[0], &fb_buf, phys_w, phys_h, display_mode);
    mp_get_buffer_raise(args[7], &png_buf, MP_BUFFER_READ);

    uint32_t width = 0, height = 0;
    int res = png_draw_gs4(fb, phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                           mp_obj_get_int(args[5]), mp_obj_get_int(args[6]),
                           (const uint8_t *)png_buf.buf, png_buf.len, mp_obj_is_true(args[8]),
                           mp_obj_is_true(args[9]), mp_obj_get_int(args[10]), &width, &height);
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("PNG decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_png_draw_gs4_obj, 11, 11,
                                           inkplate_png_draw_gs4);

// Decodes+draws a BMP straight into a framebuffer, with optional scalar
// Floyd-Steinberg/JJN/Stucki/Burkes error diffusion -- see bmp_draw.h,
// docs/REFACTOR-PLAN.md step 21. args: framebuf, phys_w, phys_h, rotation,
// display_mode, x0, y0, bmp_bytes, invert, dither, kernel_type. Returns (width,
// height) of the decoded BMP.
static mp_obj_t inkplate_bmp_draw_gs4(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, bmp_buf;
    int phys_w = mp_obj_get_int(args[1]), phys_h = mp_obj_get_int(args[2]);
    int display_mode = mp_obj_get_int(args[4]);
    uint8_t *fb = gfx_writable_buf_checked(args[0], &fb_buf, phys_w, phys_h, display_mode);
    mp_get_buffer_raise(args[7], &bmp_buf, MP_BUFFER_READ);

    uint32_t width = 0, height = 0;
    int res = bmp_draw_gs4(fb, phys_w, phys_h, mp_obj_get_int(args[3]), display_mode,
                           mp_obj_get_int(args[5]), mp_obj_get_int(args[6]),
                           (const uint8_t *)bmp_buf.buf, bmp_buf.len, mp_obj_is_true(args[8]),
                           mp_obj_is_true(args[9]), mp_obj_get_int(args[10]), &width, &height);
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("BMP decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_bmp_draw_gs4_obj, 11, 11,
                                           inkplate_bmp_draw_gs4);

// *_draw_palette bindings (docs/REFACTOR-PLAN.md Phase 10 steps 32-33): shared with
// the SPI color-panel family (Inkplate6COLOR/Inkplate2/Inkplate13SPECTRA), which
// panel/palette/packing to use is resolved from the already-selected
// active_spi_panel (select_spi_panel() must be called first, same as the
// spi_panel_* bindings above) rather than passed explicitly. args: framebuf,
// framebuf2 (Inkplate2's red plane, or None for the other two boards), rotation,
// x0, y0, invert, dither, kernel_type, image_bytes, and (png only) a caller-owned
// RGB565 scratch bytearray or None -- see inkplate_png_draw_palette's comment below
// for why. jpeg_draw_palette needs no such buffer (see its own comment below).
// Returns (width, height) of the decoded image.
static void inkplate_palette_ctx_init(spi_panel_palette_ctx_t *ctx, const mp_obj_t *args,
                                      mp_buffer_info_t *fb_buf, mp_buffer_info_t *fb2_buf)
{
    const spi_panel_config_t *panel = require_spi_panel();
    int panel_id = spi_panel_palette_id_for_name(panel->name);
    if (panel_id < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("no palette for this spi panel"));
    }

    ctx->panel = panel_id;
    ctx->fb = gfx_writable_buf(args[0], fb_buf);
    ctx->fb2 = (args[1] == mp_const_none) ? NULL : gfx_writable_buf(args[1], fb2_buf);
    ctx->width = panel->width;
    ctx->height = panel->height;
    ctx->rotation = mp_obj_get_int(args[2]);
    ctx->x0 = mp_obj_get_int(args[3]);
    ctx->y0 = mp_obj_get_int(args[4]);

    // spi_panel_palette_write_pixel's packing is fixed per panel (spi_panel_palette.c) --
    // validate the caller's buffer(s) actually match it, same reasoning as
    // gfx_writable_buf_checked above, instead of trusting Python to have sized them right.
    if (panel_id == SPI_PANEL_PALETTE_INKPLATE2) {
        // write_pixel_inkplate2 unconditionally dereferences both planes (ctx->fb/fb2) --
        // a None fb2 here would be a guaranteed NULL-pointer write, not just an OOB one.
        if (ctx->fb2 == NULL) {
            mp_raise_ValueError(MP_ERROR_TEXT("inkplate2 needs a red-plane framebuf, not None"));
        }
        size_t needed = (size_t)ctx->height * (size_t)(ctx->width / 8);
        if (fb_buf->len < needed || fb2_buf->len < needed) {
            mp_raise_ValueError(MP_ERROR_TEXT("framebuf too small for this panel's resolution"));
        }
    } else {
        // 6COLOR/13SPECTRA: single 4bpp nibble-packed buffer, fb2 unused regardless of
        // what the caller passed for it.
        size_t needed = (size_t)ctx->height * (size_t)(ctx->width / 2);
        if (fb_buf->len < needed) {
            mp_raise_ValueError(MP_ERROR_TEXT("framebuf too small for this panel's resolution"));
        }
    }
}

static mp_obj_t inkplate_bmp_draw_palette(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, fb2_buf, img_buf;
    spi_panel_palette_ctx_t ctx;
    inkplate_palette_ctx_init(&ctx, args, &fb_buf, &fb2_buf);

    int n = 0;
    const dither_palette_entry_t *palette = spi_panel_palette_table(ctx.panel, &n);
    mp_get_buffer_raise(args[8], &img_buf, MP_BUFFER_READ);

    uint32_t width = 0, height = 0;
    int res = bmp_draw_palette((const uint8_t *)img_buf.buf, img_buf.len, mp_obj_is_true(args[5]),
                               mp_obj_is_true(args[6]), mp_obj_get_int(args[7]), palette, n,
                               spi_panel_palette_write_pixel, &ctx, &width, &height);
    if (res == -2) {
        // Unlike jpeg/png_draw_palette's -2, this applies whether or not dither was
        // requested (bmp_draw_palette's comment) -- no point suggesting
        // dither=False here, it wouldn't help.
        mp_raise_ValueError(MP_ERROR_TEXT("Image too wide -- try a smaller/downscaled image"));
    }
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("BMP decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_bmp_draw_palette_obj, 9, 9,
                                           inkplate_bmp_draw_palette);

static mp_obj_t inkplate_jpeg_draw_palette(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, fb2_buf, img_buf;
    spi_panel_palette_ctx_t ctx;
    inkplate_palette_ctx_init(&ctx, args, &fb_buf, &fb2_buf);

    int n = 0;
    const dither_palette_entry_t *palette = spi_panel_palette_table(ctx.panel, &n);
    mp_get_buffer_raise(args[8], &img_buf, MP_BUFFER_READ);

    // jpeg_draw_palette buffers one MCU row-band at a time (a small static buffer,
    // see jpeg_draw_core.h's JPEG_DRAW_CORE_BAND_MAX_W/JPEG_DRAW_CORE_MCU_MAX_H) rather than
    // the whole image, so unlike bmp/png_draw_palette there's no panel-size-vs-
    // photo-floor cap or caller-supplied scratch buffer to compute here.
    uint32_t width = 0, height = 0;
    int res =
        jpeg_draw_palette((const uint8_t *)img_buf.buf, img_buf.len, mp_obj_is_true(args[5]),
                          mp_obj_is_true(args[6]), mp_obj_get_int(args[7]), palette, n,
                          spi_panel_palette_write_pixel, &ctx, &width, &height);
    if (res == -2) {
        mp_raise_ValueError(MP_ERROR_TEXT("Image too wide to dither -- try a "
                                          "smaller/downscaled image, or draw with dither=False"));
    }
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("JPEG decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_jpeg_draw_palette_obj, 9, 9,
                                           inkplate_jpeg_draw_palette);

static mp_obj_t inkplate_png_draw_palette(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, fb2_buf, img_buf;
    spi_panel_palette_ctx_t ctx;
    inkplate_palette_ctx_init(&ctx, args, &fb_buf, &fb2_buf);

    int n = 0;
    const dither_palette_entry_t *palette = spi_panel_palette_table(ctx.panel, &n);
    mp_get_buffer_raise(args[8], &img_buf, MP_BUFFER_READ);

    // Cap at the larger of this panel's own physical size and a "typical photo" floor
    // (INKPLATE_DRAW_MAX_WIDTH x 825, matching PNG's own buffered-path cap --
    // png_draw_core.h's PNG_DRAW_CORE_MAX_WIDTH/HEIGHT -- and JPEG's band-buffer width
    // floor, JPEG_DRAW_CORE_BAND_MAX_W -- all three now the same shared constant, see
    // dither.h) -- see png_draw_palette's own comment for why PNG (unlike
    // jpeg_draw_palette) still needs a whole-image scratch buffer at all (Adam7
    // interlacing).
    int max_w = ctx.width > INKPLATE_DRAW_MAX_WIDTH ? ctx.width : INKPLATE_DRAW_MAX_WIDTH;
    int max_h = ctx.height > 825 ? ctx.height : 825;

    // Caller (Python) allocates and owns this scratch bytearray -- see
    // png_draw_palette's own comment for why.
    mp_buffer_info_t scratch_buf;
    uint16_t *scratch_rgb = NULL;
    size_t scratch_cap = 0;
    if (args[9] != mp_const_none) {
        mp_get_buffer_raise(args[9], &scratch_buf, MP_BUFFER_WRITE);
        scratch_rgb = (uint16_t *)scratch_buf.buf;
        scratch_cap = scratch_buf.len / sizeof(uint16_t);
    }

    uint32_t width = 0, height = 0;
    int res = png_draw_palette((const uint8_t *)img_buf.buf, img_buf.len, mp_obj_is_true(args[5]),
                               mp_obj_is_true(args[6]), mp_obj_get_int(args[7]), palette, n,
                               spi_panel_palette_write_pixel, &ctx, max_w, max_h, scratch_rgb,
                               scratch_cap, &width, &height);
    if (res == -2) {
        // Only reachable for an Adam7-interlaced source (or a header peek that
        // couldn't even tell) -- the common non-interlaced case dithers inline, no
        // size cap or scratch buffer needed (png_draw.c). Board `draw_png_from_*`
        // wrappers don't pass a scratch buffer (that unconditional allocation used
        // to reliably MemoryError on real hardware for completely ordinary
        // non-interlaced photos, docs/REFACTOR-PLAN.md Phase 7 step 21's
        // follow-up), so this is effectively "this PNG is Adam7-interlaced, which
        // isn't supported for dithering right now" rather than a size complaint.
        mp_raise_ValueError(MP_ERROR_TEXT("Image can't be dithered -- too wide, or an "
                                          "Adam7-interlaced PNG -- try a smaller/non-interlaced "
                                          "image, or draw with dither=False"));
    }
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("PNG decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_png_draw_palette_obj, 10, 10,
                                           inkplate_png_draw_palette);

static const mp_rom_map_elem_t inkplate_module_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_inkplate)},
    {MP_ROM_QSTR(MP_QSTR_version), MP_ROM_PTR(&inkplate_version_obj)},
    {MP_ROM_QSTR(MP_QSTR_set_expander_write_cb), MP_ROM_PTR(&inkplate_set_expander_write_cb_obj)},
    {MP_ROM_QSTR(MP_QSTR_test_expander_write), MP_ROM_PTR(&inkplate_test_expander_write_obj)},
    {MP_ROM_QSTR(MP_QSTR_select_board), MP_ROM_PTR(&inkplate_select_board_obj)},
    {MP_ROM_QSTR(MP_QSTR_vscan_start), MP_ROM_PTR(&inkplate_vscan_start_obj)},
    {MP_ROM_QSTR(MP_QSTR_vscan_write), MP_ROM_PTR(&inkplate_vscan_write_obj)},
    {MP_ROM_QSTR(MP_QSTR_vscan_end), MP_ROM_PTR(&inkplate_vscan_end_obj)},
    {MP_ROM_QSTR(MP_QSTR_fill_screen), MP_ROM_PTR(&inkplate_fill_screen_obj)},
    {MP_ROM_QSTR(MP_QSTR_i2s_init), MP_ROM_PTR(&inkplate_i2s_init_obj)},
    {MP_ROM_QSTR(MP_QSTR_i2s_deinit), MP_ROM_PTR(&inkplate_i2s_deinit_obj)},
    {MP_ROM_QSTR(MP_QSTR_i2s_push_row), MP_ROM_PTR(&inkplate_i2s_push_row_obj)},
    {MP_ROM_QSTR(MP_QSTR_i2s_push_frame), MP_ROM_PTR(&inkplate_i2s_push_frame_obj)},
    {MP_ROM_QSTR(MP_QSTR_mono_display), MP_ROM_PTR(&inkplate_mono_display_obj)},
    {MP_ROM_QSTR(MP_QSTR_gs_display), MP_ROM_PTR(&inkplate_gs_display_obj)},
    {MP_ROM_QSTR(MP_QSTR_partial_display), MP_ROM_PTR(&inkplate_partial_display_obj)},
    {MP_ROM_QSTR(MP_QSTR_select_spi_panel), MP_ROM_PTR(&inkplate_select_spi_panel_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_init), MP_ROM_PTR(&inkplate_spi_panel_init_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_deinit), MP_ROM_PTR(&inkplate_spi_panel_deinit_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_reset), MP_ROM_PTR(&inkplate_spi_panel_reset_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_set_rst), MP_ROM_PTR(&inkplate_spi_panel_set_rst_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_wait_busy), MP_ROM_PTR(&inkplate_spi_panel_wait_busy_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_send_command),
     MP_ROM_PTR(&inkplate_spi_panel_send_command_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_panel_send_data), MP_ROM_PTR(&inkplate_spi_panel_send_data_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_pins_low), MP_ROM_PTR(&inkplate_spi_dual_pins_low_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_power_up_io), MP_ROM_PTR(&inkplate_spi_dual_power_up_io_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_power_down_io),
     MP_ROM_PTR(&inkplate_spi_dual_power_down_io_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_set_power), MP_ROM_PTR(&inkplate_spi_dual_set_power_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_select), MP_ROM_PTR(&inkplate_spi_dual_select_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_deselect), MP_ROM_PTR(&inkplate_spi_dual_deselect_obj)},
    {MP_ROM_QSTR(MP_QSTR_spi_dual_write), MP_ROM_PTR(&inkplate_spi_dual_write_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_set_mirror_x), MP_ROM_PTR(&inkplate_gfx_set_mirror_x_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_set_gs4_nibble_swap),
     MP_ROM_PTR(&inkplate_gfx_set_gs4_nibble_swap_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_set_pixel), MP_ROM_PTR(&inkplate_gfx_set_pixel_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_buf_fill), MP_ROM_PTR(&inkplate_gfx_buf_fill_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_draw_bitmap), MP_ROM_PTR(&inkplate_gfx_draw_bitmap_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_hline), MP_ROM_PTR(&inkplate_gfx_hline_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_vline), MP_ROM_PTR(&inkplate_gfx_vline_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_line), MP_ROM_PTR(&inkplate_gfx_line_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_rect), MP_ROM_PTR(&inkplate_gfx_rect_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_fill_rect), MP_ROM_PTR(&inkplate_gfx_fill_rect_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_circle), MP_ROM_PTR(&inkplate_gfx_circle_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_fill_circle), MP_ROM_PTR(&inkplate_gfx_fill_circle_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_triangle), MP_ROM_PTR(&inkplate_gfx_triangle_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_fill_triangle), MP_ROM_PTR(&inkplate_gfx_fill_triangle_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_round_rect), MP_ROM_PTR(&inkplate_gfx_round_rect_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_fill_round_rect), MP_ROM_PTR(&inkplate_gfx_fill_round_rect_obj)},
    {MP_ROM_QSTR(MP_QSTR_gfx_draw_char), MP_ROM_PTR(&inkplate_gfx_draw_char_obj)},
    {MP_ROM_QSTR(MP_QSTR_jpeg_draw_gs4), MP_ROM_PTR(&inkplate_jpeg_draw_gs4_obj)},
    {MP_ROM_QSTR(MP_QSTR_png_draw_gs4), MP_ROM_PTR(&inkplate_png_draw_gs4_obj)},
    {MP_ROM_QSTR(MP_QSTR_bmp_draw_gs4), MP_ROM_PTR(&inkplate_bmp_draw_gs4_obj)},
    {MP_ROM_QSTR(MP_QSTR_bmp_draw_palette), MP_ROM_PTR(&inkplate_bmp_draw_palette_obj)},
    {MP_ROM_QSTR(MP_QSTR_jpeg_draw_palette), MP_ROM_PTR(&inkplate_jpeg_draw_palette_obj)},
    {MP_ROM_QSTR(MP_QSTR_png_draw_palette), MP_ROM_PTR(&inkplate_png_draw_palette_obj)},
};
static MP_DEFINE_CONST_DICT(inkplate_module_globals, inkplate_module_globals_table);

const mp_obj_module_t inkplate_user_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&inkplate_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_inkplate, inkplate_user_cmodule);
