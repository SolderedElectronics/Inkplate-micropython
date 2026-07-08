"""Inkplate display driver: 8-level (3-bit) grayscale storage (GS4_HMSB, raw 0-7).

Storage is 8-level-ready (docs/REFACTOR-PLAN.md Phase 5 step 14), but the C engine still
folds each pixel to 4 practical levels (raw >> 1) until the real 3-bit waveform table is
wired in (step 15, blocked on per-board timing data) -- see
firmware/usermods/inkplate/gs_pack.h.
"""

import time
import micropython
import framebuf
from micropython import const
from shapes import Shapes
from inkplate10 import _Inkplate

# Raw display constants for Inkplate 10
D_ROWS = const(825)
D_COLS = const(1200)

TPS65186_addr = const(0x48)  # I2C address

# Inkplate provides access to the pins of the Inkplate 10 as well as to low-level display
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

        # clean the display (now driven via I2S DMA -- docs/REFACTOR-PLAN.md step 12)
        t0 = time.ticks_ms()
        ip.clean(1, 1)
        ip.clean(0, 10)
        ip.clean(2, 1)
        ip.clean(1, 10)
        ip.clean(2, 1)
        ip.clean(0, 10)
        ip.clean(2, 1)
        ip.clean(1, 10)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 8 phases driven in C.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(1200 * 825 // 2):
            fb[ix] = 0x77  # both nibbles = raw level 7 (white)


Shapes.__mix_me_in(InkplateGS2)
