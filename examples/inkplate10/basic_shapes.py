"""Draw the ten basic shapes on the Inkplate 10, in black and white.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate10 import Inkplate

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
BLACK = inkplate.BLACK

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Row 1, the outlines. Every shape sits in its own column, and the middle of
# each one is on the line y = 250.

# draw_rect(x, y, width, height, colour): x, y is the top left corner.
inkplate.draw_rect(40, 170, 160, 160, BLACK)

# draw_circle(x, y, radius, colour): x, y is the centre.
inkplate.draw_circle(360, 250, 80, BLACK)

# draw_round_rect(x, y, width, height, radius, colour): a rectangle with round corners.
inkplate.draw_round_rect(520, 170, 160, 160, 30, BLACK)

# draw_triangle(x1, y1, x2, y2, x3, y3, colour): joins three points.
inkplate.draw_triangle(840, 170, 760, 330, 920, 330, BLACK)

# draw_line(x1, y1, x2, y2, colour): joins two points.
inkplate.draw_line(1000, 330, 1160, 170, BLACK)

# Row 2, the solid shapes. They have the same sizes as the outlines above,
# and the middle of each one is on the line y = 580.
inkplate.fill_rect(40, 500, 160, 160, BLACK)
inkplate.fill_circle(360, 580, 80, BLACK)
inkplate.fill_round_rect(520, 500, 160, 160, 30, BLACK)
inkplate.fill_triangle(840, 500, 760, 660, 920, 660, BLACK)

# draw_pixel(x, y, colour) sets a single pixel, which is tiny, so five of them
# make a small plus.
inkplate.draw_pixel(1080, 580, BLACK)
inkplate.draw_pixel(1072, 580, BLACK)
inkplate.draw_pixel(1088, 580, BLACK)
inkplate.draw_pixel(1080, 572, BLACK)
inkplate.draw_pixel(1080, 588, BLACK)

# Send the frame buffer to the screen
inkplate.display()
