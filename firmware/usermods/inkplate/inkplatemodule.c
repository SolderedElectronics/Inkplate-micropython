#include "py/runtime.h"
#include "py/obj.h"
#include "expander_bridge.h"
#include "board_config.h"
#include "epd_bitbang.h"
#include "epd_i2s.h"
#include "epd_partial_lut.h"
#include "waveform.h"
#include "gfx.h"
#include "jpeg_draw.h"
#include "png_draw.h"
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
// way it is through the C-internal epd_bitbang API -- this is the one place that holds
// it as static state instead.
static const board_config_t *active_board = NULL;

static mp_obj_t inkplate_select_board(mp_obj_t name_obj)
{
    const char *name = mp_obj_str_get_str(name_obj);
    if (strcmp(name, "inkplate10") == 0) {
        active_board = &board_config_inkplate10;
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

    static uint8_t mono_luts[INKPLATE_MONO_WAVE_PHASES][16];
    static bool mono_luts_ready = false;
    if (!mono_luts_ready) {
        inkplate_gen_mono_wave(mono_luts);
        mono_luts_ready = true;
    }

    epd_i2s_push_mono_frame(require_board(), (const uint8_t *)bufinfo.buf, mono_luts,
                            INKPLATE_MONO_WAVE_PHASES);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_mono_display_obj, inkplate_mono_display);

static mp_obj_t inkplate_gs_display(mp_obj_t framebuf_obj)
{
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(framebuf_obj, &bufinfo, MP_BUFFER_READ);

    const board_config_t *cfg = require_board();

    static uint8_t gs_luts[MAX_WAVE_PHASES][16];
    static bool gs_luts_ready = false;
    if (!gs_luts_ready) {
        inkplate_gen_wave_3bit(&cfg->waveform->table[0][0], MAX_WAVE_LEVELS,
                               cfg->waveform->phases, gs_luts);
        gs_luts_ready = true;
    }

    epd_i2s_push_gs_frame(cfg, (const uint8_t *)bufinfo.buf, gs_luts, cfg->waveform->phases);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_gs_display_obj, inkplate_gs_display);

static mp_obj_t inkplate_partial_display(mp_obj_t old_fb_obj, mp_obj_t new_fb_obj)
{
    mp_buffer_info_t old_info, new_info;
    mp_get_buffer_raise(old_fb_obj, &old_info, MP_BUFFER_READ);
    mp_get_buffer_raise(new_fb_obj, &new_info, MP_BUFFER_READ);

    const board_config_t *cfg = require_board();

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

static mp_obj_t inkplate_gfx_hline(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_hline(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
              mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
              mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_hline_obj, 9, 9, inkplate_gfx_hline);

static mp_obj_t inkplate_gfx_vline(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_vline(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
              mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
              mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_vline_obj, 9, 9, inkplate_gfx_vline);

static mp_obj_t inkplate_gfx_line(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_line(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
             mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
             mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
             mp_obj_get_int(args[9]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_line_obj, 10, 10, inkplate_gfx_line);

static mp_obj_t inkplate_gfx_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_rect(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
             mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
             mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]),
             mp_obj_get_int(args[9]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_rect_obj, 10, 10, inkplate_gfx_rect);

static mp_obj_t inkplate_gfx_fill_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_fill_rect(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]),
                  mp_obj_get_int(args[2]), mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
                  mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), mp_obj_get_int(args[7]),
                  mp_obj_get_int(args[8]), mp_obj_get_int(args[9]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_fill_rect_obj, 10, 10,
                                           inkplate_gfx_fill_rect);

static mp_obj_t inkplate_gfx_circle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_circle(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
               mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
               mp_obj_get_int(args[6]), mp_obj_get_int(args[7]), mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_circle_obj, 9, 9, inkplate_gfx_circle);

static mp_obj_t inkplate_gfx_fill_circle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_fill_circle(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]),
                    mp_obj_get_int(args[2]), mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
                    mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), mp_obj_get_int(args[7]),
                    mp_obj_get_int(args[8]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_fill_circle_obj, 9, 9,
                                           inkplate_gfx_fill_circle);

static mp_obj_t inkplate_gfx_triangle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_triangle(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]),
                 mp_obj_get_int(args[2]), mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
                 mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), mp_obj_get_int(args[7]),
                 mp_obj_get_int(args[8]), mp_obj_get_int(args[9]), mp_obj_get_int(args[10]),
                 mp_obj_get_int(args[11]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_triangle_obj, 12, 12,
                                           inkplate_gfx_triangle);

