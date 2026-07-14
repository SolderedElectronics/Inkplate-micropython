"""Inkplate display driver: 8-level (3-bit) grayscale storage (GS4_HMSB, raw 0-7).

The C engine (firmware/usermods/inkplate/epd_i2s.c, waveform.c) drives the real 3-bit/8-level
waveform table natively -- no intermediate fold.
"""

import time
import micropython
import framebuf
from micropython import const
from inkplate5v2 import _Inkplate

# Raw display constants for Inkplate 5V2
D_ROWS = const(720)
D_COLS = const(1280)

TPS65186_addr = const(0x48)  # I2C address

# Inkplate provides access to the pins of the Inkplate 5V2 as well as to low-level display
# functions.

RTC_I2C_ADDR = 0x51
RTC_RAM_by = 0x03
RTC_DAY_ADDR = 0x07
RTC_SECOND_ADDR = 0x04


class InkplateGS2(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 2)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.GS4_HMSB)

    # display sends the grayscale buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed from the real Arduino
        # Inkplate5V2Driver.cpp display3b() -- identical sequence to display1b() on this
        # board (11 reps, own reference driver's own value, not Inkplate6's 18).
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 11)
        ip.clean(2, 1)
        ip.clean(0, 11)
        ip.clean(2, 1)
        ip.clean(1, 11)
        ip.clean(2, 1)
        ip.clean(0, 11)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display3b() -- unlike
        # Inkplate6, Inkplate5V2's own display3b() has its trailing vscan_start() call
        # commented out (never executed), so it's deliberately not ported here either.
        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(1280 * 720 // 2):
            fb[ix] = 0x77  # both nibbles = raw level 7 (white)
