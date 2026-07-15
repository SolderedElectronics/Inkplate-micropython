"""MicroPython class for a 1-bit black-and-white display mode."""

import time
import framebuf
from inkplate4tempera import _Inkplate

# Raw display constants for Inkplate 4TEMPERA (600x600 square panel)
D_ROWS = const(600)
D_COLS = const(600)


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display_mono sends the monochrome buffer to the display, clearing it first
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed directly from the real
        # Inkplate4TEMPERADriver.cpp display1b() pre-clean sequence (identical to
        # display3b()'s own sequence on this board).
        t0 = time.ticks_ms()
        ip.clean(0, 5)
        ip.clean(1, 15)
        ip.clean(0, 15)
        ip.clean(1, 15)
        ip.clean(0, 15)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 10 black-push phases + 1
        # final black/white phase driven in C. inkplatemodule.c's inkplate_mono_display
        # special-cases this board onto black_phases=10 (standard inkplate_gen_mono_wave
        # scheme, not the reversed-role Inkplate6PLUSV2 variant -- confirmed by this
        # board's own GraphicsDefs.h LUTB/LUT2 being byte-identical to the standard
        # op_blk/op_bw tables, not hand-waved from the unusual phase count alone).
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display1b() tail exactly
        # (clean(2, 1); clean(3, 1); vscan_start();) -- note this is clean(2, 1), not
        # clean(2, 2) like Inkplate6PLUSV2's own tail.
        ip.clean(2, 1)
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(600 * 600 // 8):
            fb[ix] = 0x00
