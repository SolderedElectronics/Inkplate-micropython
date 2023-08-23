# This example shows you how to use the touchscreen on Inkplate6PLUS!

# Include needed libraries
from inkplate6PLUS import Inkplate

# Create Inkplate object in 1-bit mode, black and white colors only
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Main function
if __name__ == "__main__":
    
    # Initialize the display, needs to be called only once
    display.begin()

    # Clear the frame buffer
    display.clearDisplay()

    # This has to be called every time you want to update the screen
    # Drawing or printing text will have no effect on the display itself before you call this function
    display.display()

    # Initialize the touchscreen
    display.tsInit(1)

    # Draw a rectangle right in the middle of the screen and show it
    display.drawRect(450, 350, 100, 100, display.BLACK)
    display.display()

    # Every time the user touches that rectangle, print a message
    # The messags get printed to the terminal where the script was ran from
    # Create the variable which counts how many times the rectangle was touched
    counter = 0 
    while True:
        # If a touch on the square was detected
        if(display.touchInArea(450, 350, 100, 100)):
            # Increment the counter and print a message
            counter += 1
            print("Touch detected! Touch #: "+str(counter))