#include "py/runtime.h"
#include "py/obj.h"
#include "expander_bridge.h"

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
static MP_DEFINE_CONST_FUN_OBJ_1(inkplate_set_expander_write_cb_obj, inkplate_set_expander_write_cb);

// HIL test hook: toggles one expander pin through the bridge.
// Use an unused/free expander pin for verification — OE/GMODE/SPV are wired to the
// panel and can't be probed directly (see docs/REFACTOR-PLAN.md Phase 1 step 6).
static mp_obj_t inkplate_test_expander_write(mp_obj_t addr, mp_obj_t pin, mp_obj_t value)
{
    expander_bridge_write(mp_obj_get_int(addr), mp_obj_get_int(pin), mp_obj_get_int(value));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(inkplate_test_expander_write_obj, inkplate_test_expander_write);

static const mp_rom_map_elem_t inkplate_module_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_inkplate)},
    {MP_ROM_QSTR(MP_QSTR_version), MP_ROM_PTR(&inkplate_version_obj)},
    {MP_ROM_QSTR(MP_QSTR_set_expander_write_cb), MP_ROM_PTR(&inkplate_set_expander_write_cb_obj)},
    {MP_ROM_QSTR(MP_QSTR_test_expander_write), MP_ROM_PTR(&inkplate_test_expander_write_obj)},
};
static MP_DEFINE_CONST_DICT(inkplate_module_globals, inkplate_module_globals_table);

const mp_obj_module_t inkplate_user_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&inkplate_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_inkplate, inkplate_user_cmodule);
