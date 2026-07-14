"""Manages partial display updates by diffing framebuffer copies.

It starts by making a copy of the current framebuffer, then when asked to draw
renders the differences between the copy and the new framebuffer state. The
constructor needs a reference to the current/main display object
(InkplateMono); only InkplateMono is supported at the moment.
"""

import time
from inkplate6 import _Inkplate


class InkplatePartial:
    def __init__(self, base):
        self._base = base
        self._framebuf = bytearray(len(base._framebuf))

    # start makes a reference copy of the current framebuffer
    def start(self):
        self._framebuf[:] = self._base._framebuf[:]

    # display the changes between our reference copy and the current framebuffer contents
    # -- runs over I2S DMA in C now (firmware/usermods/inkplate/epd_i2s.c's
    # epd_i2s_push_partial_frame), matching how mono/GS/clean already work. Always walks
    # the full frame (no region params) -- matches the real Arduino reference driver's
    # partialUpdate(), which has none either: unchanged pixels get a skip code from the
    # diff, there's no row-range transmission shortcut over I2S.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        t0 = time.ticks_ms()
        ip.partial_display(self._framebuf, self._base._framebuf)
        t1 = time.ticks_ms()

        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.i2s_deinit()
        ip.power_off()

        td = time.ticks_diff(t1, t0)
        print("Partial: draw %dms" % td)
