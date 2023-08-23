# This example will show you how to draw a color image (black, white, red)
# The pixel format is four pixels per byte, each pixel two bits
# 00 is Black
# 01 is White
# 10 is Red

# Include needed libraries
from inkplate2 import Inkplate

# Import the image
# It should also be copied to Inkplate when copying other libraries
# Check the README!
from color_image_inkplate2 import color_image_inkplate2

# Create Inkplate object
display = Inkplate()

# Main function
if __name__ == "__main__":

    # Initialize the display, needs to be called only once
    display.begin()

    # color_image_inkplate2 is 212x104px, draw it over the whole screen
    # Arguments are x start, y start, width, height, and then the image buffer
    display.drawColorImage(0, 0, 212, 104, color_image_inkplate2)

    # Show it on the display
    display.display()