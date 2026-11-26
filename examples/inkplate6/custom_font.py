"""Show the same text in two fonts on the Inkplate 6.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library, the font used so far and the second font
from inkplate6 import Inkplate
import gfx_standard_font_01
import free_serif_24px

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# The first font: a label at the normal size, then the text three times bigger
inkplate.set_font(gfx_standard_font_01)
inkplate.set_text_size(1)
inkplate.set_cursor(50, 50)
inkplate.print("Source Sans, the font from T1")
inkplate.set_text_size(3)
inkplate.set_cursor(50, 100)
inkplate.print("Hello World!")

# The second font: the same two lines, lower on the screen
inkplate.set_font(free_serif_24px)
inkplate.set_text_size(1)
inkplate.set_cursor(50, 300)
inkplate.print("FreeSerif, a second font")
inkplate.set_text_size(3)
inkplate.set_cursor(50, 350)
inkplate.print("Hello World!")

# Send the frame buffer to the screen
inkplate.display()
