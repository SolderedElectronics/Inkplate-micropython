"""Swap in one of the extra typefaces shipped under fonts/ instead of the default font.

fonts/ isn't installed by default -- fetch the one file you want directly:

    mpremote mip install github:SolderedElectronics/Inkplate-micropython/fonts/free_serif_24px.py

Any other file under fonts/ works the same way; see that directory for the full
family/size list (FreeMono/FreeSans/FreeSerif, regular/bold/oblique/italic, 12-48px).
"""

from inkplate6 import Inkplate
import free_serif_24px

inkplate = Inkplate(Inkplate.INKPLATE_2BIT)
inkplate.begin()

inkplate.set_text_size(1)
inkplate.set_cursor(250, 250)
inkplate.print("Default font")

inkplate.set_font(free_serif_24px)
inkplate.set_cursor(250, 300)
inkplate.print("Custom font!")

inkplate.display()
