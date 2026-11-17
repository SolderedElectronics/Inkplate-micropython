"""Scroll a line of text across a strip of the Inkplate 13 with partial updates.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the library for the clock, and the Inkplate library
import time
from inkplate13_spectra import Inkplate

# The display object
inkplate = Inkplate()

# The text that scrolls
TEXT = "Partial updates!"

# The strip of the screen that changes: top left corner, width and height
STRIP_X = 0
STRIP_Y = 540
STRIP_WIDTH = 1600
STRIP_HEIGHT = 120

# Start the display and turn it to landscape
inkplate.begin()
inkplate.set_rotation(1)

# Start from a clean, fully refreshed screen
inkplate.display()

# Black letters, twice the font's normal size
inkplate.set_text_color(inkplate.BLACK)
inkplate.set_text_size(2)

# Do not wrap text onto the next line when it reaches the edge
inkplate.set_text_wrapping(False)

# Where the text starts on the x axis. It begins left of the screen and slides in.
offset = -420

# How many updates have been sent so far
updates = 0

while True:
    # Clear the strip, then draw the text in its new place
    inkplate.fill_rect(STRIP_X, STRIP_Y, STRIP_WIDTH, STRIP_HEIGHT, inkplate.WHITE)
    inkplate.set_cursor(offset, STRIP_Y + 30)
    inkplate.print(TEXT)

    # Every 20th update is a full refresh. The others send only the strip.
    updates += 1
    if updates % 20 == 0:
        inkplate.display()
    else:
        # The last value keeps the screen's power supply on between updates
        inkplate.display_partial(STRIP_X, STRIP_Y, STRIP_WIDTH, STRIP_HEIGHT, True)

    # Move the text 40 pixels to the right for the next round
    offset += 40

    # When it has left the screen, bring it back to the left
    if offset > 1600:
        offset = -420

    # Wait half a second between updates
    time.sleep_ms(500)
