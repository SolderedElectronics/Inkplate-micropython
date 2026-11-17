"""Bounce a ball around the Inkplate 10 with partial updates, and count the updates.

Connection: none, the screen is on the board. Power and upload over USB-C.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the Inkplate library
from inkplate10 import Inkplate

# Partial update works in black and white mode only
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()

# Start from a clean, fully refreshed screen
inkplate.clear_display()
inkplate.display()

# The font from T1, at its normal size
inkplate.set_text_size(1)

# Make every fiftieth update a full refresh, to clear the leftovers
inkplate.set_full_update_threshold(49)

# The ball: its radius and its centre, in pixels
radius = 40
ball_x = 200
ball_y = 150

# How far the ball moves on each update. A negative value means left or up.
speed_x = 30
speed_y = 24

# How many updates have been sent to the screen so far
updates = 0

while True:
    # Draw the frame: a border around the screen, the ball and the update counter
    inkplate.clear_display()
    inkplate.draw_rect(0, 0, 1200, 825, inkplate.BLACK)
    inkplate.fill_circle(ball_x, ball_y, radius, inkplate.BLACK)
    inkplate.set_cursor(20, 20)
    inkplate.print("Updates: " + str(updates))

    # Send only what changed
    inkplate.partial_update()
    updates += 1

    # Move the ball
    ball_x += speed_x
    ball_y += speed_y

    # Turn the ball around when it touches a side. Setting the position back to the
    # edge keeps it from sticking in the wall.
    if ball_x < radius:
        ball_x = radius
        speed_x = -speed_x
    if ball_x > 1199 - radius:
        ball_x = 1199 - radius
        speed_x = -speed_x
    if ball_y < radius:
        ball_y = radius
        speed_y = -speed_y
    if ball_y > 824 - radius:
        ball_y = 824 - radius
        speed_y = -speed_y
