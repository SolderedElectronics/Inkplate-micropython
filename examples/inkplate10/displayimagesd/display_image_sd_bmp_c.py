"""Decode a BMP from the SD card through the new C BMP decode path (24-bit, 1/4/8-bit
indexed, and 16-bit 555/565, docs/REFACTOR-PLAN.md Phase 7 step 20) and draw it in
grayscale.

Ahead of step 21 (real Floyd-Steinberg/etc. dithering): calls the low-level
inkplate.bmp_draw_gs4() C binding directly, with simple nearest-of-8-levels luminance
quantization and no error diffusion -- expect visible banding. draw_bmp_from_sd() isn't
wired to this path yet (that Python method still uses its own pure-Python decode).

Copy a BMP onto the SD card as /sd/coastal.bmp before running this example.

Note: uses os.stat + readinto() into a pre-sized bytearray rather than f.read() --
MicroPython's whole-file read() grows its buffer geometrically and can transiently
need more than the final size, so it can MemoryError on a file that a single
pre-sized allocation of the same size handles fine (seen on real hardware with this
example's own 1.4MB BMP, ~3.3MB free heap at the time).
"""

from inkplate10 import Inkplate
import inkplate
import os
import time

# Inkplate10 physical (unrotated) panel dimensions -- see D_COLS/D_ROWS in
# boards/inkplate10/inkplate10.py.
D_COLS = 1200
D_ROWS = 825

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

bmp_size = os.stat("/sd/coastal.bmp")[6]
bmp_data = bytearray(bmp_size)
with open("/sd/coastal.bmp", "rb") as f:
    f.readinto(bmp_data)

t0 = time.ticks_ms()
width, height = inkplate.bmp_draw_gs4(
    ipk.ipg._framebuf, D_COLS, D_ROWS, ipk.rotation, 0, 0, bmp_data
)
print("decoded {}x{} BMP in {} ms".format(width, height, time.ticks_diff(time.ticks_ms(), t0)))

ipk.display()

ipk.sd_card_sleep()
