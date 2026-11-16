"""Show the eight gray levels of the Inkplate 10 as vertical bars across the screen.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate10 import Inkplate

# Gray mode: eight levels, 0 (black) to 7 (white). The constant is called INKPLATE_2BIT.
inkplate = Inkplate(Inkplate.INKPLATE_2BIT)

# How wide each bar is, in pixels. Eight bars of 150 pixels fill the 1200 pixel screen.
BAR_WIDTH = 150

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# One bar for each gray level
for level in range(8):
    # A solid rectangle: left edge, top edge, width, height, then the gray level
    inkplate.fill_rect(level * BAR_WIDTH, 0, BAR_WIDTH, 825, level)

# Send the frame buffer to the screen
inkplate.display()
