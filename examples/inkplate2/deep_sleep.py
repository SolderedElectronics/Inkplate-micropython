"""Enter deep sleep and report the wake reason on the next boot."""

from inkplate2 import Inkplate
import machine
import time

inkplate = Inkplate()

inkplate.begin()

inkplate.clear_display()

# Check for reset reason and print message accordingly
if machine.reset_cause() == machine.DEEPSLEEP_RESET:
    inkplate.println("Woke up from sleep")
else:
    inkplate.println("Cold boot / soft reset")

# Get UTC time
utc_time = time.localtime()

# Convert UTC -> local time (e.g., UTC+2)
# Offset in seconds (hours * 3600)
timezone_offset = (2 * 3600)

# Apply timezone offset and print time
local_time = time.localtime(time.mktime(utc_time) + timezone_offset)
year, month, mday, hour, minute, second, *_ = local_time
inkplate.print(f"{year}-{month:02d}-{mday:02d} {hour:02d}:{minute:02d}:{second:02d}")

inkplate.display()

# Important delay before going to sleep when writing scripts
# Wait 10 seconds so you can 'catch' it awake to upload new code later on
time.sleep(10)

# Deep sleep for 10 seconds (10000 milliseconds)
machine.deepsleep(10000)
