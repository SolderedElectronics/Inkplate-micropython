# This example will show you how to use the onboard RTC to preserve time across reboots

# Include all the required libraries
from inkplate5 import Inkplate
from soldered_logo import *
import time

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basicGrayscale.py
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Main function
if __name__ == "__main__":
    
    # Initialize the display, needs to be called only once
    display.begin()

    # Clear the frame buffer
    display.clearDisplay()

    # This has to be called every time you want to update the screen
    # Drawing or printing text will have no effect on the display itself before you call this function
    display.display()

    # This is how to set the RTC's time
    # Arguments are hour, minute, seconds
    display.rtcSetTime(9,39,10)
    # And this is the date
    # Arguments are weekday, day in month, month and year
    display.rtcSetDate(5,9,2,2024)

    # Show the set time
    print(display.rtcGetData())

    # Let's wait 10 seconds
    time.sleep(10)

    # Let's see if the time has updated
    print(display.rtcGetData())