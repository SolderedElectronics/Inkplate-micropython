# FILE: Inkplate10-RTC.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the onboard RTC to preserve time across reboots
# LAST UPDATED: 2025-08-12

# Include all the required libraries
from inkplate10 import Inkplate
import time

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basicGrayscale.py
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

    
# Initialize the display, needs to be called only once
inkplate.begin()

inkplate.clearDisplay()

inkplate.display()

inkplate.setTextSize(2)

# This is how to set the RTC's time
# Arguments are hour, minute, seconds
inkplate.rtcSetTime(9,39,10)
# And this is the date
# Arguments are weekday, day in month, month and year
inkplate.rtcSetDate(5,9,2,2024)

# Infinite loop
while True:
    inkplate.clearDisplay()
    rtcData = inkplate.rtcGetData()
    
    hour = rtcData['hour']
    minute = rtcData['minute']
    second = rtcData['second']
    
    if hour < 10:
        hour="0"+str(hour)
    if minute < 10:
        minute="0"+str(minute)
    if second < 10:
        second="0"+str(second)
    
    inkplate.setCursor(450,300)
    current_time=str(hour)+":"+str(minute)+":"+str(second)
    inkplate.print(current_time)
    inkplate.partialUpdate()

