"""Example showing how to display colorful text on the screen."""
from inkplate6_color import Inkplate  # Include the Inkplate module

inkplate = Inkplate()  # Create an instance of the display
inkplate.begin()  # Initialize the display

inkplate.set_text_size(2)  # Scale up the font size

inkplate.set_cursor(180, 180)  # Set the cursor from where the text will be written

hello_world = "Hello world!"  # Declare the string we want to print

i = 0  # Declare the counter we will use to iterate through the colors

# Iterate through each character in the string
for char in hello_world:
    # Change the color of every character
    inkplate.set_text_color(i)
    # Print a single character to the framebuffer
    inkplate.print(char)
    # Iterate the color counter
    i = i + 1
    if i == 1:  # If the color is white, skip it
        i = i + 1
    elif i // 7 > 0:  # If we displayed all 7 colors, return to the first one
        i = 0

inkplate.display()  # Display what is drawn to the buffer
