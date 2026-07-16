"""Use the touchscreen on Inkplate4TEMPERA.

Draws a random rectangle on screen which disappears when pressed, then a new
one is randomly drawn again.
"""

# Include needed libraries
from inkplate4tempera import Inkplate

import random

# Create Inkplate object in 1-bit mode, black and white colors only
display = Inkplate(Inkplate.INKPLATE_1BIT)

display.begin()

# Initialize the touchscreen
display.ts_init(1)

rand_x = random.randint(0, 500)
rand_y = random.randint(0, 500)

# Draw a rectangle right in the middle of the screen and show it
display.draw_rect(rand_x, rand_y, 100, 100, 1)
display.display()


# Every time the user touches that rectangle, print a message
# The messages get printed to the terminal where the script was ran from
# After each successful press, a new rectangle is drawn randomly on the screen
# Create the variable which counts how many times the rectangle was touched
counter = 0
while True:
    # If a touch on the square was detected
    if display.touch_in_area(rand_x, rand_y, 100, 100):
        # Increment the counter and print a message
        counter += 1
        print("Touch detected! Touch #: " + str(counter))
        rand_x = random.randint(0, 500)
        rand_y = random.randint(0, 500)
        display.clear_display()
        # Draw a rectangle on the screen and show it
        display.draw_rect(rand_x, rand_y, 100, 100, 1)

        display.partial_update()
