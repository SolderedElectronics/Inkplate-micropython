"""MicroPython class for a 1-bit black-and-white display mode."""

import time
import framebuf
from inkplate6 import _Inkplate

# Raw display constants for Inkplate 6
D_ROWS = const(600)
D_COLS = const(800)


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed from the real Arduino
        # Inkplate6Driver.cpp display1b() -- differs from Inkplate10's own clean-cycle
        # counts (12/11), so ported from this board's own reference driver instead of
        # copying Inkplate10's file verbatim.
        t0 = time.ticks_ms()
        ip.clean(0, 1)
        ip.clean(1, 18)
        ip.clean(2, 1)
        ip.clean(0, 18)
        ip.clean(2, 1)
        ip.clean(1, 18)
        ip.clean(2, 1)
        ip.clean(0, 18)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 6 phases driven in C.
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(800 * 600 // 8):
            fb[ix] = 0x00
