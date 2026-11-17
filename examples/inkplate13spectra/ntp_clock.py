"""Set the real-time clock of the Inkplate 13 from the internet, then show the time.

Connection: none. Needs a Wi-Fi network, but only for the first few seconds.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the modules for the pauses, the Wi-Fi, the time from the internet, and the Inkplate library
import time
import network
import ntptime
from inkplate13_spectra import Inkplate

# The name and the password of your Wi-Fi network
ssid = ""
password = ""

# The names of the weekdays, in the same order as the numbers: 0 is Sunday
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# The display object
inkplate = Inkplate()

# The strip of the screen that holds the clock: top left corner, width and height
STRIP_X = 0
STRIP_Y = 300
STRIP_WIDTH = 1600
STRIP_HEIGHT = 600


# Stop with a message on the screen
def fail(message):
    inkplate.print_text(100, 200, message)
    inkplate.display()
    raise SystemExit


# The day of the month of the last Sunday of a month with 31 days. Start at the 31st and
# step back until the day is a Sunday. In MicroPython Sunday is 6.
def last_sunday(year, month):
    day = 31
    while time.gmtime(time.mktime((year, month, day, 0, 0, 0, 0, 0)))[6] != 6:
        day -= 1
    return day


# Central Europe is one hour ahead of UTC, and two hours ahead in summer. Summer time starts
# on the last Sunday of March and ends on the last Sunday of October, both at 01:00 UTC.
def central_europe_offset(utc_seconds):
    year = time.gmtime(utc_seconds)[0]
    summer_start = time.mktime((year, 3, last_sunday(year, 3), 1, 0, 0, 0, 0))
    summer_end = time.mktime((year, 10, last_sunday(year, 10), 1, 0, 0, 0, 0))
    if summer_start <= utc_seconds < summer_end:
        return 2 * 3600
    return 1 * 3600


# Start the display and turn it to landscape. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_rotation(1)

# Black text, five times the font's normal size
inkplate.set_text_color(inkplate.BLACK)
inkplate.set_text_size(5)

# Join the Wi-Fi network
station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)
while not station.isconnected():
    time.sleep(0.5)

# Ask the internet for the time. This is called NTP. settime() puts the time, in UTC,
# into the board's own clock. If no answer arrives it raises an OSError.
try:
    ntptime.settime()
except OSError:
    fail("No time from the internet")

# The clock is set, so the Wi-Fi is not needed any more. Turn it off to save power.
station.disconnect()
station.active(False)

# Turn the UTC time into local time, and split it into year, month, day, hour, minute,
# second and weekday. MicroPython counts the weekday from Monday = 0.
utc_seconds = time.time()
now = time.gmtime(utc_seconds + central_europe_offset(utc_seconds))

# The RTC counts the weekday from Sunday = 0, so convert it. Then send the time and date to the RTC.
weekday = (now[6] + 1) % 7
inkplate.rtc_set_time(now[3], now[4], now[5])
inkplate.rtc_set_date(weekday, now[2], now[1], now[0])

# Start from a clean, fully refreshed screen
inkplate.clear_display()
inkplate.display()

# How many updates have been sent so far
updates = 0

while True:
    # Read the time and date from the RTC
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

    # Keep asking the RTC until the minute has changed
    shown_minute = data["minute"]
    while inkplate.rtc_get_data()["minute"] == shown_minute:
        time.sleep(1)
