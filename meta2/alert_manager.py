import socket
import json
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from collections import defaultdict
import threading

class AlertManager:
    def __init__(self, group_id, udp_ip, udp_port):
        self.group_id = group_id
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.control_topic = f"{group_id}/internal/control_commands"
        
        # Alert configuration
        self.alert_thresholds = {
            "CRITICAL": {
                "count": 5,         # 5 alarms in
                "window": 120       # 2 minutes (120 seconds)
            }
        }
        
        # Alarm tracking
        self.alarm_history = defaultdict(list)
        self.cooldowns = defaultdict(lambda: False)
        
        # MQTT client for monitoring control commands
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(self.control_topic)
        print(f"Subscribed to control topic: {self.control_topic}")

    def _on_mqtt_message(self, client, userdata, msg):
        """Track all control commands as potential alarms"""
        try:
            command = json.loads(msg.payload.decode())
            print(f"command received by MachineDataManager: {command}")
            machine_id = command["machine_id"]
            self._record_alarm(machine_id)
            self._check_alarm_condition(machine_id)
        except Exception as e:
            print(f"Error processing control command: {e}")

    def _record_alarm(self, machine_id):
        """Log alarm occurrence with timestamp"""
        now = datetime.now()
        self.alarm_history[machine_id].append(now)
        
        # Remove old alarms (outside monitoring window)
        window = timedelta(seconds=self.alert_thresholds["CRITICAL"]["window"])
        self.alarm_history[machine_id] = [
            t for t in self.alarm_history[machine_id] 
            if now - t <= window
        ]

    def _check_alarm_condition(self, machine_id):
        """Check if alarm count exceeds thresholds"""
        alarm_count = len(self.alarm_history[machine_id])
        threshold = self.alert_thresholds["CRITICAL"]["count"]
        
        if alarm_count >= threshold:
            if not self.cooldowns[machine_id]:
                self._send_alert(machine_id)
                self.cooldowns[machine_id] = True
                
                # Start a timer thread to reset cooldown after 2 seconds
                threading.Timer(2, self._reset_cooldown, args=[machine_id]).start()
            else:
                print(f"Cooldown active, skipping alert for {machine_id}")
                
    def _reset_cooldown(self, machine_id):
        print(f"Cooldown ended for {machine_id}, ready for new alerts")
        self.alarm_history[machine_id].clear()
        self.cooldowns[machine_id] = False

    def _send_alert(self, machine_id):
        """Send critical alert via UDP to Data Manager Agent"""
        alert = {
            "machine_id": machine_id,
            "level": "CRITICAL",
            "reason": "high number of control alarms",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(json.dumps(alert).encode(), (self.udp_ip, self.udp_port))
            print(f"Sent CRITICAL alert for {machine_id}")
        except Exception as e:
            print(f"Failed to send alert: {e}")

    def run(self):
        """Start the alert manager"""
        self.mqtt_client.connect(MQTT_BROKER_IP, MQTT_PORT)
        self.mqtt_client.loop_forever()
        print(f"Alert Manager started. Monitoring for critical conditions...")

if __name__ == "__main__":

    # ===== CONFIGURATION =====
    MQTT_BROKER_IP = "10.6.1.9"
    MQTT_PORT = 1883
    GROUP_ID = "19"

    # ==== UDP COMMUNICATIONS CONFIG ====
    UDP_PORT = 5005
    UDP_IP = "localhost"
    
    manager = AlertManager(GROUP_ID, UDP_IP, UDP_PORT)
    manager.run()