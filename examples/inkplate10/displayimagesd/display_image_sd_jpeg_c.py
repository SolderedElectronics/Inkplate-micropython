"""Decode mountain.jpg from the SD card through the C JPEG decode path (ROM tjpgd,
docs/refactor_plan.md Phase 7 step 18) with real Floyd-Steinberg dithering (step 21) and
draw it in grayscale.

Calls the high-level draw_jpg_from_sd() (boards/inkplate10/inkplate10.py) -- it wraps the
same inkplate.jpeg_draw_gs4() C binding this example called directly before step 43, plus
the file read and a gc.collect() after.
"""

from inkplate10 import Inkplate
import time

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

t0 = time.ticks_ms()
ipk.draw_jpg_from_sd(
    "/sd/mountain.jpg",
    0,
    0,
    invert=False,
    dither=True,
    kernel_type=Inkplate.KERNEL_FLOYD_STEINBERG,
)
print("decoded+drew JPEG in {} ms".format(time.ticks_diff(time.ticks_ms(), t0)))

ipk.display()

ipk.sd_card_sleep()
