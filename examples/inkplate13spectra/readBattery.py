# FILE: readBattery.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to read the battery voltage
# LAST UPDATED: 2026-02-09
# Include needed libraries
from inkplate13SPECTRA import Inkplate

# Creates an Inkplate object
inkplate = Inkplate()
    
# Initialize the display, needs to be called only once
inkplate.begin()

# Get the battery reading as a string
battery = str(inkplate.readBattery())

# Set text size to double from the original size, so we can see the text better
inkplate.setTextSize(2)

# Print the text at coordinates 100,100 (from the upper left corner)
inkplate.printText(100, 100, "Battery voltage: " + battery + "V")

# Show it on the display
inkplate.display()