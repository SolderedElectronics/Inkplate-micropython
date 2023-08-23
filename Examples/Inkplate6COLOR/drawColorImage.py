# This example will show you how to draw a color image from buffer

# Include needed libraries
from inkplate6COLOR import Inkplate

# Import the image
# It should also be copied to Inkplate when copying other libraries
# Check the README!
from color_image_inkplate6COLOR import color_image_inkplate6color

# Create Inkplate object
display = Inkplate()

# Main function
if __name__ == "__main__":

    # Initialize the display, needs to be called only once
    display.begin()

    # color_image_inkplate6color is 600x488px, draw it over the whole screen
    # Arguments are x start, y start, width, height, and then the image buffer
    display.drawColorImage(0, 0, 600, 488, color_image_inkplate6color)

    # Show on the display
    display.display()