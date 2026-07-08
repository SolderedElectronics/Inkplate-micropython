"""Uses a GPIO pin to blink an LED."""

# Include needed libraries
import time
from inkplate2 import Inkplate
from machine import Pin

# Create Inkplate object
inkplate = Inkplate()

# Declare the IO4 pin as an output (connect the LED to this pin with a resistor)
led_pin = Pin(4, Pin.OUT)

# Initialize the display, needs to be called only once
inkplate.begin()


while 1:
    led_pin.value(1)
    time.sleep(0.5)
    led_pin.value(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever
