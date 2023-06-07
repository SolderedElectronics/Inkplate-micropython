from soldered_inkplate6_PLUS import Inkplate
from soldered_logo import *
import time


# Initialize inkplate display
display = Inkplate(Inkplate.INKPLATE_2BIT)


# Main function, you can make infinite while loop inside this to run code indefinitely
if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()
    display.clearDisplay()
    display.display()

    # Draw pallet of posible colors
    #use color values 0, 1, 2, 3
    display.writeFillRect(0, 0, 25, 758, 3)
    display.writeFillRect(25, 0, 25, 758, 2)
    display.writeFillRect(50, 0, 25, 758, 1)
    display.writeFillRect(75, 0, 25, 758, 0)

    display.display()
    time.sleep(3)

    # Draws image from bytearray
    display.setRotation(0)
    display.drawBitmap(184, 357, soldered_logo, 211, 44)
    display.display()
    time.sleep(10)

