import paho.mqtt.client as mqtt
from datetime import datetime

class MQTTDebugger:
    def __init__(self, group_id):
        self.group_id = group_id
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print(f"Debugger connected to broker (rc={rc})")
        # Subscribe to all relevant topics
        client.subscribe(f"v3/{self.group_id}@ttn/devices/+/up")
        client.subscribe(f"v3/{self.group_id}@ttn/devices/+/down/+")
        client.subscribe(f"{self.group_id}/internal/#")
        print("Subscribed to all monitoring topics")

    def _on_message(self, client, userdata, msg):
        """Print all messages with timestamp"""
        print(f"[{datetime.now().isoformat()}] {msg.topic}: {msg.payload.decode()}")

    def run(self):
        self.client.connect(MQTT_BROKER_IP, MQTT_PORT)
        self.client.loop_forever()

if __name__ == "__main__":
    # ===== CONFIGURATION =====
    MQTT_BROKER_IP = "10.6.1.9"
    MQTT_PORT = 1883
    GROUP_ID = "19"
    
    debugger = MQTTDebugger(GROUP_ID)
    print("MQTT Debugger started. Monitoring all messages...")
    debugger.run()