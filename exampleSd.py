import os
from inkplate import Inkplate

display = Inkplate(Inkplate.INKPLATE_1BIT)
os.mount(display.sd, "/sd")

# This prints all the files on card
# print(os.listdir("/sd"))

f = open("sd/text.txt", "r")

# Print file contents
print(f.read())
f.close()
