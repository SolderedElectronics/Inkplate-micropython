"""Draw a landscape on the Inkplate 10 with every basic shape.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate10 import Inkplate

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)
BLACK = inkplate.BLACK
WHITE = inkplate.WHITE


# A cloud is three overlapping circles. Draw the outlines first, then fill every
# circle with white, a little smaller. The fills rub out the outline lines inside
# the cloud, and only the outer edge is left.
def draw_cloud(x, y):
    inkplate.draw_circle(x, y, 28, BLACK)
    inkplate.draw_circle(x + 40, y - 18, 38, BLACK)
    inkplate.draw_circle(x + 88, y, 30, BLACK)
    inkplate.fill_circle(x, y, 25, WHITE)
    inkplate.fill_circle(x + 40, y - 18, 35, WHITE)
    inkplate.fill_circle(x + 88, y, 27, WHITE)


# A mountain is a triangle. Fill it with white first, so it covers whatever is
# behind it, then draw its outline on top.
def draw_mountain(left, right, peak_x, peak_y):
    inkplate.fill_triangle(left, 700, right, 700, peak_x, peak_y, WHITE)
    inkplate.draw_triangle(left, 700, right, 700, peak_x, peak_y, BLACK)


# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# The sun: fill_circle(x, y, radius, colour) is solid, draw_circle(...) is an outline.
# x, y is the centre of the circle.
inkplate.fill_circle(1030, 130, 55, BLACK)
inkplate.draw_circle(1030, 130, 85, BLACK)

# Two clouds
draw_cloud(150, 150)
draw_cloud(520, 90)

# Mountains, from the back to the front
draw_mountain(0, 600, 300, 380)
draw_mountain(400, 1120, 760, 330)
draw_mountain(850, 1200, 1050, 470)

# The ground: draw_line(x1, y1, x2, y2, colour) joins two points.
inkplate.draw_line(0, 700, 1199, 700, BLACK)

# Speckles on the ground: draw_pixel(x, y, colour) sets one pixel.
for x in range(10, 1200, 23):
    inkplate.draw_pixel(x, 715 + (x * 7) % 29, BLACK)

# The house. draw_rect(x, y, width, height, colour) is an outline and fill_rect(...) is
# solid. The chimney is drawn first, so the roof covers its lower part.
inkplate.fill_rect(630, 420, 30, 70, BLACK)
inkplate.fill_rect(380, 520, 320, 180, WHITE)
inkplate.draw_rect(380, 520, 320, 180, BLACK)
inkplate.fill_triangle(350, 520, 730, 520, 540, 400, WHITE)
inkplate.draw_triangle(350, 520, 730, 520, 540, 400, BLACK)

# Smoke from the chimney, three circles that grow
inkplate.draw_circle(646, 400, 8, BLACK)
inkplate.draw_circle(662, 370, 12, BLACK)
inkplate.draw_circle(690, 335, 16, BLACK)

# The window has rounded corners, and two lines make the panes.
# draw_round_rect(x, y, width, height, radius, colour), and fill_round_rect(...) is solid.
inkplate.draw_round_rect(420, 560, 100, 90, 10, BLACK)
inkplate.draw_line(470, 560, 470, 649, BLACK)
inkplate.draw_line(420, 605, 519, 605, BLACK)

# The door
inkplate.fill_round_rect(580, 600, 70, 100, 10, BLACK)

# The path from the door to the bottom of the screen
inkplate.draw_line(580, 700, 540, 824, BLACK)
inkplate.draw_line(650, 700, 720, 824, BLACK)

# The fence: a loop draws the posts, two lines are the rails
for x in range(780, 1001, 30):
    inkplate.draw_line(x, 650, x, 700, BLACK)
inkplate.draw_line(780, 665, 1000, 665, BLACK)
inkplate.draw_line(780, 685, 1000, 685, BLACK)

# The tree: a trunk and two triangles
inkplate.fill_rect(1082, 640, 26, 60, BLACK)
inkplate.fill_triangle(1030, 650, 1160, 650, 1095, 540, BLACK)
inkplate.fill_triangle(1040, 580, 1150, 580, 1095, 490, BLACK)

# Tufts of grass along the bottom, drawn with a loop
for x in range(30, 1200, 40):
    if x < 500 or x > 760:
        inkplate.draw_line(x, 810, x - 8, 785, BLACK)
        inkplate.draw_line(x, 810, x + 8, 785, BLACK)

# Send the frame buffer to the screen
inkplate.display()
