"""Display text on the screen."""

from inkplate5v2 import Inkplate  # Include the Inkplate module

inkplate = Inkplate(Inkplate.INKPLATE_1BIT)  # Create an instance of the display in 2-bit grayscale

inkplate.begin()  # Initialize the display

inkplate.set_text_size(2)  # Scale up the font size

inkplate.set_cursor(500, 350)  # Set the cursor from where the text will be written

inkplate.print("Hello world!")  # Print to the display buffer

inkplate.display()  # Display what is drawn to the buffer
