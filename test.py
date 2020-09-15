from inkplate import Inkplate

display = Inkplate(Inkplate.INKPLATE_1BIT)

if __name__ == "__main__":
    display.begin()

    for x in range(100):
        display.writePixel(100, x, 1)

    display.display()

