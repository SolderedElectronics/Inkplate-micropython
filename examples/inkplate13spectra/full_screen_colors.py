"""Fill the whole Inkplate 13 screen with its six colours, as six vertical bars.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate13_spectra import Inkplate

# The display object
inkplate = Inkplate()

# Start the display and turn it to landscape, 1600 pixels across and 1200 down
inkplate.begin()
inkplate.set_rotation(1)

# One bar for each colour. The colours have the numbers 0 to 5: black, white,
# yellow, red, blue and green.
for colour in range(6):
    # A solid rectangle: left edge, top edge, width, height, then the colour number.
    # Every bar is a sixth of the screen wide, plus 2 pixels so that no gap is left.
    inkplate.fill_rect(colour * 1600 // 6, 0, 1600 // 6 + 2, 1200, colour)

# Send the frame buffer to the screen
inkplate.display()
