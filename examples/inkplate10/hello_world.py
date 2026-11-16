"""Show "Hello World!" on the Inkplate 10 e-paper display.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate10 import Inkplate

# Create the display object. INKPLATE_1BIT means black and white only.
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display hardware. Call this once, at the start.
inkplate.begin()

# The empty frame buffer is white. begin() has already cleared it.

# Where the text starts: 10 pixels from the left, 10 from the top
inkplate.set_cursor(10, 10)

# The built-in letters are 24 pixels tall. Size 3 makes them three times bigger.
inkplate.set_text_size(3)

# Write the text into the frame buffer
inkplate.print("Hello World!")

# Send the frame buffer to the screen
inkplate.display()
