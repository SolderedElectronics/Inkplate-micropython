"""Read proximity and gesture direction from the onboard APDS9960."""

# Include required libraries
import time
from inkplate4tempera import Inkplate
from apds9960 import APDS9960, DIR_NONE

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
display.begin()

# Sensors are asleep by default -- wake_peripheral() only powers the chip on;
# the real SparkFun library expects the caller to init()/begin() it themselves
display.wake_peripheral(Inkplate.INKPLATE_APDS9960)
APDS9960.begin()
APDS9960.enable_proximity_sensor()
APDS9960.enable_gesture_sensor()

print("Wave a hand over the sensor...")
# NOTE: read_gesture() can block indefinitely if the chip's gesture-valid flag
# never clears (observed under strong ambient IR/sunlight on real hardware --
# a documented APDS9960 limitation, not specific to this port). Shield the
# sensor from direct light if this loop seems to hang.
for _ in range(100):
    gesture = APDS9960.read_gesture()
    if gesture != DIR_NONE:
        print("Gesture:", gesture)
    print("Proximity:", display.read_proximity())
    time.sleep(0.2)

display.sleep_peripheral(Inkplate.INKPLATE_APDS9960)
