from soldered_inkplate6_PLUS import Inkplate
from image import *
import time

display = Inkplate(Inkplate.INKPLATE_1BIT)


#main function used by micropython
if __name__ == "__main__":
    display.begin()
    display.tsInit(1)
    display.drawRect(450, 350, 100, 100, display.BLACK)
    display.display()

    
    counter = 0 
    
    while True:
        #touch the square
        if(display.touchInArea(450, 350, 100, 100)):
            counter += 1
            print(counter)