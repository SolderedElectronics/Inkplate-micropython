# FILE: Inkplate10-batteryAndTemperatureRead.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to read the battery voltage
#        as well as its temperature and display it on the screen
# LAST UPDATED: 2025-08-12
# Include needed libraries
from inkplate10 import Inkplate
import time

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basicGrayscale.py
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
    
# Initialize the display, needs to be called only once
inkplate.begin()

# Clear the frame buffer
inkplate.clearDisplay()

# This has to be called every time you want to update the screen
# Drawing or printing text will have no effect on the display itself before you call this function
inkplate.display()

# Get the battery reading as a string
battery = str(inkplate.readBattery())

# Set text size to double from the original size, so we can see the text better
inkplate.setTextSize(2)

# Print the text at coordinates 100,100 (from the upper left corner)
inkplate.printText(350, 350, "Battery voltage: " + battery + "V")

# Show it on the display
inkplate.partialUpdate()

# Get the temperature reading, also as a string
temperature = str(inkplate.readTemperature())

# Print the text at coordinates 100, 150, and also add the measurement unit
inkplate.printText(350, 400, "Temperature: " + temperature + "C")

# Show it on the display
inkplate.partialUpdate()
