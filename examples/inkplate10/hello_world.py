"""Display text on the screen."""

from inkplate10 import Inkplate  # Include the Inkplate module

inkplate = Inkplate(Inkplate.INKPLATE_1BIT)  # Create a display instance (8-level grayscale)

inkplate.begin()  # Initialize the display

inkplate.set_text_size(2)  # Scale up the font size

inkplate.set_cursor(450, 350)  # Set the cursor from where the text will be written

inkplate.print("Hello world!")  # Print to the display buffer

inkplate.display()  # Display what is drawn to the buffer
