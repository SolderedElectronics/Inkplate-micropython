"""Show a clock on the Inkplate 13, using the real-time clock on the board.
The clock is set to the time of your computer.

Connection: none. The RTC is on the board.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip
Run it with:  python -m mpremote rtc --set run clock.py

Author: Borna Zelenika @ soldered.com
"""

# Pull in the time module and the Inkplate library
import time
from inkplate13_spectra import Inkplate

# The names of the weekdays, in the same order as the numbers: 0 is Sunday
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# The strip of the screen that holds the clock: top left corner, width and height
STRIP_X = 0
STRIP_Y = 300
STRIP_WIDTH = 1600
STRIP_HEIGHT = 600

# The display object
inkplate = Inkplate()

# Start the display and turn it to landscape
inkplate.begin()
inkplate.set_rotation(1)

# Start from a clean, fully refreshed screen
inkplate.display()

# Black text, five times the font's normal size
inkplate.set_text_color(inkplate.BLACK)
inkplate.set_text_size(5)

# "rtc --set" has put the time of your computer into the board's own clock. Read it.
# The tuple holds the year, month, day, hour, minute, second and weekday.
now = time.localtime()

# MicroPython counts the weekday from Monday = 0. The RTC counts from Sunday = 0.
weekday = (now[6] + 1) % 7

# Send the time and the date to the RTC
inkplate.rtc_set_time(now[3], now[4], now[5])
inkplate.rtc_set_date(weekday, now[2], now[1], now[0])

# How many updates have been sent so far
updates = 0

while True:
    # Read the time and date back from the RTC
    data = inkplate.rtc_get_data()

    # Clear the strip, then draw the clock into it
    inkplate.fill_rect(STRIP_X, STRIP_Y, STRIP_WIDTH, STRIP_HEIGHT, inkplate.WHITE)

    # {:02d} prints a number with at least two digits, so 7 shows as 07
    time_text = "{:02d}:{:02d}".format(data["hour"], data["minute"])
    date_text = "{:02d}.{:02d}.{}".format(data["day"], data["month"], data["year"])

    # The time, the weekday and the date
    inkplate.print_text(100, 350, time_text)
    inkplate.print_text(100, 540, WEEKDAYS[data["weekday"]])
    inkplate.print_text(100, 730, date_text)

    # Every 60th update is a full refresh. The others send only the strip.
    updates += 1
    if updates % 60 == 0:
        inkplate.display()
    else:
        inkplate.display_partial(STRIP_X, STRIP_Y, STRIP_WIDTH, STRIP_HEIGHT, True)

    # Keep asking the RTC until the minute has changed, then draw the next frame
    shown_minute = data["minute"]
    while inkplate.rtc_get_data()["minute"] == shown_minute:
        time.sleep(1)
