import paho.mqtt.client as mqtt
import time

# ==== Configuration ==== #
GROUP_ID = "19"
BROKER = "10.6.1.9"
#BROKER = "broker.emqx.io"
PORT = 1883
TOPIC_CONTROLLER = f"machine_{GROUP_ID}/controller"

# MQTT callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT Broker")
    else:
        print(f"Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc, properties=None, packet_from_broker=False):
    print(f"Disconnected from broker with return code {rc}")

# ==== MQTT Client Setup ==== #
client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    # Connect to MQTT Broker
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    while True:
        command = input("Enter command (ON/OFF): ").strip().upper()
        if command == 'ON':
            client.publish(TOPIC_CONTROLLER, "ON")
            print("Alarm activated.")
        elif command == 'OFF':
            client.publish(TOPIC_CONTROLLER, "OFF")
            print("Alarm deactivated.")
        else:
            print("Invalid command. Please enter 'ON' or 'OFF'.")
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping controller...")

except Exception as e:
    print(f"Error: {e}")

finally:

    client.loop_stop()
    client.disconnect()
    print("MQTT client disconnected.")

