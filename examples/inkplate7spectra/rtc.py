"""Use the onboard RTC."""

# Include all the required libraries
from inkplate7spectra import Inkplate
import time

# Create Inkplate object
inkplate = Inkplate()

# Initialize the display, needs to be called only once
inkplate.begin()

inkplate.set_text_size(3)

# This is how to set the RTC's time
# Arguments are hour, minute, seconds
inkplate.rtc_set_time(9, 39, 10)
# And this is the date
# Arguments are weekday, day in month, month and year
inkplate.rtc_set_date(2, 9, 2, 2026)

# Box that the time text is drawn into -- must be cleared before each redraw,
# since we redraw the whole screen every tick (this board has no partial-
# refresh support)
box_x, box_y, box_w, box_h = 100, 100, 300, 60

# Infinite loop
while True:
    rtc_data = inkplate.rtc_get_data()

    hour = rtc_data["hour"]
    minute = rtc_data["minute"]
    second = rtc_data["second"]

    if hour < 10:
        hour = "0" + str(hour)
    if minute < 10:
        minute = "0" + str(minute)
    if second < 10:
        second = "0" + str(second)

    inkplate.fill_rect(box_x, box_y, box_w, box_h, inkplate.WHITE)
    inkplate.set_cursor(box_x, box_y)
    current_time = str(hour) + ":" + str(minute) + ":" + str(second)
    inkplate.print(current_time)
    inkplate.display()

    # Let's wait 10 seconds
    time.sleep(10)
