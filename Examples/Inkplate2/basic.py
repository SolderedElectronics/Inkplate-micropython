from inkplate2 import Inkplate
from image import *
import time

display = Inkplate()

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()

    # Print some text
    display.printText(5, 23, "Welcome to Inkplate 2")

    # Print some larger text in red
    display.setTextSize(2)
    display.printText(5, 35, "MicroPython!", display.RED)

    # Fill a black circle and draw some white and red circles in it
    display.fillCircle(178, 32, 15, display.BLACK)
    display.drawCircle(178, 32, 13, display.RED)
    display.drawCircle(178, 32, 9, display.WHITE)
    display.drawCircle(178, 32, 4, display.RED)

    # Draw a red checkerboard pattern
    for x in range(30):
        display.fillRect(0 + (5*x*2), 52, 5, 5, display.RED)

    for x in range(30):
        display.fillRect(5 + (5*x*2), 57, 5, 5, display.RED)
    
    # Draw some lines
    display.drawLine(0, 52+15, 214, 52+15, display.BLACK)
    display.drawLine(0, 54+15, 214, 54+15, display.RED)
    display.drawLine(0, 56+15, 214, 56+15, display.BLACK)
    display.drawLine(0, 58+15, 214, 58+15, display.RED)

    display.display()
