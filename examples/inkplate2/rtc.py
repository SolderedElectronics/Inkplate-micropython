"""Set the onboard RTC from an NTP server and show the time on the screen."""

from inkplate2 import Inkplate
import network
import ntptime
import time

# WiFi credentials
SSID = ""
PASSWORD = ""

inkplate = Inkplate()

inkplate.begin()

# Connect to WiFi (connection process explained on previous page)
if not do_connect():
    raise SystemExit("WiFi connection failed")

# Sync with NTP server and set the RTC time
try:
    ntptime.settime()
except:
    print("Failed to sync with NTP")

while True:
    # Clear the display buffer and set cursor at upper left corner
    inkplate.clear_display()
    inkplate.set_cursor(0, 0)
        
    # Get UTC time
    utc_time = time.localtime()

    # Convert UTC -> local time (e.g., UTC+2)
    # Offset in seconds (hours * 3600)
    timezone_offset = (2 * 3600)

    # Apply timezone offset
    local_time = time.localtime(time.mktime(utc_time) + timezone_offset)

    # Extract year, month, day, hour, minute, second from the tuple, excludes weekday, yearday
    year, month, mday, hour, minute, second, *_ = local_time
    inkplate.print(f"{year}-{month:02d}-{mday:02d} {hour:02d}:{minute:02d}:{second:02d}")
    
    # Update display
    inkplate.display()
    
    time.sleep(30)
