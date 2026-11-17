"""Draw the ten basic shapes on the Inkplate 13, in colour.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate13_spectra import Inkplate

# The display object
inkplate = Inkplate()

# The colours the shapes use
BLACK = inkplate.BLACK
RED = inkplate.RED
BLUE = inkplate.BLUE
GREEN = inkplate.GREEN
YELLOW = inkplate.YELLOW

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Turn the screen to landscape, 1600 pixels across and 1200 down
inkplate.set_rotation(1)

# Row 1, the outlines. Every shape sits in its own column, and the middle of
# each one is on the line y = 330.

# draw_rect(x, y, width, height, colour): x, y is the top left corner.
inkplate.draw_rect(60, 230, 200, 200, BLACK)

# draw_circle(x, y, radius, colour): x, y is the centre.
inkplate.draw_circle(480, 330, 100, RED)

# draw_round_rect(x, y, width, height, radius, colour): a rectangle with round corners.
inkplate.draw_round_rect(700, 230, 200, 200, 40, BLUE)

# draw_triangle(x1, y1, x2, y2, x3, y3, colour): joins three points.
inkplate.draw_triangle(1120, 230, 1020, 430, 1220, 430, GREEN)

# draw_line(x1, y1, x2, y2, colour): joins two points.
inkplate.draw_line(1340, 430, 1540, 230, BLACK)

# Row 2, the solid shapes. They have the same sizes as the outlines above,
# and the middle of each one is on the line y = 800.
inkplate.fill_rect(60, 700, 200, 200, YELLOW)
inkplate.fill_circle(480, 800, 100, RED)
inkplate.fill_round_rect(700, 700, 200, 200, 40, BLUE)
inkplate.fill_triangle(1120, 700, 1020, 900, 1220, 900, GREEN)

# draw_pixel(x, y, colour) sets a single pixel, which is tiny, so five of them
# make a small plus.
inkplate.draw_pixel(1440, 800, BLACK)
inkplate.draw_pixel(1432, 800, BLACK)
inkplate.draw_pixel(1448, 800, BLACK)
inkplate.draw_pixel(1440, 792, BLACK)
inkplate.draw_pixel(1440, 808, BLACK)

# Send the frame buffer to the screen
inkplate.display()
