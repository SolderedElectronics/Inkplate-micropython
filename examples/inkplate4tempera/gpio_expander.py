"""Use the GPIO expander's pins to blink an LED."""

# Include needed libraries
import time
from pcal6416a import *
from inkplate4tempera import Inkplate

# Create Inkplate object in 1-bit mode, black and white colors only
# For 8-level grayscale, see basic_grayscale.py
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)


# Initialize the display, needs to be called only once
inkplate.begin()

# pin = inkplate.gpio_expander_pin(gpioExpander,pin,mode)
# Supported gpio expanders on Inkplate 4TEMPERA: 1, 2 (internal, external)
# Supported modes: mode_input, mode_input_pullup, mode_input_pulldown, mode_output
#
# NOTE: unlike Inkplate6/6FLICK/6PLUSV2/5v2/10, expander 1 on Inkplate4TEMPERA
# reserves pins 0-5 (EPD/TPS control lines), 11 (SD_ENABLE), and 15 (fuel gauge
# GPOUT) for onboard peripherals -- only pins 6-10, 12-14 are free for general
# use. Expander 2 has no reserved pins on this board.

# Declare the available expander-1 pins as output (6-10, 12-14 only):

expander1_p0_6 = inkplate.gpio_expander_pin(1, 6, mode_output)
expander1_p0_7 = inkplate.gpio_expander_pin(1, 7, mode_output)
expander1_p1_0 = inkplate.gpio_expander_pin(1, 8, mode_output)
expander1_p1_1 = inkplate.gpio_expander_pin(1, 9, mode_output)
expander1_p1_2 = inkplate.gpio_expander_pin(1, 10, mode_output)
expander1_p1_4 = inkplate.gpio_expander_pin(1, 12, mode_output)
expander1_p1_5 = inkplate.gpio_expander_pin(1, 13, mode_output)
expander1_p1_6 = inkplate.gpio_expander_pin(1, 14, mode_output)

# Declare all the available pins on expander 2 as output:

expander2_p0_0 = inkplate.gpio_expander_pin(2, 0, mode_output)
expander2_p0_1 = inkplate.gpio_expander_pin(2, 1, mode_output)
expander2_p0_2 = inkplate.gpio_expander_pin(2, 2, mode_output)
expander2_p0_3 = inkplate.gpio_expander_pin(2, 3, mode_output)
expander2_p0_4 = inkplate.gpio_expander_pin(2, 4, mode_output)
expander2_p0_5 = inkplate.gpio_expander_pin(2, 5, mode_output)
expander2_p0_6 = inkplate.gpio_expander_pin(2, 6, mode_output)
expander2_p0_7 = inkplate.gpio_expander_pin(2, 7, mode_output)

expander2_p1_0 = inkplate.gpio_expander_pin(2, 8, mode_output)
expander2_p1_1 = inkplate.gpio_expander_pin(2, 9, mode_output)
expander2_p1_2 = inkplate.gpio_expander_pin(2, 10, mode_output)
expander2_p1_3 = inkplate.gpio_expander_pin(2, 11, mode_output)
expander2_p1_4 = inkplate.gpio_expander_pin(2, 12, mode_output)
expander2_p1_5 = inkplate.gpio_expander_pin(2, 13, mode_output)
expander2_p1_6 = inkplate.gpio_expander_pin(2, 14, mode_output)
expander2_p1_7 = inkplate.gpio_expander_pin(2, 15, mode_output)

# Take the previously declared pin 1_5 on expander 2 and blink it
# To see the blinking, attatch a 300Ohm resistor and LED between that pin and GND
while 1:
    expander2_p1_5.digital_write(1)
    time.sleep(0.5)
    expander2_p1_5.digital_write(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever
