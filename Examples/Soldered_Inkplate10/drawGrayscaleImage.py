# This example shows how to draw a grayscale image from the SD card
# Copy the image from Sd_card_example_files and place it on the microSD card
# NOTE: This takes quite a while as MicroPython can be a bit slow

# Include needed libraries
from soldered_inkplate10 import Inkplate
import os, time

# Init display in 2bit mode, important
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

    # SD Card must be initialised with this function
    display.initSDCard()

    # Wait one second so we're totally sure it's initialized
    time.sleep(1)

    # Wake the SD (power ON)
    display.SDCardWake()

    # Draw image in grayscale and display it
    # Also print a message before and after
    print("Starting to draw image from file!")
    display.drawImageFile(0, 0, "sd/1.bmp", False)
    display.display()
    print("Finished drawing image from file!")

    # Put the SD card back to sleep to save power
    display.SDCardSleep()
    # To turn it back on, use:
    # display.SDCardWake()
