# FILE: Inkplate6-RTC.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the onboard RTC to preserve time across reboots
# LAST UPDATED: 2025-07-29

# Include all the required libraries
from inkplate6 import Inkplate
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

# This is how to set the RTC's time
# Arguments are hour, minute, seconds
inkplate.rtcSetTime(9,39,10)
# And this is the date
# Arguments are weekday, day in month, month and year
inkplate.rtcSetDate(5,9,2,2024)

# Infinite loop
while True:

    # Show the set time
    print(inkplate.rtcGetData())

    # Let's wait 10 seconds
    time.sleep(10)
