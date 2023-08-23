import os
import time
from inkplate6COLOR import Inkplate

# Import the two color images
from color_image_inkplate6color_inkplate6COLOR import color_image_inkplate6color
from small_color_image_inkplate6color import small_color_image_inkplate6color

# For this example, make sure you copy both of these images to Inkplate

display = Inkplate()
display.begin() # Must be called!
display.clearDisplay()

# This image is 600x488, draw it over the whole screen
# Arguments are x start, y start, width, height, and then the image
display.drawColorImage(0, 0, 600, 488, color_image_inkplate6color)

# This image is 140x140, draw it near the middle of the screen
# Arguments are x start, y start, width, height, and then the image
display.drawColorImage(200, 120, 140, 140, small_color_image_inkplate6color)

# Show on the display
display.display()
