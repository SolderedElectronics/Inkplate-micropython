#include "expander_bridge.h"
#include "py/runtime.h"

static mp_obj_t expander_write_cb = MP_OBJ_NULL;

void expander_bridge_set_callback(mp_obj_t cb)
{
    expander_write_cb = cb;
}

void expander_bridge_write(uint8_t addr, uint8_t pin, uint8_t value)
{
    if (expander_write_cb == MP_OBJ_NULL) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("expander callback not set"));
    }

    mp_obj_t args[3] = {
        mp_obj_new_int(addr),
        mp_obj_new_int(pin),
        mp_obj_new_int(value),
    };
    mp_call_function_n_kw(expander_write_cb, 3, 0, args);
}
