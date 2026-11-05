"""Show the wake-up count and reason on the Inkplate 10, then sleep.

Wakes on a 30 second timer or when the WakeUp button is pressed.
Connection: none, the button is on the board. Power and upload over USB-C.
Save it on the board as main.py.

Author: Borna Zelenika @ soldered.com
"""

import time
import machine
import esp32
from machine import Pin
from inkplate10 import Inkplate

# Seconds to sleep if nobody presses the button
SLEEP_S = 30

# Count wake-ups in RTC memory, like in T7
rtc = machine.RTC()
saved = rtc.memory()
if saved:
    wake_count = int(saved.decode()) + 1
else:
    wake_count = 1
rtc.memory(str(wake_count).encode())

# Ask the ESP32 what woke it up
reason = machine.wake_reason()
if reason == machine.EXT0_WAKE:
    reason_text = "WakeUp button"
elif reason == machine.TIMER_WAKE:
    reason_text = "timer"
else:
    # The first power-up is not a wake-up from sleep
    reason_text = "power-up"

inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
inkplate.begin()

# Draw the count and the reason
inkplate.clear_display()
# Size 3, so the longest line, "Woken by: WakeUp button", still fits on the screen
inkplate.set_text_size(3)
inkplate.set_cursor(100, 280)
inkplate.print("Wake-up number " + str(wake_count))
inkplate.set_cursor(100, 360)
inkplate.print("Woken by: " + reason_text)
inkplate.display()

# A window to catch the board awake, so you can upload a new script.
# Pressing the WakeUp button ends the wait early. The pin reads 0 while the button is held down.
button = Pin(36, Pin.IN)
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < 10000 and button.value():
    time.sleep(0.05)

# Wake when GPIO 36, the WakeUp button, goes low
esp32.wake_on_ext0(pin=Pin(36), level=esp32.WAKEUP_ALL_LOW)

# Sleep for 30 seconds, or until the button is pressed
machine.deepsleep(SLEEP_S * 1000)
