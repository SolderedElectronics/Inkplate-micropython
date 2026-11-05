"""Show a clock on the Inkplate 10, using the real-time clock on the board.

The clock is set to the time of your computer.
Connection: none. The RTC is on the board.
Run it with:  python -m mpremote rtc --set run clock.py

Author: Borna Zelenika @ soldered.com
"""

# Pull in the time module and the Inkplate library
import time
from inkplate10 import Inkplate

# The names of the weekdays, in the same order as the numbers: 0 is Sunday
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Partial update works in black and white mode only
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Start from a clean, fully refreshed screen
inkplate.clear_display()
inkplate.display()

# The font from T1, five times its normal size
inkplate.set_text_size(5)

# Make every sixtieth update a full refresh, about once a minute, to clear the leftovers
inkplate.set_full_update_threshold(59)

# "rtc --set" has put the time of your computer into the board's own clock. Read it.
# The tuple holds the year, month, day, hour, minute, second and weekday.
now = time.localtime()

# MicroPython counts the weekday from Monday = 0. The RTC counts from Sunday = 0.
weekday = (now[6] + 1) % 7

# Send the time and the date to the RTC
inkplate.rtc_set_time(now[3], now[4], now[5])
inkplate.rtc_set_date(weekday, now[2], now[1], now[0])

while True:
    # Read the time and date back from the RTC
    data = inkplate.rtc_get_data()
    inkplate.clear_display()

    # {:02d} prints a number with at least two digits, so 7 shows as 07
    time_text = "{:02d}:{:02d}:{:02d}".format(data["hour"], data["minute"], data["second"])
    date_text = "{:02d}.{:02d}.{}".format(data["day"], data["month"], data["year"])

    # The time, the weekday and the date
    inkplate.print_text(100, 200, time_text)
    inkplate.print_text(100, 340, WEEKDAYS[data["weekday"]])
    inkplate.print_text(100, 480, date_text)

    # Send only what changed
    inkplate.partial_update()

    # An update takes a fraction of a second, so a fixed sleep would let the clock drift
    # and skip seconds. Instead, keep asking the RTC until the second has changed.
    shown_second = data["second"]
    while inkplate.rtc_get_data()["second"] == shown_second:
        pass
