# This example will show you how to draw shapes and text in black, white and red
# Also, it will draw a bitmap of the Soldered logo in the middle

# Include needed libraries
from inkplate4 import Inkplate
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

        # Show on the display!
        # This function must be called in order for the display to update
        display.display()

        # Wait 5 seconds
        time.sleep(5)

    # Reset the rotation
    display.setRotation(0)

    # Let's draw the Soldered logo right in the middle
    # First, fill the background of the image white
    display.fillRect(94, 128, 211, 44, display.WHITE) # Draw white background
    # Now, draw the logo
    display.drawBitmap(94, 128, soldered_logo, 211, 44, display.RED)

    # Show on the display
    display.display()