"""Inkplate display driver: 8-level (3-bit) grayscale storage (GS4_HMSB, raw 0-7).

The C engine (firmware/usermods/inkplate/epd_i2s.c, waveform.c) drives the real 3-bit/8-level
waveform table natively -- no intermediate fold.
"""

import time
import micropython
import framebuf
from micropython import const
from inkplate4tempera import _Inkplate

# Raw display constants for Inkplate 4TEMPERA (600x600 square panel)
D_ROWS = const(600)
D_COLS = const(600)


class InkplateGS2(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 2)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.GS4_HMSB)

    # display sends the grayscale buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed directly from the real
        # Inkplate4TEMPERADriver.cpp display3b() pre-clean sequence -- identical to
        # display1b()'s own sequence on this board.
        t0 = time.ticks_ms()
        ip.clean(0, 5)
        ip.clean(1, 15)
        ip.clean(0, 15)
        ip.clean(1, 15)
        ip.clean(0, 15)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 9 phases driven in C,
        # same as every other board. This board's real display3b() loops for(k<8), one
        # short of the 9 stored here, but the 9th (final) phase is all-zero/no-op, so
        # pushing it as a harmless extra pass keeps this consistent with every other
        # board's waveform.phases=9 instead of a one-off 8.
        t1 = time.ticks_ms()
        ip.gs_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("GS2: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display3b() tail
        # (clean(3, 1); vscan_start();).
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(600 * 600 // 2):
            fb[ix] = 0x77  # both nibbles = raw level 7 (white)
