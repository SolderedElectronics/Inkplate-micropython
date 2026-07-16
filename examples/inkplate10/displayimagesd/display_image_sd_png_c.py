"""Decode a PNG from the SD card through the C PNG decode path (vendored pngle, ROM
miniz/tinfl, docs/refactor_plan.md Phase 7 step 19) with real Floyd-Steinberg dithering
(step 21) and draw it in grayscale. Alpha is ignored (treated fully opaque).

Calls the high-level draw_png_from_sd() (boards/inkplate10/inkplate10.py) -- it wraps the
same inkplate.png_draw_gs4() C binding this example called directly before step 43, plus
the file read and a gc.collect() after.

Copy any PNG onto the SD card as /sd/coastal.png before running this example -- no
sample PNG ships in this repo (mountain.jpg is the JPEG example's sample).
"""

from inkplate10 import Inkplate
import time

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

t0 = time.ticks_ms()
ipk.draw_png_from_sd(
    "/sd/coastal.png",
    0,
    0,
    invert=False,
    dither=True,
    kernel_type=Inkplate.KERNEL_FLOYD_STEINBERG,
)
print("decoded+drew PNG in {} ms".format(time.ticks_diff(time.ticks_ms(), t0)))

ipk.display()

ipk.sd_card_sleep()
