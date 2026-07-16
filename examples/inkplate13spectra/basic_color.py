"""Draw shapes around the upper left corner, then rotate the screen.

Creates a symmetrical-looking pattern of various shapes.
"""

# Include all the required libraries
from inkplate13_spectra import Inkplate

# Create Inkplate object
display = Inkplate()


# Initialize the display, needs to be called only once
display.begin()

# Let's draw some shapes!
# This example will draw shapes around the upper left corner, and then rotate the screen
# This creates a symmetrical-looking pattern of various shapes
for r in range(4):
    # Sets the screen rotation
    display.set_rotation(r)

    # All drawing functions
    # Available colors are:
    # Black, white, green, blue, red, yellow, orange
    display.draw_pixel(100, 100, display.BLACK)
    display.draw_rect(50, 50, 75, 75, display.GREEN)
    display.draw_circle(200, 200, 30, display.BLUE)
    display.fill_circle(300, 300, 30, display.RED)
    display.draw_fast_hline(20, 100, 50, display.BLACK)
    display.draw_round_rect(100, 10, 100, 100, 10, display.BLACK)
    display.fill_round_rect(10, 100, 100, 100, 10, display.YELLOW)
    display.draw_triangle(300, 100, 400, 150, 400, 100, display.BLACK)

# Reset the rotation
display.set_rotation(0)

# Show on the display
display.display()
