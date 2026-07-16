"""Turn on the frontlight and ramp its brightness up and down."""

# Include required libraries
from inkplate6plusv2 import Inkplate
import time

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
display.begin()

# Enable the frontlight
display.set_frontlight(True)

# Frontlight brightness can be set from 0 (dimmest) to 63 (brightest)
display.set_frontlight_brightness(0)

# Gradually increase the brightness, then decrease it back down
for i in range(0, 64):
    display.set_frontlight_brightness(i)
    time.sleep(0.05)
for i in range(63, -1, -1):
    display.set_frontlight_brightness(i)
    time.sleep(0.05)

# Turn the frontlight off
display.set_frontlight(False)
