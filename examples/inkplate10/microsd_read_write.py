"""Add a line to a log file on the microSD card every time the script runs, then show

how many lines the file has, how big the card is and which files are on it.
Connection: a microSD card in the slot on the board.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the os module for files, and the Inkplate library
import os
from inkplate10 import Inkplate

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)

# The name of the log file and the line added to it on every run
FILE_NAME = "/sd/example.txt"
LOG_LINE = "Hello from Inkplate!\n"


# Stop with a message on the screen
def fail(message):
    inkplate.print_text(50, 50, message)
    inkplate.display()
    raise SystemExit


# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_text_size(2)

# Mount the card, under the folder /sd. If it did not mount, say so and stop.
inkplate.init_sd_card()
if "sd" not in os.listdir("/"):
    fail("SD card error!")

# Open the file for writing. The mode "a" adds to the end instead of starting over, and
# creates the file the first time. The with block closes the file afterwards.
with open(FILE_NAME, "a") as card_file:
    card_file.write(LOG_LINE)

# Open the file again for reading, and count the lines
lines = 0
with open(FILE_NAME, "r") as card_file:
    for line in card_file:
        lines += 1

# The size of the file in bytes is the seventh value of os.stat()
file_bytes = os.stat(FILE_NAME)[6]

# The size of the card, in megabytes: the size of a block times the number of blocks
card_info = os.statvfs("/sd")
card_megabytes = card_info[1] * card_info[2] // 1048576

# Show the results, one line every 48 pixels
y = 50
inkplate.print_text(50, y, "Card size: " + str(card_megabytes) + " MB")
y += 48
inkplate.print_text(50, y, "example.txt: " + str(lines) + " lines, " + str(file_bytes) + " bytes")
y += 96
inkplate.print_text(50, y, "Files on the card:")
y += 48

# Go through the root folder of the card, one entry at a time
for name in os.listdir("/sd"):
    size = os.stat("/sd/" + name)[6]
    inkplate.print_text(50, y, "  " + name + "  " + str(size) + " bytes")
    y += 48

# Send the frame buffer to the screen, then let the card sleep
inkplate.display()
inkplate.sd_card_sleep()
