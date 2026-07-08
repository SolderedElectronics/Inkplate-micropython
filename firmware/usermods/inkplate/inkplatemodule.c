#include "py/runtime.h"
#include "py/obj.h"
#include "expander_bridge.h"
#include "board_config.h"
#include "epd_bitbang.h"
#include "epd_i2s.h"
#include "waveform.h"
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
};
static MP_DEFINE_CONST_DICT(inkplate_module_globals, inkplate_module_globals_table);

const mp_obj_module_t inkplate_user_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&inkplate_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_inkplate, inkplate_user_cmodule);
