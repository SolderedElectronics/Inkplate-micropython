#include "py/runtime.h"
#include "py/obj.h"

static mp_obj_t inkplate_version(void)
{
    return mp_obj_new_str("0.0.1", 5);
}
static MP_DEFINE_CONST_FUN_OBJ_0(inkplate_version_obj, inkplate_version);

static const mp_rom_map_elem_t inkplate_module_globals_table[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_inkplate)},
    {MP_ROM_QSTR(MP_QSTR_version), MP_ROM_PTR(&inkplate_version_obj)},
};
static MP_DEFINE_CONST_DICT(inkplate_module_globals, inkplate_module_globals_table);

const mp_obj_module_t inkplate_user_cmodule = {
    .base = {&mp_type_module},
    .globals = (mp_obj_dict_t *)&inkplate_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_inkplate, inkplate_user_cmodule);
