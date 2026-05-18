# FILE: Inkplate2-helloWorld.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to display text on the screen
# LAST UPDATED: 2025-08-14
from inkplate2 import Inkplate # Include the Inkplate module

inkplate = Inkplate() # Create an instance of the display

inkplate.begin() # Initialize the display

inkplate.setTextSize(2) # Scale up the font size

inkplate.setCursor(25,35) # Set the cursor from where the text will be written

inkplate.print("Hello world!") # Print to the display buffer

inkplate.display() # Display what is drawn to the buffer