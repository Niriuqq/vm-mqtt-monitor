# vm-mqtt-monitor

Cross-platform system metrics publisher for **Home Assistant** via MQTT.  
Works on **Windows Server**, **Debian**, **Ubuntu** and any other Linux distribution — all hosted on VMware ESXi or bare metal.

Inspired by [rpi-mqtt-monitor](https://github.com/hjelev/rpi-mqtt-monitor), redesigned to run everywhere.

## Metrics

| Metric | Description | Platform |
|---|---|---|
| CPU Load | CPU utilization in % | All |
| CPU Temperature | Average CPU core temperature in °C | Linux (where sensors are available), Windows (requires WMI) |
| Memory Usage | RAM usage in % | All |
| Swap / Page File | Swap or Windows page file usage in % | All |
| Disk Usage | Usage % per configured disk path/drive | All |

## Home Assistant Integration

vm-mqtt-monitor uses **MQTT Discovery** — entities appear automatically in Home Assistant under a device named after the hostname. No manual sensor configuration needed.

Each host shows up as its own device in HA, with all metrics as sensor entities.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
nano config.yaml   # or notepad config.yaml on Windows
```

Minimum required settings:

```yaml
mqtt_host: "192.168.1.10"     # Your MQTT broker / Home Assistant IP
mqtt_user: "mqtt_user"
mqtt_password: "mqtt_password"
```

### 3. Run

```bash
python3 vm_mqtt_monitor.py
```

Or one-shot (publish once and exit):

```bash
python3 vm_mqtt_monitor.py --once
```

---

## Installation as a Service

### Linux (Debian / Ubuntu)

```bash
sudo bash install/install_linux.sh
sudo nano /opt/vm-mqtt-monitor/config.yaml
sudo systemctl start vm-mqtt-monitor
sudo journalctl -u vm-mqtt-monitor -f
```

### Windows Server

Run in **Administrator PowerShell**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install\install_windows.ps1
notepad C:\vm-mqtt-monitor\config.yaml
Start-ScheduledTask -TaskName "vm-mqtt-monitor"
```

The Windows installer registers a **Scheduled Task** running every minute as SYSTEM.

---

## Configuration Reference

| Key | Default | Description |
|---|---|---|
| `mqtt_host` | — | MQTT broker hostname or IP (required) |
| `mqtt_port` | `1883` | MQTT broker port |
| `mqtt_user` | — | MQTT username |
| `mqtt_password` | — | MQTT password |
| `mqtt_tls` | `false` | Enable TLS/SSL |
| `mqtt_keepalive` | `60` | Keepalive interval in seconds |
| `discovery_prefix` | `homeassistant` | HA MQTT discovery prefix |
| `base_topic` | `vmmonitor` | Base topic for state messages |
| `hostname_override` | auto | Override the auto-detected hostname |
| `interval` | `60` | Polling interval in seconds |
| `monitor_swap` | `true` | Monitor swap / page file |
| `disk_paths` | `["/"]` | List of disk paths to monitor |

### Disk paths examples

**Linux:**
```yaml
disk_paths:
  - "/"
  - "/home"
  - "/data"
```

**Windows:**
```yaml
disk_paths:
  - "C:\\"
  - "D:\\"
```

---

## MQTT Topics

| Topic | Content |
|---|---|
| `vmmonitor/{hostname}/status` | `online` / `offline` |
| `vmmonitor/{hostname}/cpu_load` | CPU load % |
| `vmmonitor/{hostname}/cpu_temp` | CPU temperature °C |
| `vmmonitor/{hostname}/memory_usage` | Memory usage % |
| `vmmonitor/{hostname}/swap_usage` | Swap/page file usage % |
| `vmmonitor/{hostname}/disk_root` | Root disk usage % (Linux) |
| `vmmonitor/{hostname}/disk_C_drive` | C: drive usage % (Windows) |

HA Discovery config topics follow the pattern:
`homeassistant/sensor/{device_id}/{metric}/config`

---

## CPU Temperature Notes

- **Linux**: Works out of the box on most systems via `psutil.sensors_temperatures()`. Requires kernel sensors to be enabled (standard on most modern distros).
- **Windows**: Requires the optional `wmi` package (`pip install wmi`) and may need WMI access rights. If unavailable, the temperature metric is simply omitted — all other metrics still work.
- **VMware VMs**: CPU temperature sensors are typically not exposed to guest VMs. This is a hypervisor limitation — the metric will be absent on ESXi-hosted VMs.

## Requirements

- Python 3.9+
- `psutil` >= 5.9
- `paho-mqtt` >= 2.0
- `PyYAML` >= 6.0
- Optional: `wmi` (Windows CPU temperature only)
