"""Display text on the screen."""

from inkplate4tempera import Inkplate  # Include the Inkplate module

inkplate = Inkplate(Inkplate.INKPLATE_1BIT)  # Create an instance of the display in 1-bit mode

inkplate.begin()  # Initialize the display

inkplate.set_text_size(2)  # Scale up the font size

inkplate.set_cursor(150, 280)  # Set the cursor from where the text will be written (600x600 panel)

inkplate.print("Hello world!")  # Print to the display buffer

inkplate.display()  # Display what is drawn to the buffer
