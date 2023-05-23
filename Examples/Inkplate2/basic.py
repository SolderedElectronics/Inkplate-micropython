from inkplate2 import Inkplate
from soldered_logo import *
import time

display = Inkplate()

if __name__ == "__main__":
    # Must be called before using the display, like in Arduino
    display.begin()
    display.clearDisplay()

    # Print some text
    display.printText(5, 8, "Welcome to Inkplate 2")

    # Print some larger text in red
    display.setTextSize(2)
    display.printText(5, 20, "MicroPython!", display.RED)

    # Fill a black circle and draw some white and red circles in it
    display.fillCircle(178, 16, 15, display.BLACK)
    display.drawCircle(178, 16, 13, display.RED)
    display.drawCircle(178, 16, 9, display.WHITE)
    display.drawCircle(178, 16, 4, display.RED)

    # Draw a red checkerboard pattern
    for x in range(30):
        display.fillRect(0 + (5*x*2), 38, 5, 5, display.RED)

    for x in range(30):
        display.fillRect(5 + (5*x*2), 42, 5, 5, display.RED)
    
    # Draw some lines
    display.drawLine(0, 49, 214, 49, display.BLACK)
    display.drawLine(0, 51, 214, 51, display.RED)
    display.drawLine(0, 53, 214, 53, display.BLACK)
    display.drawLine(0, 55, 214, 55, display.RED)

    # Draw a bitmap image
    display.drawBitmap(0, 58, soldered_logo, 211, 44, display.RED)

    # Display everything on the ePaper - must be called!
    display.display()
