# This example will show you how to draw different shades of gray using grayscale mode

# Include needed libraries
from soldered_inkplate6 import Inkplate
from soldered_logo import *
import time

# Create Inkplate object in 2-bit grayscale mode
display = Inkplate(Inkplate.INKPLATE_2BIT)

# Main function
if __name__ == "__main__":
    
    # Initialize the display, needs to be called only once
    display.begin()

    # Clear the frame buffer
    display.clearDisplay()

    # This has to be called every time you want to update the screen
    # Drawing or printing text will have no effect on the display itself before you call this function
    display.display()

    # Draw pallet of posible shades
    # 0 being the lightest (white), 3 being the darkest
    display.writeFillRect(0, 0, 25, 600, 3)
    display.writeFillRect(25, 0, 25, 600, 2)
    display.writeFillRect(50, 0, 25, 600, 1)
    display.writeFillRect(75, 0, 25, 600, 0)

    # Show on the display
    display.display()

    # Wait 3 seconds
    time.sleep(3)

    # Let's draw the Soldered logo and show it on the display
    display.drawBitmap(294, 278, soldered_logo, 211, 44)
    display.display()