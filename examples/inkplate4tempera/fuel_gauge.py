"""Read the battery voltage and state of charge from the onboard fuel gauge."""

# Include required libraries
from inkplate4tempera import Inkplate

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
display.begin()

# Sensors are asleep by default -- wake the fuel gauge before reading it
display.wake_peripheral(Inkplate.INKPLATE_FUEL_GAUGE)

print("Battery voltage: {:.3f}V".format(display.read_battery()))
print("Battery state of charge: {}%".format(display.read_battery_soc()))

# Put it back to sleep when done
display.sleep_peripheral(Inkplate.INKPLATE_FUEL_GAUGE)
