import os
import time
from inkplate6COLOR import Inkplate

display = Inkplate()
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

display.drawImageFile(0, 0, "sd/1.bmp")

# You can turn off the power to the SD card to save power
display.SDCardSleep()
# To turn it back on, use: 
# display.SDCardWake()

display.display()
