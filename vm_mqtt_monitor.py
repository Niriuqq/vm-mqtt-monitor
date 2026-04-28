#!/usr/bin/env python3
"""
vm-mqtt-monitor: Cross-platform system metrics publisher for Home Assistant via MQTT.
Supports Windows Server, Debian, Ubuntu and other Linux distributions.
"""

import json
import logging
import platform
import socket
import sys
import time
from datetime import timedelta
from pathlib import Path

try:
    import psutil
except ImportError:
    sys.exit("psutil not installed. Run: pip install -r requirements.txt")

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("paho-mqtt not installed. Run: pip install -r requirements.txt")

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed. Run: pip install -r requirements.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        example = Path("config.example.yaml")
        if example.exists():
            sys.exit(f"config.yaml not found. Copy config.example.yaml to config.yaml and edit it.")
        sys.exit(f"config.yaml not found at {config_path.resolve()}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_hostname() -> str:
    return socket.gethostname().split(".")[0]


def get_cpu_load() -> float:
    return psutil.cpu_percent(interval=1)


def get_cpu_temp() -> float | None:
    try:
        if platform.system() == "Windows":
            # Try WMI on Windows (requires optional wmi package)
            try:
                import wmi
                w = wmi.WMI(namespace=r"root\wmi")
                sensors = w.MSAcpi_ThermalZoneTemperature()
                if sensors:
                    temp_kelvin = sensors[0].CurrentTemperature / 10.0
                    return round(temp_kelvin - 273.15, 1)
            except Exception:
                return None
        else:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            # Prefer coretemp, then k10temp, then cpu_thermal, then first available
            for key in ("coretemp", "k10temp", "cpu_thermal", "cpu-thermal"):
                if key in temps:
                    readings = [r.current for r in temps[key]]
                    return round(sum(readings) / len(readings), 1)
            # Fallback: first sensor group
            first = next(iter(temps.values()))
            readings = [r.current for r in first]
            return round(sum(readings) / len(readings), 1)
    except Exception as e:
        log.debug(f"CPU temp not available: {e}")
        return None


def get_memory_usage() -> float:
    return psutil.virtual_memory().percent


def get_disk_usage(path: str = "/") -> float:
    if platform.system() == "Windows" and path == "/":
        path = "C:\\"
    try:
        return psutil.disk_usage(path).percent
    except Exception as e:
        log.warning(f"Disk usage for {path} not available: {e}")
        return 0.0


def get_swap_usage() -> float:
    return psutil.swap_memory().percent


def get_network_stats() -> tuple[float, float]:
    """Returns (bytes_sent_MB, bytes_recv_MB) total since boot."""
    counters = psutil.net_io_counters()
    sent_mb = round(counters.bytes_sent / 1024 / 1024, 2)
    recv_mb = round(counters.bytes_recv / 1024 / 1024, 2)
    return sent_mb, recv_mb


def get_uptime() -> str:
    """Returns uptime as a human-readable string, e.g. '2d 4h 13m'."""
    delta = timedelta(seconds=int(time.time() - psutil.boot_time()))
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def collect_metrics(config: dict) -> dict:
    metrics = {}
    disk_paths = config.get("disk_paths", ["/"])
    if platform.system() == "Windows" and disk_paths == ["/"]:
        disk_paths = ["C:\\"]

    metrics["cpu_load"] = get_cpu_load()
    metrics["memory_usage"] = get_memory_usage()

    if config.get("monitor_swap", True):
        metrics["swap_usage"] = get_swap_usage()

    temp = get_cpu_temp()
    if temp is not None:
        metrics["cpu_temp"] = temp

    for path in disk_paths:
        if platform.system() == "Windows":
            label = path.replace(":\\", "").replace(":", "") + "_drive"
        else:
            label = "root" if path == "/" else path.replace("/", "_").strip("_")
        metrics[f"disk_{label}"] = get_disk_usage(path)

    if config.get("monitor_network", True):
        sent_mb, recv_mb = get_network_stats()
        metrics["data_sent"] = sent_mb
        metrics["data_received"] = recv_mb

    if config.get("monitor_uptime", True):
        metrics["uptime"] = get_uptime()

    return metrics


SENSOR_DEFINITIONS = {
    "cpu_load":      {"name": "CPU Load",        "unit": "%",  "icon": "mdi:cpu-64-bit",      "device_class": None},
    "cpu_temp":      {"name": "CPU Temperature", "unit": "°C", "icon": "mdi:thermometer",     "device_class": "temperature"},
    "memory_usage":  {"name": "Memory Usage",    "unit": "%",  "icon": "mdi:memory",          "device_class": None},
    "swap_usage":    {"name": "Swap Usage",      "unit": "%",  "icon": "mdi:swap-horizontal", "device_class": None},
    "data_sent":     {"name": "Data Sent",       "unit": "MB", "icon": "mdi:upload-network",  "device_class": None},
    "data_received": {"name": "Data Received",   "unit": "MB", "icon": "mdi:download-network","device_class": None},
    "uptime":        {"name": "Uptime",          "unit": "",   "icon": "mdi:clock-outline",   "device_class": None},
}


def get_sensor_def(metric_key: str) -> dict:
    if metric_key in SENSOR_DEFINITIONS:
        return SENSOR_DEFINITIONS[metric_key]
    # Disk sensors
    if metric_key.startswith("disk_"):
        label = metric_key[5:].replace("_", " ").title()
        return {
            "name": f"Disk {label} Usage",
            "unit": "%",
            "icon": "mdi:harddisk",
            "device_class": None,
        }
    return {"name": metric_key.replace("_", " ").title(), "unit": "", "icon": "mdi:information", "device_class": None}


class MQTTMonitor:
    def __init__(self, config: dict):
        self.config = config
        self.hostname = config.get("hostname_override") or get_hostname()
        self.device_id = f"vmmonitor_{self.hostname}".lower().replace("-", "_")
        self.base_topic = config.get("base_topic", "vmmonitor").rstrip("/")
        self.discovery_prefix = config.get("discovery_prefix", "homeassistant")
        self.client = mqtt.Client(client_id=self.device_id, protocol=mqtt.MQTTv5)
        self._setup_auth()
        self._setup_tls()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._discovery_sent = set()

    def _setup_auth(self):
        user = self.config.get("mqtt_user")
        password = self.config.get("mqtt_password")
        if user:
            self.client.username_pw_set(user, password)

    def _setup_tls(self):
        if self.config.get("mqtt_tls", False):
            import ssl
            self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            log.info(f"Connected to MQTT broker at {self.config['mqtt_host']}:{self.config.get('mqtt_port', 1883)}")
        else:
            log.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None, reason_code=None):
        if rc != 0:
            log.warning(f"Unexpected MQTT disconnect (rc={rc}), will reconnect...")

    def connect(self):
        host = self.config["mqtt_host"]
        port = self.config.get("mqtt_port", 1883)
        keepalive = self.config.get("mqtt_keepalive", 60)
        self.client.connect(host, port, keepalive)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _device_payload(self) -> dict:
        return {
            "identifiers": [self.device_id],
            "name": self.hostname,
            "model": f"{platform.system()} {platform.release()}",
            "manufacturer": "vm-mqtt-monitor",
            "sw_version": platform.version()[:64],
        }

    def publish_discovery(self, metric_key: str):
        if metric_key in self._discovery_sent:
            return
        sensor = get_sensor_def(metric_key)
        unique_id = f"{self.device_id}_{metric_key}"
        state_topic = f"{self.base_topic}/{self.hostname}/{metric_key}"
        discovery_topic = f"{self.discovery_prefix}/sensor/{self.device_id}/{metric_key}/config"

        payload = {
            "name": sensor["name"],
            "unique_id": unique_id,
            "state_topic": state_topic,
            "unit_of_measurement": sensor["unit"],
            "icon": sensor["icon"],
            "device": self._device_payload(),
            "availability_topic": f"{self.base_topic}/{self.hostname}/status",
            "payload_available": "online",
            "payload_not_available": "offline",
        }
        if sensor.get("device_class"):
            payload["device_class"] = sensor["device_class"]
            payload["state_class"] = "measurement"

        self.client.publish(discovery_topic, json.dumps(payload), retain=True)
        self._discovery_sent.add(metric_key)
        log.debug(f"Discovery published for {metric_key}")

    def publish_metrics(self, metrics: dict):
        status_topic = f"{self.base_topic}/{self.hostname}/status"
        self.client.publish(status_topic, "online", retain=True)

        for key, value in metrics.items():
            self.publish_discovery(key)
            state_topic = f"{self.base_topic}/{self.hostname}/{key}"
            self.client.publish(state_topic, str(value), retain=False)
            log.info(f"  {key}: {value}")

    def run(self):
        interval = self.config.get("interval", 60)
        log.info(f"Starting vm-mqtt-monitor for host '{self.hostname}' (interval: {interval}s)")
        self.connect()
        time.sleep(1)

        try:
            while True:
                log.info(f"Collecting metrics...")
                metrics = collect_metrics(self.config)
                self.publish_metrics(metrics)
                log.info(f"Published {len(metrics)} metrics. Next update in {interval}s.")
                time.sleep(interval)
        except KeyboardInterrupt:
            log.info("Shutting down...")
        finally:
            # Mark device offline
            self.client.publish(
                f"{self.base_topic}/{self.hostname}/status", "offline", retain=True
            )
            time.sleep(0.5)
            self.disconnect()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="vm-mqtt-monitor: Cross-platform system metrics for Home Assistant")
    parser.add_argument("--config", default="config.yaml", help="Path to config file (default: config.yaml)")
    parser.add_argument("--once", action="store_true", help="Publish once and exit (no loop)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config(args.config)
    monitor = MQTTMonitor(config)

    if args.once:
        log.info("Running in one-shot mode...")
        monitor.connect()
        time.sleep(1)
        metrics = collect_metrics(config)
        monitor.publish_metrics(metrics)
        time.sleep(0.5)
        monitor.disconnect()
    else:
        monitor.run()


if __name__ == "__main__":
    main()
