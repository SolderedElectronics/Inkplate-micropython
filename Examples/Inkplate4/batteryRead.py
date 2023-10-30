# This example will show you how to read the voltage of the battery
# and also print it on the screen

# Include needed libraries
from inkplate4 import Inkplate
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

    # Get the battery reading as a string
    battery = str(display.readBattery())

    # Set text size to double from the original size, so we can see the text better
    display.setTextSize(2)

    # Print the text at coordinates 50, 50 (from the upper left corner)
    display.printText(50, 50, "Battery voltage: " + battery + "V")

    # Show it on the display
    display.display()