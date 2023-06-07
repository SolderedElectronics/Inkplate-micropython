from soldered_inkplate6 import Inkplate
import os, time

# Init display in 2bit mode, important
display = Inkplate(Inkplate.INKPLATE_2BIT)

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()
    display.clearDisplay()
    display.display()

    # SD Card must be initialised with this function
    display.initSDCard()
    time.sleep(1)

    # Wake the SD
    display.SDCardWake()

    # Draw image in grayscale and display it
    display.drawImageFile(0, 0, "sd/1.bmp", False)
    display.display()

    # Put the SD card to sleep
    display.SDCardSleep()
