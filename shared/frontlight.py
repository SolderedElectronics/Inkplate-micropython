"""Driver for the frontlight LED driver, shared by Inkplate4TEMPERA and
Inkplate6PLUS/6PLUSV2/6FLICK (same chip + PCAL6416A-gated enable pin; each board
supplies its own FRONTLIGHT_EN pin number -- all three boards wired in this repo put
it on the internal PCAL6416A expander (0x20), but the caller passes whichever pcal
owns it).
"""

import time
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

    # v is 0-63; the pot's wiper register takes `63 - (v & 0x3F)` -- lower register
    # value is brighter, so this flips it back to the intuitive 0=dim/63=bright scale.
    @classmethod
    def set_brightness(cls, v):
        cls._i2c.writeto(_FRONTLIGHT_ADDR, bytes((0, 63 - (v & 0b00111111))))

    @classmethod
    def set_state(cls, enable):
        cls._en_pin.digital_write(1 if enable else 0)
        if enable:
            # Digital pot needs time to power up off EN before it'll ACK on I2C --
            # measured as an outright NAK at 0ms, reliably fine at 50ms, on
            # Inkplate6FLICK (HIL, 2026-07-17). Tempera/6PLUSv2 never showed this
            # with no delay, so their regulator/pot combo is just faster, but this
            # covers all three since it's the shared driver.
            time.sleep_ms(50)
