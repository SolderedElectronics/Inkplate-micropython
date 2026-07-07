# FILE: Inkplate5v2-helloWorld.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to display text on the screen
# LAST UPDATED: 2025-08-12
from inkplate5v2 import Inkplate # Include the Inkplate module

inkplate = Inkplate(Inkplate.INKPLATE_1BIT) # Create an instance of the display in 2-bit grayscale

inkplate.begin() # Initialize the display

inkplate.setTextSize(2) # Scale up the font size

inkplate.setCursor(500,350) # Set the cursor from where the text will be written

inkplate.print("Hello world!") # Print to the display buffer

inkplate.display() # Display what is drawn to the buffer