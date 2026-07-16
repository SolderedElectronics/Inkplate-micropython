"""Draw a small pre-packed color image buffer directly onto the screen.

draw_color_image() takes a raw 4bpp buffer (2 pixels per byte, row-major, high
nibble first) instead of decoding a file -- useful for small pre-rendered
icons/patterns baked directly into your code instead of loaded from SD/web.
"""

from inkplate13_spectra import Inkplate

inkplate = Inkplate()
inkplate.begin()

# Build a small pixel image cycling through all 6 available colors in vertical
# stripes, two pixels packed per byte (high nibble = first pixel, low nibble =
# second). Sized 180x90 so the stripes are clearly visible on screen.
IMG_WIDTH = 180
IMG_HEIGHT = 90
colors = [
    Inkplate.BLACK,
    Inkplate.WHITE,
    Inkplate.YELLOW,
    Inkplate.RED,
    Inkplate.BLUE,
    Inkplate.GREEN,
]

stripe_width = IMG_WIDTH // len(colors)
bytes_per_row = IMG_WIDTH // 2
image = bytearray(bytes_per_row * IMG_HEIGHT)
for y in range(IMG_HEIGHT):
    for xb in range(bytes_per_row):
        c1 = colors[min((2 * xb) // stripe_width, len(colors) - 1)]
        c2 = colors[min((2 * xb + 1) // stripe_width, len(colors) - 1)]
        image[y * bytes_per_row + xb] = (c1 << 4) | c2

# Draw it near the top-left corner
inkplate.draw_color_image(50, 50, IMG_WIDTH, IMG_HEIGHT, image)

inkplate.display()
