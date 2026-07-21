"""Standalone hardware-revision probe for Inkplate10 -- no display init, just I2C.

Prints which variant (classic v1 vs V2) the auto-detect probe picks for the board
plugged in right now. Useful to confirm the probe before trusting it in begin().
"""

from machine import I2C, Pin
from inkplate10 import _detect_variant, _PROBE_ADDR, _PROBE_REG

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
detected = i2c.scan()
print("I2C scan:", ["{:#x}".format(a) for a in detected])

if _PROBE_ADDR not in detected:
    print("ERROR: no device at {:#x} -- can't probe".format(_PROBE_ADDR))
else:
    val = i2c.readfrom_mem(_PROBE_ADDR, _PROBE_REG, 1)[0]
    print("Register {:#x} @ {:#x} = {:#x}".format(_PROBE_REG, _PROBE_ADDR, val))
    variant = _detect_variant(i2c)
    print("Detected variant:", variant)
