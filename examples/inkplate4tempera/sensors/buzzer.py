"""Beep the buzzer at a few different frequencies."""

# Include required libraries
from inkplate4tempera import Inkplate
import time

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
display.begin()

# Beep for 200ms at the default frequency
display.beep(200)
time.sleep(0.5)

# Beep for 200ms at a few frequencies across the buzzer's supported range (572-2933Hz)
for freq in (600, 1200, 1800, 2400, 2900):
    display.beep(200, freq)
    time.sleep(0.3)

# beep_on()/beep_off() are also available for non-blocking control
display.beep_on(1000)
time.sleep(0.5)
display.beep_off()
