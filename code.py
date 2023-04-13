import time
import board
import adafruit_sgp40
import pwmio
from adafruit_motor import servo
import adafruit_ahtx0
import adafruit_dotstar
import ipaddress
import ssl
import wifi
import socketpool
import adafruit_requests
from secrets import secrets
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import gc


DEBUG = True

if(DEBUG == True):
	print("\n\n\n\n")

### you may need to customize these ###
air_boundry = 120 # sets the point at which we declare "bad quality air"
live_angle = 180 # angle at which the bird is "up"
dead_angle = 0 # angle at which the bird is "down"

i2c = board.I2C()  # uses board.SCL and board.SDA

# This is our SGP40 air quality sensor
sgp = adafruit_sgp40.SGP40(i2c)

# this is our temp/humidity sensor
aht = adafruit_ahtx0.AHTx0(board.I2C())

# setup the onboard neopixel
# pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel = adafruit_dotstar.DotStar(board.APA102_SCK, board.APA102_MOSI, 1)

pixel.brightness = 0.2
pixel.fill((255, 255, 255))

# create a PWMOut object on Pin A0.
pwm = pwmio.PWMOut(board.D4, duty_cycle=2 ** 15, frequency=50) 

# Create a servo object, my_servo.
bird = servo.Servo(pwm,min_pulse = 500, max_pulse = 2300)

# don't change these unless you know what you're doing
status = "DIRTY"
old_status = status

# default to "dead" until we have a clear reading
bird.angle = dead_angle
time.sleep(1)


# sane defaults
temperature = 21
humidity = 50


if(DEBUG == True):
	print("Memory:", gc.mem_free())


# Define callback methods which are called when events occur
# pylint: disable=unused-argument, redefined-outer-name
def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    if(DEBUG == True):
	    print("Connected to " + secrets["mqtt_broker"] + " Listening for topic changes on " + secrets["mqtt_topic"])
    # Subscribe to all changes on the onoff_feed.
    client.subscribe(secrets["mqtt_topic"])

def disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    if(DEBUG == True):
	    print("Disconnected from" + secrets["mqtt_broker"])

def message(client, topic, message):
    # This method is called when a topic the client is subscribed to
    # has a new message.
    if(DEBUG == True):
	    print("New message on topic {0}: {1}".format(topic, message))

if(DEBUG == True):
	print("Connecting to %s"%secrets["wifi_ssid"])

try:
	# connect to wifi
	wifi.radio.connect(secrets["wifi_ssid"], secrets["wifi_password"])
	print("Connected to %s!"%secrets["wifi_ssid"])
	print("My IP address is", wifi.radio.ipv4_address)
	online = True
except:
	print("There is no wifi, only zool")
	online = False

if(online == True):
	# Create a socket pool
	pool = socketpool.SocketPool(wifi.radio)

if(DEBUG == True):
	print("="*26)
	print(" THE BIRD IS THE WORD")
	print("="*26)



if(online == True):

	# Set up a MiniMQTT Client
	mqtt_client = MQTT.MQTT(
	    broker = secrets["mqtt_broker"],
	    port = secrets["mqtt_port"],
	    username = secrets["mqtt_username"],
	    password = secrets["mqtt_password"],
	    socket_pool = pool,
	    ssl_context = ssl.create_default_context(),
	    keep_alive = 120
	)

	# Setup the callback methods above
	mqtt_client.on_connect = connected
	mqtt_client.on_disconnect = disconnected
	mqtt_client.on_message = message


	# Connect the client to the MQTT broker.
	try:
		mqtt_client.connect()
	except:
		print("Could not find MQTT broker (%s)" % (secrets["mqtt_broker"]))
		online = False



while True:

	# getting temp and humidity for more acurate air quality readings
	temperature = aht.temperature
	humidity = aht.relative_humidity

	# return int The VOC index measured, ranged from 0 to 500
	compensated_raw_gas = sgp.measure_raw(temperature = temperature, relative_humidity = humidity)
	raw_gas = sgp.raw

	voc = sgp.measure_index(temperature = temperature, relative_humidity = humidity)

	# it takes a minute or so for the sensor to warm up
	# so we don't do anything until we get a reading
	if(voc > 10):
		
		print("")

		if(DEBUG == True):
			print("Memory:", gc.mem_free())


		if(voc >= air_boundry):
			status = "DIRTY"
			pixel.fill((255, 0, 0))
		else:
			status = "CLEAN"
			pixel.fill((0, 255, 0))

		# print for debugging
		if(DEBUG == True):
			print("THE AIR IS", status, "! \t", "Raw Gas: ", raw_gas, " \t VOC: ", voc, " \t Temp:", round(temperature,2), " \t Humidity: ", round(humidity,2))

		if(status == "DIRTY" and old_status == "CLEAN"):
			# kill the bird
			bird.angle = dead_angle
			if(DEBUG == True):
				print("MURDERING THE BIRD")
		
		if(status == "CLEAN" and old_status == "DIRTY"):
			# revivive the bird
			bird.angle = live_angle	
			if(DEBUG == True):
				print("THE BIRD IS REBORN")	

		# save the status for the next loop so we can conpare
		old_status = status

		if(online == True):

			# Poll the message queue
			mqtt_client.loop()

			if(DEBUG == True):
				# Send a new message
				print("SENDING VALUE")

			mqtt_msg = """
{
	\"status\" : \"%s\",
	\"gas\" : %s,
	\"voc\" : %s,
	\"temperature\" : %s,
	\"humidity\" : %s,
	\"memory\" : %s 	
 }""" % (status, str(raw_gas), str(voc), str(round(temperature,2)), str(round(humidity,2)), gc.mem_free())


 			try:
				mqtt_client.publish(secrets["mqtt_topic"], mqtt_msg)
			except:
				mqtt_client.connect()

			if(DEBUG == True):
				print("SENT!")

			time.sleep(10)

		else:
			time.sleep(1)

		gc.collect()

	else:

		print(".", end="")
		time.sleep(1)