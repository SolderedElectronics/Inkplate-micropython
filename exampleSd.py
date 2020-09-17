import os
from inkplate import Inkplate

display = Inkplate(Inkplate.INKPLATE_2BIT)
display.begin()

# This prints all the files on card
# print(os.listdir("/sd"))

f = open("sd/text.txt", "r")

# Print file contents
print(f.read())
f.close()

# Utterly slow, can take minutes :(
display.drawImageFile(0, 0, "sd/32bit.bmp")

display.display()
