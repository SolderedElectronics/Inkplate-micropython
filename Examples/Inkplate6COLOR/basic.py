from inkplate6COLOR import Inkplate
from image import *
import time

display = Inkplate()

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()

    for r in range(4):
        # Sets the screen rotation
        display.setRotation(r)

        # All drawing functions
        display.drawPixel(100, 100, display.BLACK)
        display.drawRect(50, 50, 75, 75, display.GREEN)
        display.drawCircle(200, 200, 30, display.BLUE)
        display.fillCircle(300, 300, 30, display.BLACK)
        display.drawFastHLine(20, 100, 50, display.BLACK)
        display.drawFastVLine(100, 20, 50, display.ORANGE)
        display.drawLine(100, 100, 400, 400, display.ORANGE)
        display.drawRoundRect(100, 10, 100, 100, 10, display.BLACK)
        display.fillRoundRect(10, 100, 100, 100, 10, display.YELLOW)
        display.drawTriangle(300, 100, 400, 150, 400, 100, display.BLACK)

    # Draws image from bytearray
    display.setRotation(0)
    display.drawBitmap(10, 160, image, 576, 100, display.BLUE)
    display.display()
