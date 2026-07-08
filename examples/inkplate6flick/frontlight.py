"""Adjust the frontlight."""

# Include required libraries
from inkplate6_flick import Inkplate
import time

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)


# Initialize the display, needs to be called only once
display.begin()

# Clear the frame buffer
display.clear_display()

# This has to be called every time you want to update the screen
# Drawing or printing text will have no effect on the display itself before you call this function
display.display()

# Enable the frontlight
display.frontlight(True)

display.display()


# Frontlight strenght can be set from values 0 to 64
# For example:
display.set_frontlight(0)

# Slowly gradually increase the frontlight and then decrease it
# First, increase the brightness gradually
for i in range(0, 64):
    display.set_frontlight(i)
    time.sleep(0.5)  # Wait for 500ms
# Then, decrease
for v in range(0, 64):
    display.set_frontlight(60 - v)
    time.sleep(0.5)  # Wait for 500ms

# Turn it off
display.frontlight(False)
