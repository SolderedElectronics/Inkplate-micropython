"""Tri-states the e-paper bit-banged control/data bus during power_off() to stop ESP32
GPIOs from actively driving current into now-unpowered downstream circuitry during
deep sleep. Only the plain GPIO input/output-mode toggle is done here -- the I2S
GPIO-matrix connect/disconnect for the same signals is already handled by this
project's own epd_i2s_init()/epd_i2s_deinit() at the right times.
"""

from machine import Pin

_CL = 0
_LE = 2
_CKV = 32
_SPH = 33
_DATA_PINS = (4, 5, 18, 19, 23, 25, 26, 27)


def tristate_display_pins(*expander_pins):
    for pin in (_CL, _LE, _CKV, _SPH) + _DATA_PINS:
        Pin(pin, Pin.IN)
    for gpio_pin in expander_pins:
        gpio_pin.pcal6416a.pin_mode(gpio_pin.pin, 0)  # mode_input


def restore_display_pins(*expander_pins):
    Pin(_CL, Pin.OUT, value=0)
    Pin(_LE, Pin.OUT, value=0)
    Pin(_CKV, Pin.OUT, value=0)
    Pin(_SPH, Pin.OUT, value=1)
    for pin in _DATA_PINS:
        Pin(pin, Pin.OUT)
    for gpio_pin in expander_pins:
        gpio_pin.pcal6416a.pin_mode(gpio_pin.pin, 1)  # mode_output
