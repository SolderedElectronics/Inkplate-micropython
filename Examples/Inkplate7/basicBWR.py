# This example will show you how to draw shapes and text in black, white and red
# Also, it will draw a bitmap of the Soldered logo in the middle

# Include all the required libraries
from inkplate7 import Inkplate
from soldered_logo import *
import time

# Create Inkplate object
display = Inkplate()

# Main function
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

        # If it's rotation 0 or 2, also add this filled triangle
        if display.rotation % 2 == 0:
            display.fillTriangle(500, 101, 400, 150, 400, 100, display.RED)

        # Show on the display!
        # This function must be called in order for the display to update
        display.display()

        # Wait 5 seconds
        time.sleep(5)

    # Reset the rotation
    display.setRotation(0)

    # Let's draw the Soldered logo right in the middle
    # First, fill the background of the image white
    display.fillRect(214, 170, 211, 44, display.WHITE)
    # Now, draw the logo
    display.drawBitmap(214, 170, soldered_logo, 211, 44, display.RED)

    # Show on the display
    display.display()