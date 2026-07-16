"""Read accelerometer, gyro, and temperature from the onboard LSM6DS3."""

# Include required libraries
import time
from inkplate4tempera import Inkplate
from lsm6ds3 import LSM6DS3

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
display.begin()

# Sensors are asleep by default -- wake_peripheral() runs the chip's real begin()
display.wake_peripheral(Inkplate.INKPLATE_ACCELEROMETER)

for _ in range(20):
    x, y, z = display.read_accelerometer()
    print("Accel (g): x={:.3f} y={:.3f} z={:.3f}".format(x, y, z))
    print(
        "Gyro (dps): x={:.3f} y={:.3f} z={:.3f}".format(
            LSM6DS3.read_float_gyro_x(), LSM6DS3.read_float_gyro_y(), LSM6DS3.read_float_gyro_z()
        )
    )
    print("Temperature: {:.2f} C".format(LSM6DS3.read_temp_c()))
    time.sleep(0.5)

display.sleep_peripheral(Inkplate.INKPLATE_ACCELEROMETER)
