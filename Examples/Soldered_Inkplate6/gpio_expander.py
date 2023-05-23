import time
from PCAL6416A import *

from soldered_inkplate6 import Inkplate

display = Inkplate(Inkplate.INKPLATE_1BIT)

# This script demonstrates using all the available GPIO expander pins as output

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()

    # pin = display.gpioExpanderPin(gpioExpander,pin,mode)
    # Supported gpio expanders on Soldered Inkplate 10: 1, 2
    # Supported modes: modeINPUT, modeINPUT_PULLUP, modeINPUT_PULLDOWN, modeOUTPUT
    # Supported pins on Soldered Inkplate 10 are listed below

    expander1_P1_1 = display.gpioExpanderPin(1, 9, modeOUTPUT)
    expander1_P1_2 = display.gpioExpanderPin(1, 10, modeOUTPUT)
    expander1_P1_3 = display.gpioExpanderPin(1, 11, modeOUTPUT)
    expander1_P1_4 = display.gpioExpanderPin(1, 12, modeOUTPUT)
    expander1_P1_5 = display.gpioExpanderPin(1, 13, modeOUTPUT)
    expander1_P1_6 = display.gpioExpanderPin(1, 14, modeOUTPUT)
    expander1_P1_7 = display.gpioExpanderPin(1, 15, modeOUTPUT)

    expander2_P0_0 = display.gpioExpanderPin(2, 0, modeOUTPUT)
    expander2_P0_1 = display.gpioExpanderPin(2, 1, modeOUTPUT)
    expander2_P0_2 = display.gpioExpanderPin(2, 2, modeOUTPUT)
    expander2_P0_3 = display.gpioExpanderPin(2, 3, modeOUTPUT)
    expander2_P0_4 = display.gpioExpanderPin(2, 4, modeOUTPUT)
    expander2_P0_5 = display.gpioExpanderPin(2, 5, modeOUTPUT)
    expander2_P0_6 = display.gpioExpanderPin(2, 6, modeOUTPUT)
    expander2_P0_7 = display.gpioExpanderPin(2, 7, modeOUTPUT)

    expander2_P1_0 = display.gpioExpanderPin(2, 8, modeOUTPUT)
    expander2_P1_1 = display.gpioExpanderPin(2, 9, modeOUTPUT)
    expander2_P1_2 = display.gpioExpanderPin(2, 10, modeOUTPUT)
    expander2_P1_3 = display.gpioExpanderPin(2, 11, modeOUTPUT)
    expander2_P1_4 = display.gpioExpanderPin(2, 12, modeOUTPUT)
    expander2_P1_5 = display.gpioExpanderPin(2, 13, modeOUTPUT)
    expander2_P1_6 = display.gpioExpanderPin(2, 14, modeOUTPUT)
    expander2_P1_7 = display.gpioExpanderPin(2, 15, modeOUTPUT)

    pins = (expander1_P1_1,
            expander1_P1_2,
            expander1_P1_3,
            expander1_P1_5,
            expander1_P1_6,
            expander1_P1_7,
            expander2_P0_0,
            expander2_P0_1,
            expander2_P0_2,
            expander2_P0_3,
            expander2_P0_4,
            expander2_P0_5,
            expander2_P0_6,
            expander2_P0_7,
            expander2_P1_0,
            expander2_P1_1,
            expander2_P1_2,
            expander2_P1_3,
            expander2_P1_4,
            expander2_P1_5,
            expander2_P1_6,
            expander2_P1_7,
            )

    # This example writes a 0.2s pulse on the pins consecutively to test the output

    while (1):
        for pin in pins:
            pin.digitalWrite(1)
            time.sleep(0.2)
            pin.digitalWrite(0)
            time.sleep(0.2)
