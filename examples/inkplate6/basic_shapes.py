"""Draw the ten basic shapes on the Inkplate 6, in black and white.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate6 import Inkplate

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
BLACK = inkplate.BLACK

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Row 1, the outlines. Every shape sits in its own column, and the middle of
# each one is on the line y = 170.

# draw_rect(x, y, width, height, colour): x, y is the top left corner.
inkplate.draw_rect(30, 120, 100, 100, BLACK)

# draw_circle(x, y, radius, colour): x, y is the centre.
inkplate.draw_circle(230, 170, 50, BLACK)

# draw_round_rect(x, y, width, height, radius, colour): a rectangle with round corners.
inkplate.draw_round_rect(330, 120, 100, 100, 20, BLACK)

# draw_triangle(x1, y1, x2, y2, x3, y3, colour): joins three points.
inkplate.draw_triangle(530, 120, 480, 220, 580, 220, BLACK)

# draw_line(x1, y1, x2, y2, colour): joins two points.
inkplate.draw_line(630, 220, 730, 120, BLACK)

# Row 2, the solid shapes. They have the same sizes as the outlines above,
# and the middle of each one is on the line y = 420.
inkplate.fill_rect(30, 370, 100, 100, BLACK)
inkplate.fill_circle(230, 420, 50, BLACK)
inkplate.fill_round_rect(330, 370, 100, 100, 20, BLACK)
inkplate.fill_triangle(530, 370, 480, 470, 580, 470, BLACK)

# draw_pixel(x, y, colour) sets a single pixel, which is tiny, so five of them
# make a small plus.
inkplate.draw_pixel(680, 420, BLACK)
inkplate.draw_pixel(672, 420, BLACK)
inkplate.draw_pixel(688, 420, BLACK)
inkplate.draw_pixel(680, 412, BLACK)
inkplate.draw_pixel(680, 428, BLACK)

# Send the frame buffer to the screen
inkplate.display()
