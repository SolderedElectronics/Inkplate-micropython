# This example will show you how to draw shapes and text in black, white and red
# Also, it will draw a bitmap of the Soldered logo in the middle

# Include needed libraries
from inkplate2 import Inkplate
from soldered_logo import *

# Create Inkplate object
display = Inkplate()

# Main function
if __name__ == "__main__":

    # Initialize the display, needs to be called only once
    display.begin()

    # Print some text at location x = 5 px, y = 8 px
    # So, close to the upper left corner
    display.printText(5, 8, "Welcome to Inkplate 2")

    # Print some larger text in red
    display.setTextSize(2)
    display.printText(5, 20, "MicroPython!", display.RED)

    # Fill a black circle and draw some white and red circles inside it
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

    # Draw the soldered logo as a bitmap image in red
    display.drawBitmap(0, 58, soldered_logo, 211, 44, display.RED)

    # Display everything on Inkplate's display
    # This function must be called after drawing, or else the display won't update
    display.display()