import time
from PCAL6416A import *

from inkplate6_COLOR import Inkplate

display = Inkplate()

# This script demonstrates using all the available GPIO expander pins as output

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()

    # pin = display.gpioExpanderPin(pin,mode)
    # Supported modes: modeINPUT, modeINPUT_PULLUP, modeINPUT_PULLDOWN, modeOUTPUT
    # Supported pins on Inkplate 6 COLOR are listed below

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

    pins = (expander_P0_0,
            expander_P0_1,
            expander_P0_2,
            expander_P0_3,
            expander_P0_4,
            expander_P0_5,
            expander_P0_6,
            expander_P0_7,
            expander_P1_0,
            expander_P1_1,
            expander_P1_2,
            expander_P1_3,
            expander_P1_4,
            expander_P1_5,
            expander_P1_6,
            expander_P1_7,
            )

    # This example writes a 0.2s pulse on the pins consecutively to test the output

    while (1):
        for pin in pins:
            pin.digitalWrite(1)
            time.sleep(0.2)
            pin.digitalWrite(0)
            time.sleep(0.2)