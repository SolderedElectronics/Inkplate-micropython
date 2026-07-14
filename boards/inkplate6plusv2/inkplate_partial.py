"""Manages partial display updates by diffing framebuffer copies.

It starts by making a copy of the current framebuffer, then when asked to draw
renders the differences between the copy and the new framebuffer state. The
constructor needs a reference to the current/main display object
(InkplateMono); only InkplateMono is supported at the moment.
"""

import time
from inkplate6plusv2 import _Inkplate


class InkplatePartial:
    def __init__(self, base):
        self._base = base
        self._framebuf = bytearray(len(base._framebuf))

    # start makes a reference copy of the current framebuffer
    def start(self):
        self._framebuf[:] = self._base._framebuf[:]

    # display the changes between our reference copy and the current framebuffer contents
    # -- runs over I2S DMA in C now (firmware/usermods/inkplate/epd_i2s.c's
    # epd_i2s_push_partial_frame, cfg->partial_reps=5 matching this board's own pasted
    # Arduino reference driver's partialUpdate() for(k<5) loop), matching how mono/GS/clean
    # already work. Always walks the full frame (no region params) -- matches the real
    # Arduino reference driver's partialUpdate(), which has none either.
    def display(self):
        ip = _Inkplate
        ip.power_on()
        ip.i2s_init()

        t0 = time.ticks_ms()
        ip.partial_display(self._framebuf, self._base._framebuf)
        t1 = time.ticks_ms()

        # Tail transcribed directly from the real Inkplate6PLUSDriver.cpp partialUpdate()
        # (clean(2, 2); clean(3, 1); vscan_start();).
        ip.clean(2, 2)
        ip.clean(3, 1)
        ip.vscan_start()
        ip.i2s_deinit()
        ip.power_off()

        td = time.ticks_diff(t1, t0)
        print("Partial: draw %dms" % td)
