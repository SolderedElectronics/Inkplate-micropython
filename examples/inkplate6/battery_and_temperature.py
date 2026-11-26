"""Show the battery voltage and the temperature of the Inkplate 6 in big text, each with its picture.

Connection: none. The sensors are on the board. A battery is optional.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the time module for the pauses, the Inkplate library, and the picture file that sits on the board
import time
from inkplate6 import Inkplate
from symbols import battery_symbol, temperature_symbol

# Partial update works in black and white mode only
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Start from a clean, fully refreshed screen
inkplate.clear_display()
inkplate.display()

# The font from T1, four times its normal size
inkplate.set_text_size(4)

# Make every tenth update a full refresh, to clear the leftovers
inkplate.set_full_update_threshold(9)

while True:
    # Take both measurements
    battery = inkplate.read_battery()
    temperature = inkplate.read_temperature()

    # Round them for the screen: two decimals for the voltage, none for the temperature
    battery_text = "{:.2f}".format(battery)
    temperature_text = "{:.0f}".format(temperature)

    # Redraw the screen: each picture with its number to the right of it
    inkplate.clear_display()
    inkplate.draw_bitmap(151, 105, battery_symbol, 212, 90)
    inkplate.print_text(413, 102, battery_text + " V")
    inkplate.draw_bitmap(219, 341, temperature_symbol, 76, 158)
    inkplate.print_text(413, 372, temperature_text + " C")

    # Send only what changed
    inkplate.partial_update()

    # Wait 10 seconds before the next measurement
    time.sleep(10)
