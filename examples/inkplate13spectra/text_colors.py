"""Display text in different colors, sizes, and with wrapping enabled/disabled."""

from inkplate13_spectra import Inkplate

inkplate = Inkplate()
# Initialize the display, needs to be called only once
inkplate.begin()

# Clear the frame buffer
inkplate.clear_display()
inkplate.display()


inkplate.set_cursor(50, 50)
inkplate.set_text_size(1)
inkplate.set_text_color(3)  # red
inkplate.print("Size 1")

inkplate.set_cursor(50, 100)
inkplate.set_text_size(2)
inkplate.set_text_color(4)  # blue
inkplate.print("Size 2")

inkplate.set_cursor(50, 180)
inkplate.set_text_size(3)
inkplate.set_text_color(5)  # green
inkplate.print("Size 3")

inkplate.set_text_color(0)  # black
long_text = (
    "This is a very long line of text intended to demonstrate how wrapping works. "
    "When wrap mode is enabled, the text will continue onto the next line once it "
    "reaches the edge of the display. This makes it possible to write paragraphs "
    "or larger blocks of text without worrying about manually inserting line breaks. "
    "It is especially useful for rendering user interfaces, menus, or e-books."
)
inkplate.set_cursor(50, 340)
inkplate.set_text_size(1)
inkplate.set_text_wrapping(True)
inkplate.print(long_text)

inkplate.set_cursor(50, 460)
inkplate.set_text_size(1)
inkplate.set_text_wrapping(False)
inkplate.print(long_text)

inkplate.display()
