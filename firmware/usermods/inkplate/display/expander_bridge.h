/**
 * @file expander_bridge.h
 * @brief C-callable interface for toggling PCAL6416A expander lines.
 *
 * The actual I2C transaction stays in Python (shared/PCAL6416A.py) so the bus keeps a
 * single owner alongside the PMIC/RTC drivers (also Python-side). C holds a callback
 * registered by Python at init and invokes it whenever an expander pin needs a write.
 */
#ifndef INKPLATE_EXPANDER_BRIDGE_H
#define INKPLATE_EXPANDER_BRIDGE_H

#include "py/obj.h"
#include <stdint.h>

/**
 * @brief Registers the Python callback used to write expander pins.
 * @param cb Callable invoked as cb(addr, pin, value) -> None.
 */
void expander_bridge_set_callback(mp_obj_t cb);

/**
 * @brief Toggles one expander pin via the registered callback.
 * Raises RuntimeError if no callback has been registered yet.
 * @param addr I2C address of the target expander.
 * @param pin Pin number on the expander to write.
 * @param value Logic level to write to the pin.
 */
void expander_bridge_write(uint8_t addr, uint8_t pin, uint8_t value);

#endif // INKPLATE_EXPANDER_BRIDGE_H
