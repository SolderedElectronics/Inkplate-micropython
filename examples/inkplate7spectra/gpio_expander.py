"""Use the GPIO expander's pins to blink an LED."""
# This example shows you how to use the GPIO expander's pins
# See below which pins are available

# Include needed libraries
import time
from pcal6416a import *
from inkplate7spectra import Inkplate

# Create Inkplate object
display = Inkplate()

# Initialize the display, needs to be called only once
display.begin()

# pin = display.gpio_expander_pin(pin,mode)
# Supported modes: mode_input, mode_input_pullup, mode_input_pulldown, mode_output
# Supported pins on Inkplate 7SPECTRA are listed below

expander_p0_0 = display.gpio_expander_pin(0, mode_output)
expander_p0_1 = display.gpio_expander_pin(1, mode_output)
expander_p0_2 = display.gpio_expander_pin(2, mode_output)
expander_p0_3 = display.gpio_expander_pin(3, mode_output)
expander_p0_4 = display.gpio_expander_pin(4, mode_output)
expander_p0_5 = display.gpio_expander_pin(5, mode_output)
expander_p0_6 = display.gpio_expander_pin(6, mode_output)
expander_p0_7 = display.gpio_expander_pin(7, mode_output)

expander_p1_0 = display.gpio_expander_pin(8, mode_output)
expander_p1_1 = display.gpio_expander_pin(9, mode_output)
expander_p1_2 = display.gpio_expander_pin(10, mode_output)
expander_p1_3 = display.gpio_expander_pin(11, mode_output)
expander_p1_4 = display.gpio_expander_pin(12, mode_output)
expander_p1_5 = display.gpio_expander_pin(13, mode_output)
expander_p1_6 = display.gpio_expander_pin(14, mode_output)
expander_p1_7 = display.gpio_expander_pin(15, mode_output)

# Take the previously declared pin 1_5 and blink it
# To see the blinking, attatch a 300Ohm resistor and LED between that pin and GND
while 1:
    expander_p1_5.digital_write(1)
    time.sleep(0.5)
    expander_p1_5.digital_write(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever
