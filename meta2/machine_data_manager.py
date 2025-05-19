import paho.mqtt.client as mqtt
import json
import sys
from datetime import datetime

class MachineDataManager:
    def __init__(self, group_id, intervals):
        self.group_id = group_id
        self.mqtt_client = mqtt.Client()
        
        # Healthy intervals configuration
        self.healthy_ranges = intervals
        
        # MQTT topics
        self.data_topic = f"{group_id}/internal/machine_data"
        self.control_topic = f"{group_id}/internal/control_commands"
        
        # MQTT callbacks
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        # Alarm tracking
        self.alarm_history = {}

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        self.mqtt_client.subscribe(self.data_topic)
        print(f"Subscribed to topic: {self.data_topic}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"Received data from DataManagerAgent:\n{payload}")
            self._process_machine_data(payload)
        except Exception as e:
            print(f"Error processing message: {e}")

    def _process_machine_data(self, payload):
        """Analyze sensor data and send control commands if needed"""
        machine_id = payload["machine_id"]
        sensor_data = payload["sensor_data"]
        
        print(f"Analyzing data from {machine_id}")
        
        # Check each parameter against healthy ranges
        for param, value in sensor_data.items():
            if param in self.healthy_ranges:
                healthy = self.healthy_ranges[param]
                
                # Check if value is outside healthy range
                if value < healthy["low"] or value > healthy["high"]:
                    adjustment = self._calculate_adjustment(param, value, healthy)
                    self._send_control_command(machine_id, param, adjustment)

    def _calculate_adjustment(self, param, current_value, healthy_range):
        """Returns adjustment value with protective bounds"""
        ideal = healthy_range["ideal"]
        adjustment = ideal - current_value
        
        # Apply parameter-specific bounds
        bounds = {
            "rpm": (-128, 127),
            "coolant_temp": (-10, 10),
            "oil_pressure": (-2, 2),
            "battery_potential": (-1, 1),
            "consumption": (-5, 5)
        }.get(param, (-50, 50))
        
        return max(bounds[0], min(adjustment, bounds[1]))

    def _send_control_command(self, machine_id, param, adjustment):
        """Send control command to Data Manager Agent"""
        command = {
            "machine_id": machine_id,
            "modify_param": param,
            "adjustment": round(adjustment,2),
            "timestamp": datetime.now().isoformat()
        }
        
        self.mqtt_client.publish(self.control_topic, json.dumps(command))
        print(f"Sent control command to {machine_id}: {param} by {adjustment}")

    def run(self):
        """Start the manager"""
        self.mqtt_client.connect(MQTT_BROKER_IP, MQTT_PORT)
        self.mqtt_client.loop_forever()


if __name__ == "__main__":

    # ===== MACHINE CONFIGURATION =====
    intervals_path = "config/intervals.json"

    try:
        with open(intervals_path, "r", encoding="utf-8") as f:
            INTERVALS =  json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
            print("File not found/invalid")
            INTERVALS = {}
            sys.exit(1)

    # ===== MQTT CONFIG =====
    MQTT_BROKER_IP = "10.6.1.9"
    MQTT_PORT = 1883
    GROUP_ID = "19"

    manager = MachineDataManager(GROUP_ID,INTERVALS)
    manager.run()