from inkplate import Inkplate
from image import *

display = Inkplate(Inkplate.INKPLATE_1BIT)

if __name__ == "__main__":
    display.begin()

    # display.drawRect(50, 50, 75, 75, 1)
    # display.drawCircle(50, 50, 30, 1)
    # display.fillCircle(100, 100, 30, 1)
    # display.drawFastHLine(100, 100, 50, 1)
    # display.drawFastVLine(100, 100, 50, 1)
    # display.drawLine(100, 100, 150, 150, 1)

    # display.drawRoundRect(100, 100, 200, 200, 20, 1)
    # display.drawRoundRect(100, 100, 400, 400, 20, 1)

    display.drawBitmap(20, 20, image, 576, 100)
    display.display()

