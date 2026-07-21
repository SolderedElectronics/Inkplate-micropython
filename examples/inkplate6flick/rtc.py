"""Use the onboard RTC to preserve time across reboots."""

# Include all the required libraries
from inkplate6_flick import Inkplate

# Create Inkplate object in 1-bit mode, black and white colors only
# For 8-level grayscale, see basic_grayscale.py
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)


# Initialize the display, needs to be called only once
inkplate.begin()

inkplate.clear_display()

inkplate.display()

inkplate.set_text_size(3)

# This is how to set the RTC's time
# Arguments are hour, minute, seconds
inkplate.rtc_set_time(9, 39, 10)
# And this is the date
# Arguments are weekday, day in month, month and year
inkplate.rtc_set_date(5, 9, 2, 2024)

# Infinite loop
while True:
    inkplate.clear_display()
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

    inkplate.set_cursor(390, 320)
    current_time = str(hour) + ":" + str(minute) + ":" + str(second)
    inkplate.print(current_time)
    inkplate.partial_update()
