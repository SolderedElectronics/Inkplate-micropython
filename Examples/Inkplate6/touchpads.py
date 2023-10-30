# This example shows you how to use the touchpads
# Only older models of Inkplate6 (e-Radionica Inkplate 6) have them

# Include required libraries
from inkplate6 import Inkplate

# Create Inkplate object in 1-bit mode, black and white colors only
# For 2-bit grayscale, see basicGrayscale.py
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Create some coordinates and a radius for drawing a circle
circle_x = 400
circle_y = 300
circle_r = 40

# Main function
if __name__ == "__main__":
    
    # Initialize the display, needs to be called only once
    display.begin()

    # Clear the frame buffer
    display.clearDisplay()

    # This has to be called every time you want to update the screen
    # Drawing or printing text will have no effect on the display itself before you call this function
    display.display()

    # Function to show text at the top of the screen
    # Needs to be called every time we clear the display to re-draw the text
    def draw_top_text():
        display.setTextSize(2)
        display.printText(100, 10, "TOUCHPADS EXAMPLE! 1, 3 TO MOVE CIRCLE, 2 TO RESET")
    
    # Call it
    draw_top_text()

    # Touchpads definitions
    touch1, touch2, touch3 = display.TOUCH1, display.TOUCH2, display.TOUCH3
    
    # Draw the initial circle for touchpad demonstration
    display.drawCircle(circle_x, circle_y, circle_r, display.BLACK)

    # Show everything on the display
    display.display()

    # Start infinite loop
    while True:
        # If a touchpad is pressed, move the circle and redraw everything
        # Touch 1 moves the circle to the left
        if touch1():
            circle_x -= 40
            display.clearDisplay()
            draw_top_text()
            display.drawCircle(circle_x, circle_y, circle_r, display.BLACK)
            # Show on the display!
            # Use display.partialUpdate instead of display.display() to draw only updated pixels
            # This makes for a faster update
            # IMPORTANT: the display should be fully updated every ~10 partialUpdates with display.display()
            # This ensures the image retains it's quality
            display.partialUpdate()

        # Touch 2 will reset the position of the circle
        if touch2():
            circle_x = 400
            circle_y = 300
            circle_r = 40
            display.clearDisplay()
            draw_top_text()
            display.drawCircle(circle_x, circle_y, circle_r, display.BLACK)
            display.display() # Do a full refresh also

        # Touch 3 will move the circle to the right
        if touch3():
            circle_x += 40
            display.clearDisplay()
            draw_top_text()
            display.drawCircle(circle_x, circle_y, circle_r, display.BLACK)
            display.partialUpdate()