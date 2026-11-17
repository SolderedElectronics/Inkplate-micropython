"""Show "Hello World!" on the Inkplate 13 e-paper display.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip (see the Set up the board page)

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate13_spectra import Inkplate

# Create the display object
inkplate = Inkplate()

# Start the display hardware. Call this once, at the start.
inkplate.begin()

# Turn the screen to landscape, 1600 pixels across and 1200 down
inkplate.set_rotation(1)

# Letters are black unless you pick another colour
inkplate.set_text_color(inkplate.BLACK)

# Where the text starts: 10 pixels from the left, 10 from the top
inkplate.set_cursor(10, 10)

# The built-in letters are 24 pixels tall. Size 3 makes them three times bigger.
inkplate.set_text_size(3)

# Write the text into the frame buffer
inkplate.print("Hello World!")

# Send the frame buffer to the screen
inkplate.display()
