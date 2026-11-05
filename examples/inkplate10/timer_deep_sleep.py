"""Show a wake-up counter on the Inkplate 10, then sleep for 20 seconds.

Connection: none, the screen is on the board. Power and upload over USB-C.
Save it on the board as main.py, so it runs again after every wake-up.

Author: Borna Zelenika @ soldered.com
"""

import time
import machine
from inkplate10 import Inkplate

# How long to sleep, in milliseconds
SLEEP_MS = 20000

# RTC memory keeps its content through deep sleep
rtc = machine.RTC()

# Read the old count. On the first start the memory is empty, so we start at 1.
saved = rtc.memory()
if saved:
    wake_count = int(saved.decode()) + 1
else:
    wake_count = 1

# Store the new count, as bytes
rtc.memory(str(wake_count).encode())

inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
inkplate.begin()

# Draw the counter
inkplate.clear_display()
inkplate.set_text_size(3)
inkplate.set_cursor(100, 300)
inkplate.print("Wake-up number " + str(wake_count))

# A full refresh. The picture stays on the screen while the board sleeps.
inkplate.display()

# A window to catch the board awake, so you can upload a new script
time.sleep(10)

# Go to sleep. The board restarts from the top when the time is up.
machine.deepsleep(SLEEP_MS)
