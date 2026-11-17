"""Scroll a line of text across the Inkplate 10 with partial updates.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the time module for the pauses, and the Inkplate library
import time
from inkplate10 import Inkplate

# Partial update works in black and white mode only
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Start from a clean, fully refreshed screen
inkplate.clear_display()
inkplate.display()

# Twice the size of the font's normal letters
inkplate.set_text_size(2)

# Do not wrap text onto the next line when it reaches the edge
inkplate.set_text_wrapping(False)

# Make every 30th update a full refresh, to clear the leftovers
inkplate.set_full_update_threshold(29)

# The text that scrolls
text = "Partial updates!"

# Where the text starts on the x axis. It begins left of the screen and slides in.
offset = -320

while True:
    # Redraw the text in its new place
    inkplate.clear_display()
    inkplate.set_cursor(offset, 360)
    inkplate.print(text)

    # Update only what changed
    inkplate.partial_update()

    # Move the text 15 pixels to the right for the next round
    offset += 15

    # When it has left the screen, bring it back to the left
    if offset > 1200:
        offset = -320

    # Wait half a second between updates
    time.sleep(0.5)
