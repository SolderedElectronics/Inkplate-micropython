"""Write a line in the built-in font and a line in the FreeSerif font on the Inkplate 13, to compare them.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip
Font:       free_serif_48px, installed with
            mpremote mip install github:SolderedElectronics/Inkplate-micropython/fonts/free_serif_48px.py

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library, then the serif font you put on the board
from inkplate13_spectra import Inkplate
import free_serif_48px

# The display object
inkplate = Inkplate()

# Start the display and turn it to landscape. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_rotation(1)
inkplate.set_text_color(inkplate.BLACK)

# The first line, in the built-in font. Size 3 makes its letters three times bigger.
inkplate.set_text_size(3)
inkplate.set_cursor(180, 180)
inkplate.print("Default font")

# Select the serif font. It is already big, so size 1 is enough.
inkplate.set_font(free_serif_48px)
inkplate.set_text_size(1)
inkplate.set_cursor(180, 330)
inkplate.print("Serif font!")

# Send the frame buffer to the screen
inkplate.display()
