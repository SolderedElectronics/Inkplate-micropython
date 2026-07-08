"""Example showing how to read the battery voltage."""

# Include needed libraries
from inkplate6_color import Inkplate

# Creates an Inkplate object
inkplate = Inkplate()

# Initialize the display, needs to be called only once
inkplate.begin()

# Clear the frame buffer
inkplate.clear_display()

# Get the battery reading as a string
battery = str(inkplate.read_battery())

# Set text size to double from the original size, so we can see the text better
inkplate.set_text_size(1)

# Print the text at coordinates 100,180 (from the upper left corner)
inkplate.print_text(150, 190, "Battery voltage: " + battery + "V")

# Show it on the display
inkplate.display()
