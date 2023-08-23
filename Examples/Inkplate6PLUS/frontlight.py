from inkplate6PLUS import Inkplate
import time
display = Inkplate(Inkplate.INKPLATE_1BIT)

if __name__ == "__main__":
    # Must be called before using, line in Arduino
    display.begin()
    #display.clearDisplay()
    #display.display()

    display.frontlight(True)
    
    for i in range(0, 60):
        display.setFrontlight(10)
        time.sleep(2)
    display.frontlight(False)