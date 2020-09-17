from inkplate import Inkplate
from image import *
import time

display = Inkplate(Inkplate.INKPLATE_1BIT)

if __name__ == "__main__":
    display.begin()

    for r in range(4):
        display.setRotation(r)

        # All drawing functions
        display.drawPixel(100, 100, display.BLACK)
        display.drawRect(50, 50, 75, 75, display.BLACK)
        display.drawCircle(200, 200, 30, display.BLACK)
        display.fillCircle(300, 300, 30, display.BLACK)
        display.drawFastHLine(20, 100, 50, display.BLACK)
        display.drawFastVLine(100, 20, 50, display.BLACK)
        display.drawLine(100, 100, 400, 400, display.BLACK)
        display.drawRoundRect(100, 10, 100, 100, 10, display.BLACK)
        display.fillRoundRect(10, 100, 100, 100, 10, display.BLACK)
        display.drawTriangle(300, 100, 400, 150, 400, 100, display.BLACK)

        if display.rotation % 2 == 0:
            display.fillTriangle(500, 101, 400, 150, 400, 100, display.BLACK)

    display.setRotation(0)
    display.drawBitmap(120, 200, image, 576, 100)
    display.display()

    time.sleep(5)

    display.selectDisplayMode(display.INKPLATE_3BIT)

    display.clearDisplay()
    for r in range(4):
        display.setRotation(r)

        # All drawing functions
        display.drawPixel(100, 100, 0)
        display.drawRect(50, 50, 75, 75, 1)
        display.drawCircle(200, 200, 30, 1)
        display.fillCircle(300, 300, 30, 1)
        display.drawFastHLine(20, 100, 50, 1)
        display.drawFastVLine(100, 20, 50, 1)
        display.drawLine(100, 100, 400, 400, 0)
        display.drawRoundRect(100, 10, 100, 100, 10, 0)
        display.fillRoundRect(10, 100, 100, 100, 10, 1)
        display.drawTriangle(300, 100, 400, 150, 400, 100, 1)

        if display.rotation % 2 == 0:
            display.fillTriangle(500, 101, 400, 150, 400, 100, 1)

    display.setRotation(0)
    display.display()
