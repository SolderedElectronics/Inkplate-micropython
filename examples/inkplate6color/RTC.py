# FILE: Inkplate6COLOR-RTC.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the onboard RTC to preserve time across reboots
# LAST UPDATED: 2025-08-19

# Include all the required libraries
from inkplate6COLOR import Inkplate
import time

# Create Inkplate object
inkplate = Inkplate()

# Initialize the display, needs to be called only once
inkplate.begin()

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

