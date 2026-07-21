"""Update only a small region of the screen using display_partial().

Draws a static frame once with a full refresh, then repeatedly updates just a
counter box using display_partial() -- much faster than a full display() call
since only the given rectangle is re-sent to the panel and refreshed.

Note: unlike some other Inkplate boards' partial update, this does not diff
old vs new pixels -- it unconditionally re-sends whatever is currently in the
framebuffer inside the given rectangle. The old content in that rectangle
must be cleared/overdrawn yourself (see fill_rect() below) before drawing the
new content, otherwise old and new pixels will overlap.
"""

import time
from inkplate13_spectra import Inkplate

# Create Inkplate object
display = Inkplate()

# Initialize the display, needs to be called only once
display.begin()
display.set_rotation(1)

# Static content, drawn once
display.print_text(50, 50, "Partial update demo")
display.draw_rect(50, 120, 150, 60, display.BLACK)

# Full refresh to show the static frame -- also required before the first
# display_partial() call, since the panel needs to be initialized once with a
# complete image before a partial-window refresh makes sense.
display.display()

# Counter box coordinates -- must line up with the rect drawn above
box_x, box_y, box_w, box_h = 50, 120, 150, 60

for i in range(10):
    # Clear just the box interior (fill with white) before drawing the new
    # number -- inset by 1px so the border drawn by draw_rect() above isn't
    # overwritten, since display_partial() has no diffing of its own
    display.fill_rect(box_x + 1, box_y + 1, box_w - 2, box_h - 2, display.WHITE)
    display.print_text(box_x + 10, box_y + 15, "Count: " + str(i))

    # Only this rectangle gets re-sent and refreshed -- much faster than
    # calling display.display() (a full-panel refresh) every iteration
    display.display_partial(box_x, box_y, box_w, box_h)

    time.sleep(2)
