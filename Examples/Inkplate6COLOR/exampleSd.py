import os
import time
from inkplate6_COLOR import Inkplate

display = Inkplate()
display.begin()

# This prints all the files on card
print(os.listdir("/sd"))

f = open("sd/text.txt", "r")

# Print file contents
print(f.read())
f.close()
