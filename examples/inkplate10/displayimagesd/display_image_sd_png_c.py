"""Decode a PNG from the SD card through the new C PNG decode path (vendored pngle,
ROM miniz/tinfl, docs/refactor_plan.md Phase 7 step 19) with real Floyd-Steinberg
dithering (step 21) and draw it in grayscale. Alpha is ignored (treated fully opaque).

Calls the low-level inkplate.png_draw_gs4() C binding directly -- draw_image()/
draw_png_from_sd() (boards/inkplate10/inkplate10.py) now call the same binding, so this
example is mainly useful for exercising it without SD-card/urequests plumbing.

Copy any PNG onto the SD card as /sd/coastal.png before running this example -- no
sample PNG ships in this repo (mountain.jpg is the JPEG example's sample).
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

with open("/sd/coastal.png", "rb") as f:
    png_data = f.read()

t0 = time.ticks_ms()
width, height = inkplate.png_draw_gs4(
    ipk.ipg._framebuf,
    D_COLS,
    D_ROWS,
    ipk.rotation,
    ipk.display_mode,
    0,
    0,
    png_data,
    False,  # invert
    True,  # dither
    0,  # kernel_type: Floyd-Steinberg
)
print("decoded {}x{} PNG in {} ms".format(width, height, time.ticks_diff(time.ticks_ms(), t0)))

ipk.display()

ipk.sd_card_sleep()
