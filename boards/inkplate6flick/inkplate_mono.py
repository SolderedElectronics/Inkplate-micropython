"""MicroPython class for a 1-bit black-and-white display mode."""

import time
import framebuf
from inkplate6_flick import _Inkplate

# Raw display constants for Inkplate 6FLICK
D_ROWS = const(758)
D_COLS = const(1024)


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # KNOWN ISSUE (docs/refactor_plan.md step 24, HIL-blocked): on real hardware,
        # calling more than one display-affecting operation (clean()/mono_display()) in
        # the same power_on()/i2s_init() bracket is unreliable -- content sometimes
        # doesn't show, sometimes the whole panel goes solid black regardless of what was
        # drawn. Each operation alone (burn-in only, or mono_display only) works
        # correctly and reproducibly. A "priming" mono_display() call before the burn-in
        # was tried as a workaround and made things worse for all-white content (stuck
        # solid black), so it was reverted -- do not re-add it without re-verifying
        # against a genuinely fresh (never-before-drawn) screen position, since the same
        # rect position across repeated tests gives false-positive "visible" results on
        # this bistable display. Root cause not identified; needs either a scope on
        # CKV/SPH/LE/GMODE comparing single-op vs chained-op timing, or a check of the
        # physical panel FPC/connector for a marginal connection.

        # clean the display (I2S DMA), reps transcribed verbatim from the real Arduino
        # Inkplate6FLICKDriver.cpp display1b()'s clear sequence -- same 9-call shape as
        # display3b()'s, but with this board's own rep counts (5/15/1/15/1/15/1/15/1,
        # not Inkplate6's 1/18/1/18/1/18/1/18).
        t0 = time.ticks_ms()
        ip.clean(0, 5)
        ip.clean(1, 15)
        ip.clean(2, 1)
        ip.clean(0, 15)
        ip.clean(2, 1)
        ip.clean(1, 15)
        ip.clean(2, 1)
        ip.clean(0, 15)
        ip.clean(2, 1)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 4 black-push phases + 1
        # black/white phase driven in C (inkplatemodule.c's inkplate_mono_display special-
        # cases this board to 4 instead of the usual 5, matching display1b()'s own
        # for (k<4)/for (k<1) loops).
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        # display1b()'s delayMicroseconds(230) before its separate discharge pass, then
        # the discharge pass itself -- pattern index 2 (0x00, "discharge the screen") is
        # exactly what that pass writes to every line.
        time.sleep_us(230)
        ip.clean(2, 1)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(1024 * 758 // 8):
            fb[ix] = 0x00
