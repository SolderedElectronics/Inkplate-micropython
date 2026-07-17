"""Decode mountain.jpg from the SD card through the C JPEG decode path (ROM tjpgd,
docs/refactor_plan.md Phase 7 step 18) with real Floyd-Steinberg dithering (step 21) and
draw it in grayscale.

Calls the high-level draw_jpg_from_sd() (boards/inkplate10/inkplate10.py) -- it wraps the
same inkplate.jpeg_draw_gs4() C binding this example called directly before step 43, plus
the file read and a gc.collect() after.
"""

from inkplate10 import Inkplate
from os import stat

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

IMAGE_PATH = "/sd/mountain.jpg"
try:
    stat(IMAGE_PATH)
except OSError:
    print("Image not found on SD card: {}".format(IMAGE_PATH))
    print("Copy a JPEG to that path on the SD card, or change IMAGE_PATH above.")
else:
    # draw_jpg_from_sd() prints its own read/decode/total timing (shared/
    # inkplate_image_gs4_mixin.py) -- no need to time it again here.
    ipk.draw_jpg_from_sd(
        IMAGE_PATH,
        0,
        0,
        invert=False,
        dither=True,
        kernel_type=Inkplate.KERNEL_FLOYD_STEINBERG,
    )

    ipk.display()

ipk.sd_card_sleep()
