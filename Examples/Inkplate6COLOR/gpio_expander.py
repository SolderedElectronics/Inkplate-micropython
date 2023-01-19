import time

from inkplate6_COLOR import Inkplate

display = Inkplate()

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()

    while (1):
        for x in range(16):
            display._GPIOexpander.digitalWrite(int(x), 1)

        time.sleep(0.5)

        for x in range(16):
            display._GPIOexpander.digitalWrite(int(x), 0)

        time.sleep(0.5)
