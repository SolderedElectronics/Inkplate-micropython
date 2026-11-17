"""Bounce a ball around a box on the Inkplate 13 with partial updates, and count the updates.

Connection: none, the screen is on the board. Power and upload over USB-C.
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the library for the clock, and the Inkplate library
import time
from inkplate13_spectra import Inkplate

# The display object
inkplate = Inkplate()

# The box the ball bounces in: top left corner, width and height
BOX_X = 0
BOX_Y = 0
BOX_WIDTH = 1600
BOX_HEIGHT = 1200

# The ball: its radius and its centre, in pixels
RADIUS = 80
ball_x = BOX_X + 200
ball_y = BOX_Y + 150

# How far the ball moves on each update. A negative value means left or up.
speed_x = 30
speed_y = 24

# How many updates have been sent to the screen so far
updates = 0

# Start the display and turn it to landscape
inkplate.begin()
inkplate.set_rotation(1)

# Start from a clean, fully refreshed screen
inkplate.display()

# Black letters at the font's normal size
inkplate.set_text_color(inkplate.BLACK)
inkplate.set_text_size(1)

while True:
    # Draw the frame: the box, the ball and the update counter
    inkplate.fill_rect(BOX_X, BOX_Y, BOX_WIDTH, BOX_HEIGHT, inkplate.WHITE)
    inkplate.draw_rect(BOX_X, BOX_Y, BOX_WIDTH, BOX_HEIGHT, inkplate.BLACK)
    inkplate.fill_circle(ball_x, ball_y, RADIUS, inkplate.RED)
    inkplate.set_cursor(BOX_X + 20, BOX_Y + 20)
    inkplate.print("Updates: " + str(updates))

    # Every 50th update is a full refresh. The others send only the box.
    updates += 1
    if updates % 50 == 0:
        inkplate.display()
    else:
        inkplate.display_partial(BOX_X, BOX_Y, BOX_WIDTH, BOX_HEIGHT, True)

    # Move the ball
    ball_x += speed_x
    ball_y += speed_y

    # Turn the ball around when it touches a side of the box. Setting the position back to
    # the edge keeps it from sticking in the wall.
    if ball_x < BOX_X + RADIUS:
        ball_x = BOX_X + RADIUS
        speed_x = -speed_x
    if ball_x > BOX_X + BOX_WIDTH - 1 - RADIUS:
        ball_x = BOX_X + BOX_WIDTH - 1 - RADIUS
        speed_x = -speed_x
    if ball_y < BOX_Y + RADIUS:
        ball_y = BOX_Y + RADIUS
        speed_y = -speed_y
    if ball_y > BOX_Y + BOX_HEIGHT - 1 - RADIUS:
        ball_y = BOX_Y + BOX_HEIGHT - 1 - RADIUS
        speed_y = -speed_y
