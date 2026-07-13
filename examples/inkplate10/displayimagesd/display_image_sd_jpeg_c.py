"""Decode mountain.jpg from the SD card through the new C JPEG decode path (ROM tjpgd,
docs/REFACTOR-PLAN.md Phase 7 step 18) and draw it in grayscale.

Ahead of step 21 (real Floyd-Steinberg/etc. dithering): calls the low-level
inkplate.jpeg_draw_gs4() C binding directly, with simple nearest-of-8-levels luminance
quantization and no error diffusion -- expect visible banding. draw_image()/
draw_jpg_from_sd() aren't wired to this path yet.
"""

from inkplate10 import Inkplate
import inkplate
import time

# Inkplate10 physical (unrotated) panel dimensions -- see D_COLS/D_ROWS in
# boards/inkplate10/inkplate10.py.
D_COLS = 1200
D_ROWS = 825

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

with open("/sd/mountain.jpg", "rb") as f:
    jpg_data = f.read()

t0 = time.ticks_ms()
width, height = inkplate.jpeg_draw_gs4(
    ipk.ipg._framebuf, D_COLS, D_ROWS, ipk.rotation, 0, 0, jpg_data
)
print("decoded {}x{} JPEG in {} ms".format(width, height, time.ticks_diff(time.ticks_ms(), t0)))

ipk.display()

ipk.sd_card_sleep()
