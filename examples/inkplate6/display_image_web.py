"""Download a picture from the web and show it on the Inkplate 6, in eight levels of gray.

Connection: none. Needs a Wi-Fi network.
Picture:    A coastal town, from the Inkplate examples on GitHub, 800 x 600 pixels.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the modules for the pauses and the Wi-Fi, and the Inkplate library
import time
import network
from inkplate6 import Inkplate

# The name and the password of your Wi-Fi network
ssid = ""
password = ""

# The web address of the picture. It has to point straight at a JPG, PNG or BMP file.
PICTURE_URL = "https://learn.soldered.com/inkplate-6/files/coastal-town.jpg"

# Gray mode: eight levels, 0 (black) to 7 (white). Pictures need it to look right.
inkplate = Inkplate(Inkplate.INKPLATE_2BIT)

# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_text_color(0)
inkplate.set_text_size(2)

# Join the Wi-Fi network
station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)
while not station.isconnected():
    time.sleep(0.5)

# Download the picture and draw it with its top left corner at 0, 0, which fills the screen,
# because the picture is 800 x 600 pixels. dither=True mixes black and white dots, which makes
# the grays look smoother. If the download or the drawing fails, say so.
try:
    inkplate.draw_image(PICTURE_URL, 0, 0, dither=True)
except OSError:
    inkplate.print_text(50, 50, "Could not download the picture")

# Send the frame buffer to the screen, then turn the Wi-Fi off to save power
inkplate.display()
station.active(False)
