from inkplate7 import Inkplate
from soldered_logo import *
import time

display = Inkplate()

if __name__ == "__main__":
    # Must be called before using the display, like in Arduino
    display.begin()
    display.clearDisplay()
    display.display()

    for r in range(4):
        # Sets the screen rotation
        display.setRotation(r)

        # All drawing functions
        # Draw some of the elements in red so we can see the color
        display.drawPixel(100, 100, display.BLACK)
        display.drawRect(50, 50, 75, 75, display.RED)
        display.drawCircle(200, 200, 30, display.RED)
        display.fillCircle(300, 300, 30, display.BLACK)
        display.drawFastHLine(20, 100, 50, display.BLACK)
        display.drawFastVLine(100, 20, 50, display.BLACK)
        display.drawLine(100, 100, 400, 400, display.BLACK) 
        display.drawRoundRect(100, 10, 100, 100, 10, display.BLACK)
        display.fillRoundRect(10, 100, 100, 100, 10, display.BLACK)
        display.drawTriangle(300, 100, 400, 150, 400, 100, display.BLACK)

        if display.rotation % 2 == 0:
            display.fillTriangle(500, 101, 400, 150, 400, 100, display.RED)

        display.display()
        time.sleep(5)

    # Draws image from bytearray
    display.setRotation(0)
    display.drawBitmap(214, 170, soldered_logo, 211, 44, display.RED)

    # Use display.partialUpdate instead of display.display() to draw only updated pixels
    display.display()