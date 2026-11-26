"""Send the temperature of the Inkplate 6 to a test server in a POST request, and show the answer.

Connection: none. Needs a Wi-Fi network.

Author: Borna Zelenika @ soldered.com
"""

# Pull in the modules for the pauses, the Wi-Fi and web requests, and the Inkplate library
import time
import network
import requests
from inkplate6 import Inkplate

# The name and the password of your Wi-Fi network
ssid = ""
password = ""

# The test server. It accepts what you send and answers as if it had saved it, but it keeps nothing.
SERVER_URL = "https://jsonplaceholder.typicode.com/posts"

# Black and white mode: a colour is inkplate.BLACK or inkplate.WHITE
inkplate = Inkplate(Inkplate.INKPLATE_1BIT)


# Stop with a message on the screen
def fail(message):
    inkplate.print_text(50, 50, message)
    inkplate.display()
    raise SystemExit


# Start the display. begin() leaves the frame buffer empty and white.
inkplate.begin()
inkplate.set_text_size(2)

# Join the Wi-Fi network
station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)
while not station.isconnected():
    time.sleep(0.5)

# Read the temperature of the board and round it to a whole number of degrees Celsius
temperature = int(inkplate.read_temperature())

# Build the message to send: a dictionary with two names and their values
message = {"title": "Inkplate temperature", "body": str(temperature) + " C"}

# Send it with a POST request. json=message turns the dictionary into JSON text and tells the
# server that the body is JSON. If the request never reaches the server, say so.
try:
    response = requests.post(SERVER_URL, json=message)
except OSError:
    fail("Could not reach the server")

# Read the answer: the server sends back what it received, and adds an id of its own
status = response.status_code
answer = response.json()
response.close()
server_id = answer["id"]

# Draw the result: one line for each value, all in the same size
inkplate.set_text_size(3)
inkplate.print_text(60, 100, "POST request")
inkplate.print_text(60, 200, "Sent: " + str(temperature) + " C")
inkplate.print_text(60, 300, "Status: " + str(status))
inkplate.print_text(60, 400, "Server id: " + str(server_id))

# Send the frame buffer to the screen
inkplate.display()
