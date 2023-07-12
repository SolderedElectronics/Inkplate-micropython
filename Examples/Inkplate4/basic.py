from inkplate4 import Inkplate
from soldered_logo import *
import time

display = Inkplate()

if __name__ == "__main__":
    # Must be called before using the display, like in Arduino
    display.begin()
    display.clearDisplay()

    for r in range(4):
        # Sets the screen rotation
        display.setRotation(r)

        # All drawing functions
        # Draw some of the elements in red so we can see the color
        display.drawPixel(20, 5, display.BLACK)
        display.drawRect(10, 40, 20, 60, display.RED)
        display.drawCircle(30, 60, 15, display.RED)
        display.fillCircle(70, 30, 15, display.BLACK)
        display.drawFastHLine(30, 75, 100, display.BLACK)
        display.drawFastVLine(100, 10, 40, display.BLACK)
        display.drawLine(5, 5, 150, 150, display.BLACK) 
        display.drawRoundRect(160, 5, 20, 60, 10, display.BLACK)
        display.fillRoundRect(150, 70, 60, 15, 10, display.RED)
        display.drawTriangle(5, 196, 60, 196, 33, 149, display.RED)

        display.display()
        time.sleep(5)

    # Draws image from bytearray
    display.setRotation(0)
    display.fillRect(94, 128, 211, 44, display.WHITE) # Draw white background
    display.drawBitmap(94, 128, soldered_logo, 211, 44, display.RED)

    # Use display.partialUpdate instead of display.display() to draw only updated pixels
    display.display()