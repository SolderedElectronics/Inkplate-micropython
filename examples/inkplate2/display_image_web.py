"""Connects to WiFi and renders an image fetched from a URL."""

import network
import time
from inkplate2 import Inkplate

# Enter your WiFi credentials here
SSID = "YOUR_SSID_HERE"
PASSWORD = "YOUR_PASSWORD_HERE"


# Connects to a WiFi network using given SSID and PASSWORD.
#
# Returns:
# - True if successfully connected
# - False if connection fails within the timeout period
#
# Notes:
# - Timeout is set to 30 seconds
# - Prints network IP config on success
def do_connect():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("Connecting to network...")
        sta_if.active(True)
        sta_if.connect(SSID, PASSWORD)

        timeout = 30  # seconds
        start = time.ticks_ms()
        while not sta_if.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                print("Failed to connect within timeout")
                return False
            time.sleep(0.5)
    print("Network config:", sta_if.ifconfig())
    return True


# Create Inkplate object in 2-bit (grayscale) mode
inkplate = Inkplate()

# Initialize the display, needs to be called only once
inkplate.begin()

# Connect to WiFi
if not do_connect():
    raise SystemExit("WiFi connection failed")

# Draw an image on the screen.
#
# Parameters:
# - path: File path to the image. Supports local paths (e.g., from SD card) or URLs.
#         Supported formats: JPG, PNG, BMP.
#
# - x0: X-coordinate of the top-left corner where the image will be displayed.
#
# - y0: Y-coordinate of the top-left corner where the image will be displayed.
#
# - invert (bool, default=False): If True, inverts the image colors.
#
# - dither (bool, default=False): If True, applies a dithering algorithm to
#   the image for better grayscale rendering.
#
# Performance Notes:
# - JPG: ~3 seconds (or ~5s with dithering)
# - PNG: ~4 seconds (or ~6s with dithering)
# - BMP: ~6 seconds (or ~7s with dithering)
# - Maximum image file size: ~800kB
#
# Example usage:
draw_length = time.ticks_ms()
inkplate.draw_image(
    "https://i.imgur.com/VSRtgBr.jpeg",  # URL to image
    0,
    0,  # X, Y position
    dither=True,  # Enable dithering
)
draw_length = time.ticks_ms() - draw_length
print("time it took to draw to buffer: {} ms ".format(draw_length))

# Show the image from the internal buffer
draw_length = time.ticks_ms()
inkplate.display()
draw_length = time.ticks_ms() - draw_length
print("time it took to display: {} ms ".format(draw_length))
