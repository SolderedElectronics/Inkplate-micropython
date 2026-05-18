# FILE: Inkplate6FLICK-frontlight.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to adjust the frontlight
# LAST UPDATED: 2025-08-27

# Include required libraries
from inkplate6FLICK import Inkplate
import time

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

    
# Initialize the display, needs to be called only once
display.begin()

# Clear the frame buffer
display.clearDisplay()

# This has to be called every time you want to update the screen
# Drawing or printing text will have no effect on the display itself before you call this function
display.display()

# Enable the frontlight
display.frontlight(True)

display.display()


# Frontlight strenght can be set from values 0 to 64
# For example:
display.setFrontlight(0)

# Slowly gradually increase the frontlight and then decrease it
# First, increase the brightness gradually
for i in range(0, 64):
    display.setFrontlight(i)
    time.sleep(0.5) # Wait for 500ms
# Then, decrease
for v in range(0, 64):
    display.setFrontlight(60-v)
    time.sleep(0.5) # Wait for 500ms

# Turn it off
display.frontlight(False)

