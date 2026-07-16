"""Driver for the Inkplate4TEMPERA buzzer -- BUZZ_EN pin (12, internal
PCAL6416A expander per the pasted pins.h) gates the buzzer on/off; pitch is
set via the MCP4018 digipot at DIGIPOT_ADDR (0x2F). Ported from the real
Arduino Buzzer.cpp/.h (`#ifdef ARDUINO_INKPLATE4TEMPERA`-gated,
Inkplate4TEMPERA-only peripheral).
"""

import time
from micropython import const
from pcal6416a import GpioPin, mode_output
from mcp4018 import MCP4018

_BEEP_FREQ_MIN = const(572)
_BEEP_FREQ_MAX = const(2933)


class Buzzer:
    _en_pin = None
    _digipot = None

    @classmethod
    def init(cls, i2c, pcal, en_pin, digipot_addr=0x2F):
        cls._en_pin = GpioPin(pcal, en_pin, mode_output)
        cls._en_pin.digital_write(1)  # active-low enable -- HIGH = off
        cls._digipot = MCP4018(i2c, digipot_addr)

    # matches the real freqToWiperPercent()'s quadratic-regression approximation,
    # including its implicit truncation-toward-zero int cast (C++ `int freq` return)
    @classmethod
    def _freq_to_wiper_percent(cls, freq):
        freq = min(max(freq, _BEEP_FREQ_MIN), _BEEP_FREQ_MAX)
        return int(156.499576 + (-0.130347337 * freq))

    @classmethod
    def beep_on(cls, freq=None):
        cls._en_pin.digital_write(0)
        if freq is None:
            cls._digipot.set_wiper_percent(50)  # real beepOn()'s no-arg default
        else:
            cls._digipot.set_wiper_percent(cls._freq_to_wiper_percent(freq))

    @classmethod
    def beep_off(cls):
        cls._en_pin.digital_write(1)

    # blocking, matches the real beep()'s delay(length)-then-off shape
    @classmethod
    def beep(cls, length_ms, freq=None):
        cls.beep_on(freq)
        time.sleep_ms(length_ms)
        cls.beep_off()
