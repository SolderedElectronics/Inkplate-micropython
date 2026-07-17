"""Driver for the Inkplate4TEMPERA buzzer -- BUZZ_EN pin (12, internal
PCAL6416A expander) gates the buzzer on/off; pitch is set via the MCP4018
digipot at DIGIPOT_ADDR (0x2F). Inkplate4TEMPERA-only peripheral.
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
        cls._en_pin.digital_write(1)  # Active-low enable -- HIGH = off
        cls._digipot = MCP4018(i2c, digipot_addr)

    # Quadratic-regression approximation mapping frequency to wiper percent;
    # truncates toward zero (like a C int cast), not Python's round-half-even.
    @classmethod
    def _freq_to_wiper_percent(cls, freq):
        freq = min(max(freq, _BEEP_FREQ_MIN), _BEEP_FREQ_MAX)
        return int(156.499576 + (-0.130347337 * freq))

    @classmethod
    def beep_on(cls, freq=None):
        cls._en_pin.digital_write(0)
        if freq is None:
            cls._digipot.set_wiper_percent(50)  # Default duty when no frequency given
        else:
            cls._digipot.set_wiper_percent(cls._freq_to_wiper_percent(freq))

    @classmethod
    def beep_off(cls):
        cls._en_pin.digital_write(1)

    # Blocking: sleeps for length_ms, then turns off.
    @classmethod
    def beep(cls, length_ms, freq=None):
        cls.beep_on(freq)
        time.sleep_ms(length_ms)
        cls.beep_off()
