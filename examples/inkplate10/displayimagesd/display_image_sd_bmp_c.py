"""Decode a BMP from the SD card through the C BMP decode path (24-bit, 1/4/8-bit
indexed, and 16-bit 555/565, docs/refactor_plan.md Phase 7 step 20) with real
Floyd-Steinberg dithering (step 21) and draw it in grayscale.

Calls the high-level draw_bmp_from_sd() (boards/inkplate10/inkplate10.py) -- it wraps the
same inkplate.bmp_draw_gs4() C binding this example called directly before step 43, plus
the file read and a gc.collect() after. Its own file read already uses os.stat +
readinto() into a pre-sized bytearray rather than f.read() -- MicroPython's whole-file
read() grows its buffer geometrically and can transiently need more than the final size,
so it can MemoryError on a file that a single pre-sized allocation of the same size
handles fine (seen on real hardware with this example's own 1.4MB BMP, ~3.3MB free heap
at the time).

Copy a BMP onto the SD card as /sd/coastal.bmp before running this example.
"""

from inkplate10 import Inkplate
from os import stat

ipk = Inkplate(Inkplate.INKPLATE_2BIT)
ipk.begin()
ipk.init_sd_card(fast_boot=True)

IMAGE_PATH = "/sd/coastal.bmp"
try:
    stat(IMAGE_PATH)
except OSError:
    print("Image not found on SD card: {}".format(IMAGE_PATH))
    print("Copy a BMP to that path on the SD card, or change IMAGE_PATH above.")
else:
    # draw_bmp_from_sd() prints its own read/decode/total timing (shared/
    # inkplate_image_gs4_mixin.py) -- no need to time it again here.
    ipk.draw_bmp_from_sd(
        IMAGE_PATH,
        0,
        0,
        invert=False,
        dither=True,
        kernel_type=Inkplate.KERNEL_FLOYD_STEINBERG,
    )

    ipk.display()

ipk.sd_card_sleep()
