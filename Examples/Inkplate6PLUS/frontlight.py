# This example will show you how to adjust the frontlight

# Include required libraries
from inkplate6PLUS import Inkplate
import time

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Main function
if __name__ == "__main__":
    
    # Initialize the display, needs to be called only once
    display.begin()

    # Clear the frame buffer
    display.clearDisplay()

    # This has to be called every time you want to update the screen
    # Drawing or printing text will have no effect on the display itself before you call this function
    display.display()

    # Enable the frontlight
    display.frontlight(True)
    
    # Frontlight strength can be set from values 0 to 64
    # For example:
    display.setFrontlight(34)

    # Wait 3 seconds
    time.sleep(3)

    # Slowly gradually increase the frontlight and then decrease it, infinitely
    while(True):
        # First, increase the brightness gradually
        for i in range(0, 60):
            display.setFrontlight(i)
            time.sleep(0.5) # Wait for 500ms

        # Then, decrease
        for i in range(60, 0):
            display.setFrontlight(i)
            time.sleep(0.5) # Wait for 500ms