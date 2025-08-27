# FILE: Inkplate6FLICK-touchscreen.py
# AUTHOR: Josip ŠSoldered
# BRIEF: An example showing how to use the touchscreen on Inkplate6FLICK
#        by drawing a random rectangle on screen which when pressed
#        disappears and a new one is rendomly drawn again
# LAST UPDATED: 2025-08-27
# Include needed libraries
from inkplate6FLICK import Inkplate

import random

# Create Inkplate object in 1-bit mode, black and white colors only
display = Inkplate(Inkplate.INKPLATE_1BIT)

display.begin()

# Initialize the touchscreen
display.tsInit(1)

rand_x = random.randint(0,924)
rand_y = random.randint(0,658)

# Draw a rectangle right in the middle of the screen and show it
display.drawRect(rand_x, rand_y, 100, 100, 1)
display.display()


# Every time the user touches that rectangle, print a message
# The messages get printed to the terminal where the script was ran from
# After each successful press, a new rectangle is drawn randomly on the screen
# Create the variable which counts how many times the rectangle was touched
counter = 0 
while True:
    # If a touch on the square was detected
    if(display.touchInArea(rand_x, rand_y, 100, 100)):
        # Increment the counter and print a message
        counter += 1
        print("Touch detected! Touch #: "+str(counter))
        rand_x = random.randint(0,924)
        rand_y = random.randint(0,658)
        display.clearDisplay()
        # Draw a rectangle on the screen and show it
        display.drawRect(rand_x, rand_y, 100, 100, 1)
        
        display.partialUpdate()