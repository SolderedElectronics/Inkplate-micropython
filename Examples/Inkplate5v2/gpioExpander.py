# FILE: Inkplate5v2-gpioExpander.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the GPIO expander's pins
#        to blink an LED
# LAST UPDATED: 2025-08-22
# Include needed libraries
import time
from PCAL6416A import *
from inkplate5v2 import Inkplate

# Create Inkplate object
display = Inkplate(Inkplate.INKPLATE_2BIT)

# Initialize the display, needs to be called only once
display.begin()

# pin = display.gpioExpanderPin(gpioExpander,pin,mode)
# Supported modes: modeINPUT, modeINPUT_PULLUP, modeINPUT_PULLDOWN, modeOUTPUT
# Supported pins on Soldered Inkplate 5 are listed below

# Declare all the available pins as output:

expander_P1_1 = display.gpioExpanderPin(1,9, modeOUTPUT)
expander_P1_2 = display.gpioExpanderPin(1,10, modeOUTPUT)
expander_P1_3 = display.gpioExpanderPin(1,11, modeOUTPUT)
expander_P1_4 = display.gpioExpanderPin(1,12, modeOUTPUT)
expander_P1_5 = display.gpioExpanderPin(1,13, modeOUTPUT)
expander_P1_6 = display.gpioExpanderPin(1,14, modeOUTPUT)
expander_P1_7 = display.gpioExpanderPin(1,15, modeOUTPUT)

# Take the previously declared pin 1_5 and blink it
# To see the blinking, attatch a 300Ohm resistor and LED between that pin and GND
while (1):
    expander_P1_5.digitalWrite(1)
    time.sleep(0.5)
    expander_P1_5.digitalWrite(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever