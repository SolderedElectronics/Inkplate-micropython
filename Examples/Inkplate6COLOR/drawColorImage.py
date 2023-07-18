import os
import time
from inkplate6_COLOR import Inkplate

# Import the two color images
from color_image import color_image
from small_color_image import small_color_image

# For this example, make sure you copy both of these images to Inkplate

display = Inkplate()
display.begin() # Must be called!
display.clearDisplay()

# This image is 600x488, draw it over the whole screen
# Arguments are x start, y start, width, height, and then the image
display.drawColorImage(0, 0, 600, 488, color_image)

# This image is 140x140, draw it near the middle of the screen
# Arguments are x start, y start, width, height, and then the image
display.drawColorImage(200, 120, 140, 140, small_color_image)

# Show on the display
display.display()
