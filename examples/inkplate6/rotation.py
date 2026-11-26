"""Draw the grid of T1 on the Inkplate 6 with the screen turned upright.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate6 import Inkplate

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Turn the screen upright. Do this before anything is drawn.
inkplate.set_rotation(3)
inkplate.set_text_size(1)

# A vertical dotted line every 100 pixels. width() and height() give the size of the
# turned screen, so the loops fit it without writing the numbers in.
for x in range(100, inkplate.width(), 100):
    for y in range(0, inkplate.height(), 8):
        inkplate.draw_pixel(x, y, inkplate.BLACK)

# The same for the horizontal lines
for y in range(100, inkplate.height(), 100):
    for x in range(0, inkplate.width(), 8):
        inkplate.draw_pixel(x, y, inkplate.BLACK)

# The x numbers along the top edge and the y numbers down the left edge
for x in range(0, inkplate.width(), 100):
    inkplate.set_cursor(x + 4, 4)
    inkplate.print(str(x))
for y in range(100, inkplate.height(), 100):
    inkplate.set_cursor(4, y + 4)
    inkplate.print(str(y))

# Send the frame buffer to the screen
inkplate.display()
