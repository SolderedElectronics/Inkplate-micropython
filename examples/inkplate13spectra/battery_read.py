"""Show the battery voltage of the Inkplate 13 in big text, next to a battery picture.

Connection: none. The measurement is on the board. A battery is optional.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the library for the clock, the Inkplate library and the battery picture from symbols.py
import time
from inkplate13_spectra import Inkplate
from symbols import battery_symbol

# The display object
inkplate = Inkplate()

# The strip of the screen that shows the voltage: top left corner, width and height
STRIP_X = 0
STRIP_Y = 500
STRIP_WIDTH = 1600
STRIP_HEIGHT = 200

# Start the display and turn it to landscape
inkplate.begin()
inkplate.set_rotation(1)

# Start from a clean, fully refreshed screen
inkplate.display()

# Black text, four times the font's normal size
inkplate.set_text_color(inkplate.BLACK)
inkplate.set_text_size(4)

# How many measurements have been shown so far
updates = 0

while True:
    # Take the measurement
    voltage = inkplate.read_battery()

    # Clear the strip, then draw the picture and write the voltage to the right of it. "{:.2f}" gives two decimals.
    inkplate.fill_rect(STRIP_X, STRIP_Y, STRIP_WIDTH, STRIP_HEIGHT, inkplate.WHITE)
    inkplate.draw_bitmap(554, 555, battery_symbol, 212, 90, inkplate.BLACK)
    inkplate.set_cursor(810, STRIP_Y + 60)
    inkplate.print("{:.2f} V".format(voltage))

    # Every 10th update is a full refresh. The others send only the strip.
    updates += 1
    if updates % 10 == 0:
        inkplate.display()
    else:
        inkplate.display_partial(STRIP_X, STRIP_Y, STRIP_WIDTH, STRIP_HEIGHT, True)

    # Wait 10 seconds before the next measurement
    time.sleep(10)
