# FILE: Inkplate6COLOR-gpioExpander.py
# AUTHOR: Soldered
# BRIEF: An example showing how to use the GPIO expander's pins
#        to blink an LED
# LAST UPDATED: 2025-07-30
# This example shows you how to use the GPIO expander's pins
# See below which pins are available

# Include needed libraries
import time
from PCAL6416A import *
from inkplate6COLOR import Inkplate

# Create Inkplate object
display = Inkplate()

# Initialize the display, needs to be called only once
display.begin()

# pin = display.gpioExpanderPin(pin,mode)
# Supported modes: modeINPUT, modeINPUT_PULLUP, modeINPUT_PULLDOWN, modeOUTPUT
# Supported pins on Inkplate 6COLOR COLOR are listed below

expander_P0_0 = display.gpioExpanderPin(0, modeOUTPUT)
expander_P0_1 = display.gpioExpanderPin(1, modeOUTPUT)
expander_P0_2 = display.gpioExpanderPin(2, modeOUTPUT)
expander_P0_3 = display.gpioExpanderPin(3, modeOUTPUT)
expander_P0_4 = display.gpioExpanderPin(4, modeOUTPUT)
expander_P0_5 = display.gpioExpanderPin(5, modeOUTPUT)
expander_P0_6 = display.gpioExpanderPin(6, modeOUTPUT)
expander_P0_7 = display.gpioExpanderPin(7, modeOUTPUT)

expander_P1_0 = display.gpioExpanderPin(8, modeOUTPUT)
expander_P1_1 = display.gpioExpanderPin(9, modeOUTPUT)
expander_P1_2 = display.gpioExpanderPin(10, modeOUTPUT)
expander_P1_3 = display.gpioExpanderPin(11, modeOUTPUT)
expander_P1_4 = display.gpioExpanderPin(12, modeOUTPUT)
expander_P1_5 = display.gpioExpanderPin(13, modeOUTPUT)
expander_P1_6 = display.gpioExpanderPin(14, modeOUTPUT)
expander_P1_7 = display.gpioExpanderPin(15, modeOUTPUT)

# Take the previously declared pin 1_5 and blink it
# To see the blinking, attatch a 300Ohm resistor and LED between that pin and GND
while (1):
    expander_P1_5.digitalWrite(1)
    time.sleep(0.5)
    expander_P1_5.digitalWrite(0)
    time.sleep(0.5)
    # Infinite loop, this goes on forever

