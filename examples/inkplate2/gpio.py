# FILE: Inkplate2-gpio.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the GPIO pins
#        to blink an LED
# LAST UPDATED: 2025-08-12

# Include needed libraries
import time
from inkplate2 import Inkplate
from machine import Pin

# Create Inkplate object 
inkplate = Inkplate()

# Declare the IO4 pin as an output (connect the LED to this pin with a resistor)
ledPin=Pin(4,Pin.OUT)

# Initialize the display, needs to be called only once
inkplate.begin()


while (1):
    ledPin.value(1)
    time.sleep(0.5)
    ledPin.value(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever