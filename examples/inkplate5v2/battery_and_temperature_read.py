# FILE: Inkplate5v2-battery_and_temperature_read.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to read the battery voltage
#        as well as its temperature and display it on the screen
# LAST UPDATED: 2025-08-22
# Include needed libraries
from inkplate5v2 import Inkplate

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basic_grayscale.py
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
inkplate.begin()

# Clear the frame buffer
inkplate.clear_display()

# This has to be called every time you want to update the screen
# Drawing or printing text will have no effect on the display itself before you call this function
inkplate.display()

# Get the battery reading as a string
battery = str(inkplate.read_battery())

# Set text size to double from the original size, so we can see the text better
inkplate.set_text_size(2)

# Print the text at coordinates 100,100 (from the upper left corner)
inkplate.print_text(100, 100, "Battery voltage: " + battery + "V")

# Show it on the display
inkplate.partial_update()

# Get the temperature reading, also as a string
temperature = str(inkplate.read_temperature())

# Print the text at coordinates 100, 150, and also add the measurement unit
inkplate.print_text(100, 150, "Temperature: " + temperature + "C")

# Show it on the display
inkplate.partial_update()
