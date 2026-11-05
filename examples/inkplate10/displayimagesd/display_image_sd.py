"""Show a picture from the microSD card on the Inkplate 10, in eight levels of gray.

Connection: a microSD card in the slot on the board, with a file called cosmic-cliffs.jpg on it.
Picture:    Cosmic Cliffs, NASA / ESA / CSA / STScI, public domain. The manual has it cropped to 1200 x 825, the original is at
            https://commons.wikimedia.org/wiki/File:NASA%E2%80%99s_Webb_Reveals_Cosmic_Cliffs,_Glittering_Landscape_of_Star_Birth.jpg

Author: Borna Zelenika @ soldered.com
"""

# Pull in the os module for files, and the Inkplate library
import os
from inkplate10 import Inkplate

# Gray mode: eight levels, 0 (black) to 7 (white). Pictures need it to look right.
inkplate = Inkplate(Inkplate.INKPLATE_2BIT)

# The name of the picture on the card. It can be a JPG, PNG or BMP file.
PICTURE_NAME = "/sd/cosmic-cliffs.jpg"

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_text_color(0)
inkplate.set_text_size(2)

# Mount the card, under the folder /sd. If it did not mount, say so.
inkplate.init_sd_card()
if "sd" not in os.listdir("/"):
    inkplate.print_text(50, 50, "SD card error!")
else:
    # Draw the picture with its top left corner at 0, 0, which fills the screen, because the
    # picture is 1200 x 825 pixels. dither=True mixes black and white dots, which makes the grays look
    # smoother. If this fails, say so.
    try:
        inkplate.draw_image(PICTURE_NAME, 0, 0, dither=True)
    except OSError:
        inkplate.print_text(50, 50, "Could not open " + PICTURE_NAME)

# Send the frame buffer to the screen, then let the card sleep
inkplate.display()
inkplate.sd_card_sleep()
