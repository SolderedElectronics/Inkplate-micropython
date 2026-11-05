"""Show the current weather in a city on the Inkplate 10, from the free Open-Meteo service.

Connection: none. Needs a Wi-Fi network.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the modules for the pauses, the Wi-Fi and web requests, and the Inkplate library
import time
import network
import requests
from inkplate10 import Inkplate

# The name and the password of your Wi-Fi network
ssid = ""
password = ""

# The city to show the weather for. Use only its name, without spaces.
CITY = "Osijek"

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)


# Turn the weather code of Open-Meteo into a few words
def describe(code):
    if code == 0:
        return "Clear sky"
    if code <= 3:
        return "Partly cloudy"
    if code <= 48:
        return "Fog"
    if code <= 57:
        return "Drizzle"
    if code <= 67:
        return "Rain"
    if code <= 77:
        return "Snow"
    if code <= 82:
        return "Rain showers"
    if code <= 86:
        return "Snow showers"
    return "Thunderstorm"


# Stop with a message on the screen
def fail(message):
    inkplate.print_text(50, 50, message)
    inkplate.display()
    raise SystemExit


# Ask a web address for JSON. Returns None if anything goes wrong. The address starts with
# https, so the connection is encrypted.
def get_json(address):
    response = requests.get(address)
    if response.status_code != 200:
        response.close()
        return None

    # The answer is JSON text. json() turns it into dictionaries and lists we can pick values out of.
    data = response.json()
    response.close()
    return data


# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_text_size(2)

# Join the Wi-Fi network
station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)
while not station.isconnected():
    time.sleep(0.5)

# Ask Open-Meteo's search for the position of the city
place = get_json("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + CITY)
if place is None:
    fail("Could not look up the city")
if "results" not in place:
    fail("City not found")
latitude = place["results"][0]["latitude"]
longitude = place["results"][0]["longitude"]

# Ask Open-Meteo for the current weather at that position
weather_url = (
    "https://api.open-meteo.com/v1/forecast?latitude={:.4f}&longitude={:.4f}"
    "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto"
).format(latitude, longitude)
weather = get_json(weather_url)
if weather is None:
    fail("Could not get the weather")

# Pick out the values we want
temperature = weather["current"]["temperature_2m"]
humidity = int(weather["current"]["relative_humidity_2m"])
wind = weather["current"]["wind_speed_10m"]
code = weather["current"]["weather_code"]

# Draw the card: one line for each value, all in the same size
inkplate.clear_display()
inkplate.set_text_size(4)
inkplate.print_text(80, 120, CITY)
inkplate.print_text(80, 250, "Temperature: {:.1f} C".format(temperature))
inkplate.print_text(80, 380, describe(code))
inkplate.print_text(80, 510, "Humidity: " + str(humidity) + " %")
inkplate.print_text(80, 640, "Wind: {:.1f} km/h".format(wind))

# Send the frame buffer to the screen
inkplate.display()
