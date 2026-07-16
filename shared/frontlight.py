"""Driver for the frontlight LED driver, shared by Inkplate4TEMPERA and
Inkplate6PLUS/6PLUSV2/6FLICK (same chip + PCAL6416A-gated enable pin -- real Arduino
Frontlight.cpp/.h gated `#if defined(ARDUINO_INKPLATE6PLUS) ||
defined(ARDUINO_INKPLATE6PLUSV2) || defined(ARDUINO_INKPLATE4TEMPERA) ||
defined(ARDUINO_INKPLATE6FLICK)` -- each board's own pins.h supplies its own
FRONTLIGHT_EN pin number; all three boards wired in this repo put it on the internal
PCAL6416A expander (0x20), but the caller passes whichever pcal owns it).
"""

from micropython import const
from pcal6416a import GpioPin, mode_output

_FRONTLIGHT_ADDR = const(0x5C >> 1)  # 0x2E, digital-pot chip identical on all 3 boards


class Frontlight:
    _i2c = None
    _en_pin = None

    @classmethod
    def init(cls, i2c, pcal, en_pin):
        cls._i2c = i2c
        cls._en_pin = GpioPin(pcal, en_pin, mode_output)

    # v is 0-63; real setBrightness() writes `63 - (v & 0x3F)` to the pot's wiper
    # register -- lower register value is brighter, so this flips it back to the
    # intuitive 0=dim/63=bright the Arduino API exposes.
    @classmethod
    def set_brightness(cls, v):
        cls._i2c.writeto(_FRONTLIGHT_ADDR, bytes((0, 63 - (v & 0b00111111))))

    @classmethod
    def set_state(cls, enable):
        cls._en_pin.digital_write(1 if enable else 0)
