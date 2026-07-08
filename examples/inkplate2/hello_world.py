"""Displays "Hello world!" text on the Inkplate 2 screen."""

from inkplate2 import Inkplate  # Include the Inkplate module

inkplate = Inkplate()  # Create an instance of the display

inkplate.begin()  # Initialize the display

inkplate.set_text_size(2)  # Scale up the font size

inkplate.set_cursor(25, 35)  # Set the cursor from where the text will be written

inkplate.print("Hello world!")  # Print to the display buffer

inkplate.display()  # Display what is drawn to the buffer
