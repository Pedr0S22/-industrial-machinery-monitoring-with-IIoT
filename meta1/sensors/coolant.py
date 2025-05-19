import paho.mqtt.client as mqtt_publish
import random
import time

# ==== Configuration ==== #
GROUP_ID = "19"
BROKER = "10.6.1.9"
#BROKER = "broker.emqx.io"
PORT = 1883
INTERVAL = 2

connected = False

# MQTT Topics
TOPIC_COOLANT = f"machine_{GROUP_ID}/coolant"
TOPIC_STATUS = f"machine_{GROUP_ID}/status/coolant"

# Sensor simulation functions
current_temp = random.uniform(95, 100)

# TEST ONLY
current_temp = 97

def generate_coolant_temp():
    global current_temp
    change = random.uniform(-2, 2)
    current_temp = max(10, min(200, current_temp + change))
    return round(current_temp, 2)

# ==== MQTT client setup ==== #
client = mqtt_publish.Client(callback_api_version=mqtt_publish.CallbackAPIVersion.VERSION2)
client.will_set(TOPIC_STATUS, payload="offline", qos=1, retain=True)
client.will_set(TOPIC_COOLANT, 0, qos=1, retain=True)

def on_connect(client, userdata, flags, rc, properties=None):
    global connected
    if rc == 0:
        connected = True
        print("Connected to MQTT Broker")
        client.publish(TOPIC_STATUS, "online", qos=1, retain=True)
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

    while not connected:
        print("Waiting for MQTT connection...")
        time.sleep(5)

    while True:
        temp = generate_coolant_temp()

        client.publish(TOPIC_COOLANT, temp)

        print(f"Sent - Temp: {temp} °C")
        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("Stopping sensor simulator...")

except Exception as e:
    print(f"Error: {e}")

finally:

    client.loop_stop()
    client.publish(TOPIC_STATUS, "offline", retain=True)
    client.publish(TOPIC_COOLANT, 0, qos=1, retain=True)
    client.disconnect()
    print("MQTT client disconnected.")
