"""MicroPython class for a 1-bit black-and-white display mode."""

import time
import framebuf
from inkplate6plusv2 import _Inkplate

# Raw display constants for Inkplate 6PLUS (same 1024x758 panel as Inkplate6FLICK)
D_ROWS = const(758)
D_COLS = const(1024)


class InkplateMono(framebuf.FrameBuffer):
    def __init__(self):
        self._framebuf = bytearray(D_ROWS * D_COLS // 8)
        super().__init__(self._framebuf, D_COLS, D_ROWS, framebuf.MONO_HMSB)

    # display_mono sends the monochrome buffer to the display, clearing it first.
    # extra_clean runs the pre-clean sequence twice instead of once -- defaults on because the
    # panel's prior content may be GS3 (8-level), whose per-pixel charge diversity the vendor's
    # single-pass rep counts (tuned for same-mode transitions) don't fully flush: HIL-confirmed
    # ghosting on a GS3->mono switch with a single pass, gone with two. Costs an extra ~570ms;
    # pass extra_clean=False to skip it for back-to-back mono updates that don't need it.
    def display(self, extra_clean=True):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        # clean the display (I2S DMA), reps transcribed directly from the real
        # Inkplate6PLUSDriver.cpp display1b() pre-clean sequence (identical to display3b()'s
        # own sequence on this board, matching Inkplate6's precedent of the two sequences
        # matching, though the actual rep counts differ from Inkplate6's).
        t0 = time.ticks_ms()
        for _ in range(2 if extra_clean else 1):
            ip.clean(0, 1)
            ip.clean(1, 15)
            ip.clean(2, 1)
            ip.clean(0, 5)
            ip.clean(2, 1)
            ip.clean(1, 15)

        # the display gets written via I2S DMA + the C waveform engine
        # (firmware/usermods/inkplate/epd_i2s.c, waveform.c) -- 4 white-push phases + 1
        # final black-push phase driven in C. inkplatemodule.c's inkplate_mono_display
        # special-cases this board onto inkplate_gen_mono_wave_white_first instead of the
        # usual inkplate_gen_mono_wave: this board's real display1b() also loops for(k<4),
        # but its phase *roles* are reversed from every other wired board's (repeated
        # phases push white/skip black, one final phase pushes black/skip white) -- HIL-
        # confirmed after the naive black_phases=4 mapping produced a uniformly dark/washed
        # panel, root-caused by decoding this board's own GraphicsDefs.h LUTW/LUTB against
        # its ~dram/dram indexing scheme.
        t1 = time.ticks_ms()
        ip.mono_display(self._framebuf)

        t2 = time.ticks_ms()
        tc = time.ticks_diff(t1, t0)
        td = time.ticks_diff(t2, t1)
        tt = time.ticks_diff(t2, t0)
        print("Mono: clean %dms, draw %dms, total %dms" % (tc, td, tt))

        # trailing park sequence, matches the real Arduino display1b() tail
        # (clean(2, 2); clean(3, 1); vscan_start();) -- unlike Inkplate6's own mono driver,
        # this board's real display1b() does end with a bare vscan_start() pulse.
        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

    @staticmethod
    @micropython.viper
    def clear(fb: ptr8):
        for ix in range(1024 * 758 // 8):
            fb[ix] = 0x00
