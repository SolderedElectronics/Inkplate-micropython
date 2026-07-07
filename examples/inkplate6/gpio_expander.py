# FILE: Inkplate6-gpioExpander.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the GPIO expander's pins
#        to blink an LED
# LAST UPDATED: 2025-07-30

# Include needed libraries
import time
from PCAL6416A import *
from inkplate6 import Inkplate

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basicGrayscale.py
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)


# Initialize the display, needs to be called only once
inkplate.begin()

# pin = inkplate.gpioExpanderPin(gpioExpander,pin,mode)
# Supported gpio expanders on Inkplate 6: 1, 2 (internal, external)
# Supported modes: modeINPUT, modeINPUT_PULLUP, modeINPUT_PULLDOWN, modeOUTPUT
# Supported pins on Inkplate 6 are listed below

# Declare all the available pins as output:

expander1_P1_1 = inkplate.gpioExpanderPin(1, 9, modeOUTPUT)
expander1_P1_2 = inkplate.gpioExpanderPin(1, 10, modeOUTPUT)
expander1_P1_3 = inkplate.gpioExpanderPin(1, 11, modeOUTPUT)
expander1_P1_4 = inkplate.gpioExpanderPin(1, 12, modeOUTPUT)
expander1_P1_5 = inkplate.gpioExpanderPin(1, 13, modeOUTPUT)
expander1_P1_6 = inkplate.gpioExpanderPin(1, 14, modeOUTPUT)
expander1_P1_7 = inkplate.gpioExpanderPin(1, 15, modeOUTPUT)

expander2_P0_0 = inkplate.gpioExpanderPin(2, 0, modeOUTPUT)
expander2_P0_1 = inkplate.gpioExpanderPin(2, 1, modeOUTPUT)
expander2_P0_2 = inkplate.gpioExpanderPin(2, 2, modeOUTPUT)
expander2_P0_3 = inkplate.gpioExpanderPin(2, 3, modeOUTPUT)
expander2_P0_4 = inkplate.gpioExpanderPin(2, 4, modeOUTPUT)
expander2_P0_5 = inkplate.gpioExpanderPin(2, 5, modeOUTPUT)
expander2_P0_6 = inkplate.gpioExpanderPin(2, 6, modeOUTPUT)
expander2_P0_7 = inkplate.gpioExpanderPin(2, 7, modeOUTPUT)

expander2_P1_0 = inkplate.gpioExpanderPin(2, 8, modeOUTPUT)
expander2_P1_1 = inkplate.gpioExpanderPin(2, 9, modeOUTPUT)
expander2_P1_2 = inkplate.gpioExpanderPin(2, 10, modeOUTPUT)
expander2_P1_3 = inkplate.gpioExpanderPin(2, 11, modeOUTPUT)
expander2_P1_4 = inkplate.gpioExpanderPin(2, 12, modeOUTPUT)
expander2_P1_5 = inkplate.gpioExpanderPin(2, 13, modeOUTPUT)
expander2_P1_6 = inkplate.gpioExpanderPin(2, 14, modeOUTPUT)
expander2_P1_7 = inkplate.gpioExpanderPin(2, 15, modeOUTPUT)

# Take the previously declared pin 1_5 on expander 2 and blink it
# To see the blinking, attatch a 300Ohm resistor and LED between that pin and GND
while (1):
    expander2_P1_5.digitalWrite(1)
    time.sleep(0.5)
    expander2_P1_5.digitalWrite(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever