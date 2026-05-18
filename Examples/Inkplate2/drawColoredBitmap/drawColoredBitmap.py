# FILE: Inkplate2-drawColoredBitmap.py
# AUTHOR: Soldered
# BRIEF: An example showing how to draw a colored bitmap which is stored in flash memory
# LAST UPDATED: 2025-08-12
from inkplate2 import Inkplate

# Import the bytearray containing the image from the demo_image.py file
from demo_image import *

# Create Inkplate object
display = Inkplate()

# Initialize the display
display.begin()

# Draw a colored bitmap to the screen from flash memory.
#
# Parameters:
# - x: X-coordinate of the top-left corner where the image will be displayed.
#
# - y: Y-coordinate of the top-left corner where the image will be displayed.
#
# - w: If True, inverts the image colors.
#
# - h: If True, applies a dithering algorithm to the image for better grayscale rendering.
#
# - data: The bitmap stored in flash in the form of a bytearray (see below)
display.drawColorBitmap(0,0,212,104,demo_image)

# Display the drawn image onto the screen
display.display()

