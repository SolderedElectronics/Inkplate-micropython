import os
import time
from inkplate2 import Inkplate

# Import the image
from color_image_small import color_image_small

display = Inkplate()
display.begin() # Must be called!
display.clearDisplay()

# This image is 212x104, draw it over the whole screen
# Arguments are x start, y start, width, height, and then the image
display.drawColorImage(0, 0, 212, 104, color_image_small)

# Show on the display
display.display()
