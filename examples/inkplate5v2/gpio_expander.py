"""Use the GPIO expander's pins to blink an LED."""

# Include needed libraries
import time
from pcal6416a import *
from inkplate5v2 import Inkplate

# Create Inkplate object
display = Inkplate(Inkplate.INKPLATE_2BIT)

# Initialize the display, needs to be called only once
display.begin()

# pin = display.gpio_expander_pin(gpioExpander,pin,mode)
# Supported modes: mode_input, mode_input_pullup, mode_input_pulldown, mode_output
# Supported pins on Soldered Inkplate 5 are listed below
#
# NOTE: pin 10 is reserved for SD_ENABLE (uSD card power) -- not available for
# general use.

# Declare all the available pins as output:

expander_p1_1 = display.gpio_expander_pin(1, 9, mode_output)
expander_p1_3 = display.gpio_expander_pin(1, 11, mode_output)
expander_p1_4 = display.gpio_expander_pin(1, 12, mode_output)
expander_p1_5 = display.gpio_expander_pin(1, 13, mode_output)
expander_p1_6 = display.gpio_expander_pin(1, 14, mode_output)
expander_p1_7 = display.gpio_expander_pin(1, 15, mode_output)

# Take the previously declared pin 1_5 and blink it
# To see the blinking, attatch a 300Ohm resistor and LED between that pin and GND
while 1:
    expander_p1_5.digital_write(1)
    time.sleep(0.5)
    expander_p1_5.digital_write(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever
