# For this example, copy the files from the directory "Sd_card_example_files"
# to an empty microSD card's root folder and then insert it into Inkplate

# Include required libraries
import os, time
from soldered_inkplate6_PLUS import Inkplate

# Create Inkplate object in 2-bit (grayscale) mode
display = Inkplate(Inkplate.INKPLATE_2BIT)

# Init Inkplate
display.begin()

# SD Card must be initialised with this function
display.initSDCard()

# This prints all the files on card
print(os.listdir("/sd"))

f = open("sd/text.txt", "r")

# Print file contents
print(f.read())
f.close()

time.sleep(5)

# Draw the image titled "1.bmp"
# Warning, this takes quite a while
# It's faster with smaller images or in 1-bit mode
display.drawImageFile(0, 0, "sd/1.bmp")

# You can turn off the power to the SD card to save power
display.SDCardSleep()
# To turn it back on, use: 
# display.SDCardWake()

display.display()
