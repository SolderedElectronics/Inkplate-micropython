"""Show the battery voltage and the temperature in big text on the Inkplate 10.

Connection: none. The sensors are on the board. A battery is optional.

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

    # Redraw the screen. print_text() writes at the position you give it.
    inkplate.clear_display()
    inkplate.print_text(120, 280, "Battery: " + battery_text + " V")
    inkplate.print_text(120, 420, "Temperature: " + temperature_text + " C")

    # Send only what changed
    inkplate.partial_update()

    # Wait 10 seconds before the next measurement
    time.sleep(10)