static mp_obj_t inkplate_gfx_fill_triangle(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_fill_triangle(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]),
                      mp_obj_get_int(args[2]), mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
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
    gfx_round_rect(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]),
                   mp_obj_get_int(args[2]), mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
                   mp_obj_get_int(args[5]), mp_obj_get_int(args[6]), mp_obj_get_int(args[7]),
                   mp_obj_get_int(args[8]), mp_obj_get_int(args[9]), mp_obj_get_int(args[10]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_round_rect_obj, 11, 11,
                                           inkplate_gfx_round_rect);

static mp_obj_t inkplate_gfx_fill_round_rect(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t buf;
    gfx_fill_round_rect(gfx_writable_buf(args[0], &buf), mp_obj_get_int(args[1]),
                        mp_obj_get_int(args[2]), mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
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
    uint8_t *fb = gfx_writable_buf(args[0], &buf);
    mp_get_buffer_raise(args[7], &char_buf, MP_BUFFER_READ);

    gfx_draw_char(fb, mp_obj_get_int(args[1]), mp_obj_get_int(args[2]), mp_obj_get_int(args[3]),
                  mp_obj_get_int(args[4]), mp_obj_get_int(args[5]), mp_obj_get_int(args[6]),
                  (const uint8_t *)char_buf.buf, mp_obj_get_int(args[8]), mp_obj_get_int(args[9]),
                  mp_obj_get_int(args[10]), mp_obj_get_int(args[11]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_gfx_draw_char_obj, 12, 12,
                                           inkplate_gfx_draw_char);

// Decodes+draws a JPEG straight into a GS4 framebuffer, ahead of docs/REFACTOR-PLAN.md
// step 21's real dithering -- see jpeg_draw.h. args: framebuf, phys_w, phys_h, rotation,
// x0, y0, jpeg_bytes. Returns (width, height) of the decoded JPEG.
static mp_obj_t inkplate_jpeg_draw_gs4(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, jpg_buf;
    uint8_t *fb = gfx_writable_buf(args[0], &fb_buf);
    mp_get_buffer_raise(args[6], &jpg_buf, MP_BUFFER_READ);

    uint32_t width = 0, height = 0;
    int res =
        jpeg_draw_gs4(fb, mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
                      mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
                      (const uint8_t *)jpg_buf.buf, jpg_buf.len, &width, &height);
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("JPEG decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_jpeg_draw_gs4_obj, 7, 7,
                                           inkplate_jpeg_draw_gs4);

// Decodes+draws a PNG straight into a GS4 framebuffer, ahead of
// docs/REFACTOR-PLAN.md step 21's real dithering -- see png_draw.h. args:
// framebuf, phys_w, phys_h, rotation, x0, y0, png_bytes. Returns (width, height)
// of the decoded PNG.
static mp_obj_t inkplate_png_draw_gs4(size_t n_args, const mp_obj_t *args)
{
    (void)n_args;
    mp_buffer_info_t fb_buf, png_buf;
    uint8_t *fb = gfx_writable_buf(args[0], &fb_buf);
    mp_get_buffer_raise(args[6], &png_buf, MP_BUFFER_READ);

    uint32_t width = 0, height = 0;
    int res =
        png_draw_gs4(fb, mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
                     mp_obj_get_int(args[3]), mp_obj_get_int(args[4]), mp_obj_get_int(args[5]),
                     (const uint8_t *)png_buf.buf, png_buf.len, &width, &height);
    if (res != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("PNG decode failed"));
    }

    mp_obj_t dims[2] = {mp_obj_new_int(width), mp_obj_new_int(height)};
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(inkplate_png_draw_gs4_obj, 7, 7,
                                           inkplate_png_draw_gs4);

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
};
static MP_DEFINE_CONST_DICT(inkplate_module_globals, inkplate_module_globals_table);

const mp_obj_module_t inkplate_user_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&inkplate_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_inkplate, inkplate_user_cmodule);
