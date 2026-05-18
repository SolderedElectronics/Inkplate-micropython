# FILE: Inkplate5v2-displayImageSd.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to initialize an SD card and
#        render an image located on it
# LAST UPDATED: 2025-07-30
# Include needed libraries
from inkplate5v2 import Inkplate

from os import listdir

# Create Inkplate object in 2-bit (grayscale) mode
inkplate = Inkplate(Inkplate.INKPLATE_2BIT)

# Initialize the display, needs to be called only once
inkplate.begin()

# Initializes the SD card.
#
# Parameters:
# - fastboot (bool, default=False): 
#     If True, performs a soft reboot immediately after SD card initialization 
#     (only on cold start or hard reset). This significantly improves SD card 
#     read speeds—typically doubling performance.
#
# Note:
# - This function must be called before accessing files on the SD card.
# - The fastboot option has no effect if the device is already running.
inkplate.initSDCard(fastBoot=True)

# This prints all the files on card
print(listdir("/sd"))


# Draw an image on the screen.
#
# Parameters:
# - path: File path to the image. Supports local paths (e.g., from SD card) or URLs.
#         Supported formats: JPG, PNG, BMP.
#
# - x0: X-coordinate of the top-left corner where the image will be displayed.
#
# - y0: Y-coordinate of the top-left corner where the image will be displayed.
#
# - invert (bool, default=False): If True, inverts the image colors.
#
# - dither (bool, default=False): If True, applies a dithering algorithm to the image for better grayscale rendering.
#
# - kernel_type (int): Specifies the dithering algorithm to use.
#     Available options:
#       Inkplate.KERNEL_FLOYD_STEINBERG = 0
#       Inkplate.KERNEL_JJN             = 1
#       Inkplate.KERNEL_STUCKI          = 2
#       Inkplate.KERNEL_BURKES          = 3
#
# Performance Notes:
# - JPG: ~3 seconds (or ~7s with dithering)
# - PNG: ~10 seconds (or ~14s with dithering)
# - BMP: ~15 seconds (or ~20s with dithering)
# - Maximum image file size: ~800kB
#
# Example usage:
inkplate.drawImage("sd/canyon.jpg", 0, 0, invert=False, dither=True, kernel_type=Inkplate.KERNEL_FLOYD_STEINBERG )

# Show the image from the buffer
inkplate.display()

inkplate.SDCardSleep()
# To turn it back on, use:
# inkplate.SDCardWake()