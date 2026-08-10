"""Connect to WiFi and POST a field value to ThingSpeak over a socket."""

from inkplate6_color import Inkplate
import network
import socket
import time

# Replace with your credentials
SSID = ""
PASSWORD = ""

# ThingSpeak Write API key
API_KEY = ""

# Initialize Inkplate
inkplate = Inkplate()
inkplate.begin()


def do_connect():
    connected = False
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("Connecting to network...")
        sta_if.active(True)
        try:
            sta_if.connect(SSID, PASSWORD)
        except Exception as e:
            print(f"Wi-Fi connect error: {e}\n")
            print("Check your credentials!")
        else:
            timeout = 30  # seconds
            start = time.ticks_ms()

            while not sta_if.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                    print("Failed to connect within timeout")
                    break
                time.sleep(0.5)
            else:
                connected = True
    else:
        connected = True

    if connected:
        print(f"CONNECTED: \n{sta_if.ifconfig()}")
        return True
    else:
        return False


# Function to sent HTTP Post request
def http_post(url, data, host):
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()  # Create a TCP socket
    s.connect(addr)  # Connect to server (ThingSpeak)

    # Build HTTP POST request
    request = (
        "POST /update HTTP/1.1\r\n"  # Method (POST), path (/update), protocol (HTTP/1.1)
        "Host: " + host + "\r\n"  # Specify host
        "Content-Type: application/x-www-form-urlencoded\r\n"  # Data format to send
        "Content-Length: " + str(len(data)) + "\r\n"  # Content length
        "Connection: close\r\n\r\n"  # Close connection after response + end of header
         + data  # The actual data
    )

    s.send(bytes(request, "utf8"))  # Send full HTTP request
    res = ""
    while True:
        buf = s.recv(100)  # Read server response
        if not buf:
            break
        res += str(buf, "utf8")

    s.close()  # Close the socket
    return res  # Return server Response


# Connect to WiFi
if not do_connect():
    raise SystemExit("WiFi connection failed")

# Example: update field1 with value 125
payload = "api_key={}&field1={}".format(API_KEY, 125)

response = http_post("http://api.thingspeak.com/update", payload, "api.thingspeak.com")

# Display HTTP response data
inkplate.print(response)
inkplate.display()
