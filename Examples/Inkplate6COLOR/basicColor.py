# FILE: Inkplate6COLOR-basicColor.py
# AUTHOR: Soldered
# BRIEF: An example showing how to draw shapes around the upper left corner, and then rotate the screen
#        This creates a symmetrical-looking pattern of various shapes
# LAST UPDATED: 2025-08-19

# Include all the required libraries
from inkplate6COLOR import Inkplate

# Create Inkplate object
display = Inkplate()

    
# Initialize the display, needs to be called only once
display.begin()

# Let's draw some shapes!
# This example will draw shapes around the upper left corner, and then rotate the screen
# This creates a symmetrical-looking pattern of various shapes
for r in range(4):

    # Sets the screen rotation
    display.setRotation(r)

    # All drawing functions
    # Available colors are:
    # Black, white, green, blue, red, yellow, orange
    display.drawPixel(100, 100, display.BLACK)
    display.drawRect(50, 50, 75, 75, display.GREEN)
    display.drawCircle(200, 200, 30, display.BLUE)
    display.fillCircle(300, 300, 30, display.RED)
    display.drawFastHLine(20, 100, 50, display.BLACK)
    display.drawFastVLine(100, 20, 50, display.ORANGE)
    display.drawLine(100, 100, 400, 400, display.ORANGE)
    display.drawRoundRect(100, 10, 100, 100, 10, display.BLACK)
    display.fillRoundRect(10, 100, 100, 100, 10, display.YELLOW)
    display.drawTriangle(300, 100, 400, 150, 400, 100, display.BLACK)

# Reset the rotation
display.setRotation(0)

# Show on the display
display.display()

