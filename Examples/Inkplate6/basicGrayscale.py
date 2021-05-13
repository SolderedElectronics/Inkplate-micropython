# Include needed libraries

from inkplate import Inkplate
from image import *
import time

# Initialize inkplate display
display = Inkplate(Inkplate.INKPLATE_2BIT)

color = 1

# Main function, you can make infinite while loop inside this to run code indefinitely
if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()
    while True:
        display.clearDisplay()
        display.display()

        # All drawing functions
        display.writeFillRect(0, 0, 50, 600, color)

        display.display()
        time.sleep(3)

        # Draws image from bytearray
        display.setRotation(0)
        display.drawBitmap(120, 200, image, 576, 100)
        display.display()
        time.sleep(10)
