import time
from PCAL6416A import *

from inkplate7 import Inkplate

display = Inkplate()

# This script demonstrates using all the available GPIO expander pins as output

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()

    # pin = display.gpioExpanderPin(gpioExpander,pin,mode)
    # Supported gpio expanders on Soldered Inkplate 6: 1, 2
    # Supported modes: modeINPUT, modeINPUT_PULLUP, modeINPUT_PULLDOWN, modeOUTPUT
    # Supported pins on Soldered Inkplate 6 are listed below

    expander1_P0_0 = display.gpioExpanderPin(0, modeOUTPUT)
    expander1_P0_1 = display.gpioExpanderPin(1, modeOUTPUT)
    expander1_P0_2 = display.gpioExpanderPin(2, modeOUTPUT)
    expander1_P0_3 = display.gpioExpanderPin(3, modeOUTPUT)
    expander1_P0_4 = display.gpioExpanderPin(4, modeOUTPUT)
    expander1_P0_5 = display.gpioExpanderPin(5, modeOUTPUT)
    expander1_P0_6 = display.gpioExpanderPin(6, modeOUTPUT)
    expander1_P0_7 = display.gpioExpanderPin(7, modeOUTPUT)

    expander1_P1_0 = display.gpioExpanderPin(8, modeOUTPUT)
    expander1_P1_1 = display.gpioExpanderPin(9, modeOUTPUT)
    expander1_P1_2 = display.gpioExpanderPin(10, modeOUTPUT)
    expander1_P1_3 = display.gpioExpanderPin(11, modeOUTPUT)
    expander1_P1_4 = display.gpioExpanderPin(12, modeOUTPUT)
    expander1_P1_5 = display.gpioExpanderPin(13, modeOUTPUT)
    expander1_P1_6 = display.gpioExpanderPin(14, modeOUTPUT)
    expander1_P1_7 = display.gpioExpanderPin(15, modeOUTPUT)

    pins = (expander1_P0_0,
            expander1_P0_1,
            expander1_P0_2,
            expander1_P0_3,
            expander1_P0_4,
            expander1_P0_5,
            expander1_P0_6,
            expander1_P0_7,
            expander1_P1_0,
            expander1_P1_1,
            expander1_P1_2,
            expander1_P1_3,
            expander1_P1_4,
            expander1_P1_5,
            expander1_P1_6,
            expander1_P1_7,
            )
    
    # This example writes a 0.2s pulse on the pins consecutively to test the output

    while (1):
        for pin in pins:
            pin.digitalWrite(1)
            time.sleep(0.2)
            pin.digitalWrite(0)
            time.sleep(0.2)
