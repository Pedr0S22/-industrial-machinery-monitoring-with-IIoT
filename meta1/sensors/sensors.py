import paho.mqtt.client as mqtt_publish
import random
import time

# ==== Configuration ==== #
GROUP_ID = "01"
#BROKER = "10.6.1.9"
BROKER = "broker.hivemq.com"
PORT = 1883
INTERVAL = 2

# MQTT Topics
TOPIC_COOLANT = f"machine_{GROUP_ID}/coolant"
TOPIC_PRESSURE = f"machine_{GROUP_ID}/pressure"
TOPIC_RPM = f"machine_{GROUP_ID}/rpm"
TOPIC_STATUS = f"machine_{GROUP_ID}/status"

# Sensor simulation functions
current_temp = random.uniform(60, 80)
current_pressure = random.uniform(2, 5)

def generate_coolant_temp():
    global current_temp
    change = random.uniform(-2, 2)
    current_temp = max(10, min(200, current_temp + change))
    return round(current_temp, 2)

def generate_oil_pressure():
    global current_pressure
    change = random.uniform(-0.2, 0.2)
    current_pressure = max(0, min(8, current_pressure + change))
    return round(current_pressure, 2)


def generate_rpm():
    return random.randint(0, 4000)

# ==== MQTT client setup ==== #
client = mqtt_publish.Client(callback_api_version=mqtt_publish.CallbackAPIVersion.VERSION2)
client.will_set(TOPIC_STATUS, payload="offline", qos=1, retain=True)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT Broker")
    else:
        print(f"Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc, properties=None, packet_from_broker=False):
    print(f"Disconnected from broker, return code: {rc}")
    if packet_from_broker:
        print("The disconnect was initiated by the broker.")
    else:
        print("The disconnect was initiated by the client.")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    client.connect(BROKER, PORT, keepalive=10)
    client.loop_start()

    while True:
        temp = generate_coolant_temp()
        pressure = generate_oil_pressure()
        rpm = generate_rpm()

        client.publish(TOPIC_COOLANT, temp)
        client.publish(TOPIC_PRESSURE, pressure)
        client.publish(TOPIC_RPM, rpm)
        client.publish(TOPIC_STATUS, "online", retain=True)

        print(f"Sent - Temp: {temp} °C | Pressure: {pressure} bar | RPM: {rpm}")
        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("Stopping sensor simulator...")

except Exception as e:
    print(f"Error: {e}")

finally:

    client.loop_stop()
    client.disconnect()
    print("MQTT client disconnected.")
