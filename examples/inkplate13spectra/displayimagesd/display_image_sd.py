"""Show a picture from the microSD card on the Inkplate 13, in colour.

Connection: a microSD card in the slot on the board, with a file called cosmic-cliffs.jpg on it.
Picture:    Cosmic Cliffs, NASA / ESA / CSA / STScI, public domain. The manual has it cropped to 1600 x 1200, the original is at
            https://commons.wikimedia.org/wiki/File:NASA%E2%80%99s_Webb_Reveals_Cosmic_Cliffs,_Glittering_Landscape_of_Star_Birth.jpg
Board:      Soldered Inkplate 13, running the Inkplate MicroPython firmware
Library:    inkplate13spectra, installed with mpremote mip

Author: Borna Zelenika @ soldered.com
"""

# Pull in the os module for files, and the Inkplate library
import os
from inkplate13_spectra import Inkplate

# The display object
inkplate = Inkplate()

# The name of the picture on the card. It can be a JPG, PNG or BMP file.
PICTURE_NAME = "/sd/cosmic-cliffs.jpg"

# Start the display and turn it to landscape. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_rotation(1)
inkplate.set_text_color(inkplate.BLACK)
inkplate.set_text_size(2)

# Mount the card, under the folder /sd. If it did not mount, say so.
inkplate.init_sd_card()
if "sd" not in os.listdir("/"):
    inkplate.print_text(50, 50, "SD card error!")
else:
    # Draw the picture with its top left corner at 0, 0. The picture is 1600 x 1200 pixels,
    # so it fills the 1600 x 1200 screen. dither=True mixes dots of the
    # six colours, which makes the colours look smoother. If this fails, say so.
    try:
        inkplate.draw_image(PICTURE_NAME, 0, 0, dither=True)
    except OSError:
        inkplate.print_text(50, 50, "Could not open " + PICTURE_NAME)

# Send the frame buffer to the screen, then let the card sleep
inkplate.display()
inkplate.sd_card_sleep()
