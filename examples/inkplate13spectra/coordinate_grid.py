"""Draw a dotted grid with numbers on the Inkplate 13, to see how the coordinates map to pixels.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate13_spectra import Inkplate

# The display object. Inkplate 13 draws in six colours, and this task uses black and white.
inkplate = Inkplate()

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Turn the screen to landscape, 1600 pixels across and 1200 down. Without this it is the other way round.
inkplate.set_rotation(1)
inkplate.set_text_size(1)

# A vertical dotted line every 100 pixels. draw_pixel(x, y, colour) sets one pixel, and
# a pixel every 8 pixels down the screen makes a dotted line.
for x in range(100, 1600, 100):
    for y in range(0, 1200, 8):
        inkplate.draw_pixel(x, y, inkplate.BLACK)

# The same for the horizontal lines
for y in range(100, 1200, 100):
    for x in range(0, 1600, 8):
        inkplate.draw_pixel(x, y, inkplate.BLACK)

# The x numbers along the top edge, one every 100 pixels, and the y numbers down the
# left edge. Each number starts a few pixels right of and below the position it names.
for x in range(0, 1600, 100):
    inkplate.set_cursor(x + 4, 4)
    inkplate.print(str(x))
for y in range(100, 1200, 100):
    inkplate.set_cursor(4, y + 4)
    inkplate.print(str(y))

# Send the frame buffer to the screen
inkplate.display()
