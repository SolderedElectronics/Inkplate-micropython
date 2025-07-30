# FILE: Inkplate6-helloWorld.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to display text on the screen
# LAST UPDATED: 2025-07-29
from inkplate6 import Inkplate # Include the Inkplate module

inkplate = Inkplate(Inkplate.INKPLATE_2BIT) # Create an instance of the display in 2-bit grayscale

inkplate.begin() # Initialize the display

inkplate.setTextSize(2) # Scale up the font size

inkplate.setCursor(250,250) # Set the cursor from where the text will be written

inkplate.print("Hello world!") # Print to the display buffer

inkplate.display() # Display what is drawn to the buffer