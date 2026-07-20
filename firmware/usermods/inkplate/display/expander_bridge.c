/**
 * @file expander_bridge.c
 * @brief C-to-Python callback bridge for PCAL6416A expander writes.
 */
#include "expander_bridge.h"
#include "py/runtime.h"

void expander_bridge_set_callback(mp_obj_t cb)
{
    MP_STATE_VM(inkplate_expander_write_cb) = cb;
}

void expander_bridge_write(uint8_t addr, uint8_t pin, uint8_t value)
{
    mp_obj_t cb = MP_STATE_VM(inkplate_expander_write_cb);
    if (cb == MP_OBJ_NULL) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("expander callback not set"));
    }

    mp_obj_t args[3] = {
        mp_obj_new_int(addr),
        mp_obj_new_int(pin),
        mp_obj_new_int(value),
    };
    mp_call_function_n_kw(cb, 3, 0, args);
}

MP_REGISTER_ROOT_POINTER(mp_obj_t inkplate_expander_write_cb);
