"""Decode a PNG from the SD card through the C PNG decode path (vendored pngle, ROM
miniz/tinfl) with Floyd-Steinberg dithering and draw it in grayscale. Alpha is ignored
(treated fully opaque).

Calls the high-level draw_png_from_sd() (boards/inkplate10/inkplate10.py), which wraps
the inkplate.png_draw_gs4() C binding plus the file read and a gc.collect() after.

Copy any PNG onto the SD card as /sd/image.png before running this example -- no
sample PNG ships in this repo (the JPEG example ships its own sample instead).
"""

from inkplate10 import Inkplate
from os import stat

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

IMAGE_PATH = "/sd/image.png"
try:
    stat(IMAGE_PATH)
except OSError:
    print("Image not found on SD card: {}".format(IMAGE_PATH))
    print("Copy a PNG to that path on the SD card, or change IMAGE_PATH above.")
else:
    # draw_png_from_sd() prints its own read/decode/total timing (shared/mixins/
    # inkplate_image_gs4_mixin.py) -- no need to time it again here.
    ipk.draw_png_from_sd(
        IMAGE_PATH,
        0,
        0,
        invert=False,
        dither=True,
        kernel_type=Inkplate.KERNEL_FLOYD_STEINBERG,
    )

    ipk.display()

ipk.sd_card_sleep()
