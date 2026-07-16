"""Read temperature, humidity, pressure and gas resistance from the onboard BME688."""

# Include required libraries
from inkplate4tempera import Inkplate
from bme688 import BME688

# Create Inkplate object in 1-bit (black and white) mode
display = Inkplate(Inkplate.INKPLATE_1BIT)

# Initialize the display, needs to be called only once
display.begin()

# Sensors are asleep by default -- wake the BME688 before reading it (runs its
# real begin(): soft reset, calibration read, TPH/filter/heater config)
display.wake_peripheral(Inkplate.INKPLATE_BME688)

temperature, humidity, pressure, gas = BME688.read_sensor_data()
print("Temperature: {:.2f} C".format(temperature))
print("Humidity: {:.2f} %".format(humidity))
print("Pressure: {:.2f} hPa".format(pressure))
print("Gas resistance: {:.2f}".format(gas))

# Put it back to sleep when done
display.sleep_peripheral(Inkplate.INKPLATE_BME688)
