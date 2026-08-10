"""List, write and read back a text file on the microSD card."""

from inkplate6 import Inkplate
import os

inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
inkplate.begin()
inkplate.init_sd_card(fast_boot=True)

# List files on the SD card
print("FIles on SD:", os.listdir("sd"))

# Writing to a file
with open("sd/example.txt", "w") as f:
    f.write("Hello from Inkplate!\n")
    f.write("this text is stored on the SD card.\n")
print("Data written to sd/example.txt")

# Reading from the same file
with open("sd/example.txt", "r") as f:
    content = f.read()
print("File contents:")
print(content)
