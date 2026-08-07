"""Count deep sleep cycles using RTC memory and show the count on the screen."""

from inkplate6_color import Inkplate
import machine
import time

# Create a RTC object that stores states between deep sleep cycles
rtc = machine.RTC()

# Read stored bytes from memory
raw = rtc.memory()

# If we have at least 1 stored byte, set as counter,
# otherwise start from 0
count = raw[0] if raw and len(raw) >= 1 else 0

inkplate = Inkplate()

inkplate.begin()

inkplate.clear_display()

# Check for reset reason and print message accordingly
if machine.reset_cause() == machine.DEEPSLEEP_RESET:
    inkplate.println("Woke up from sleep")
    # Increment counter
    count = count + 1
else:
    count = 1
    inkplate.println("Cold boot / soft reset")

# Write one byte back to RTC memory
rtc.memory(bytes([count]))

inkplate.print(f"Count: {count}")
inkplate.display()

# Important delay before going to sleep when writing scripts
# Wait 10 seconds so you can 'catch' it awake to upload new code later on
time.sleep(10)

# Deep sleep for 10 seconds (10000 milliseconds)
machine.deepsleep(10000)
