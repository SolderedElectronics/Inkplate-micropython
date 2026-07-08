# FILE: Inkplate10-lowLevelTest.py
# BRIEF: Diagnostic-only test for the Phase 2 C port (docs/REFACTOR-PLAN.md step 7).
#        Exercises ONLY power_on/clean/power_off (vscan_start + fill_screen) --
#        bypasses InkplateMono/InkplateGS2/InkplatePartial and the per-row draw loop
#        entirely, to isolate whether the lowest-level primitives can produce a
#        correct, visible result at all.
from machine import I2C, Pin
from inkplate10 import _Inkplate
import time

_Inkplate.init(I2C(0, scl=Pin(22), sda=Pin(21)))

print("power on")
_Inkplate.power_on()
_Inkplate.i2s_init()

print("discharge x20 -- reset panel to a neutral state")
_Inkplate.clean(2, 20)
time.sleep_ms(1000)

print("black x8 -- should turn the whole panel solid black")
_Inkplate.clean(1, 8)
time.sleep_ms(2000)

print("white x8 -- should turn the whole panel solid white")
_Inkplate.clean(0, 8)
time.sleep_ms(2000)

_Inkplate.i2s_deinit()
print("power off")
_Inkplate.power_off()

print("done")
