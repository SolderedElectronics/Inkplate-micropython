# FILE: Inkplate6COLOR-helloWorld.py
# AUTHOR: Josip Šimun Kuči @ Soldered
# BRIEF: An example showing how to display a colorful text on the screen
# LAST UPDATED: 2025-08-19
from inkplate6COLOR import Inkplate # Include the Inkplate module

inkplate = Inkplate() # Create an instance of the display
inkplate.begin() # Initialize the display

inkplate.setTextSize(2) # Scale up the font size

inkplate.setCursor(180,180) # Set the cursor from where the text will be written

helloWorld = "Hello world!" # Declare the string we want to print

i = 0 # Declare the counter we will use to iterate through the colors

# Iterate through each character in the string
for char in helloWorld:
    # Change the color of every character
    inkplate.setTextColor(i)
    # Print a single character to the framebuffer
    inkplate.print(char)
    # Iterate the color counter
    i = i + 1
    if (i == 1): # If the color is white, skip it
        i = i + 1
    elif (i // 7 > 0): # If we displayed all 7 colors, return to the first one
        i = 0

inkplate.display() # Display what is drawn to the buffer
