# This example will show you how to draw basic black and white shapes
# Also, it will draw a bitmap of the Soldered logo in the middle

# Include all the required libraries
from soldered_inkplate6 import Inkplate
from soldered_logo import *
import time

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basicGrayscale.py
display = Inkplate(Inkplate.INKPLATE_1BIT)

if __name__ == "__main__":
    # Initialize the display, needs to be called only once
    display.begin()

    # Clear the frame buffer
    display.clearDisplay()

    # This has to be called every time you want to update the screen
    # Drawing or printing text will have no effect on the display itself before you call this function
    display.display()

    # Let's draw some shapes!
    # This example will draw shapes around the upper left corner, and then rotate the screen
    # This creates a symmetrical-looking pattern of various shapes
    for r in range(4):

        # Sets the screen rotation
        display.setRotation(r)

        # All the drawing functions
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

        # If it's rotation 0 or 2, also add this filled triangle
        if display.rotation % 2 == 0:
            display.fillTriangle(500, 101, 400, 150, 400, 100, display.BLACK)

        # Show on the display!
        # Use display.partialUpdate instead of display.display() to draw only updated pixels
        # This makes for a faster update
        # IMPORTANT: the display should be fully updated every ~10 partialUpdates with display.display()
        # This ensures the image retains it's quality
        display.partialUpdate()

        # Wait 5 seconds
        time.sleep(5)

    # We've drawn the pattern, now let's draw the Soldered logo right in the middle
    display.setRotation(0)
    display.drawBitmap(294, 20, soldered_logo, 211, 44)

    display.display()
