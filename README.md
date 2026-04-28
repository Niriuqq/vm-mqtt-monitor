# vm-mqtt-monitor

Cross-platform system metrics publisher for **Home Assistant** via MQTT.  
Läuft auf **Windows Server**, **Debian**, **Ubuntu** und anderen Linux-Distributionen — auch auf VMware ESXi gehostete VMs.

Inspiriert von [rpi-mqtt-monitor](https://github.com/hjelev/rpi-mqtt-monitor), neu gebaut für alle Plattformen.

## Was wird überwacht?

| Metrik | Beschreibung |
|---|---|
| CPU Load | CPU-Auslastung in % |
| CPU Temperatur | Durchschnittliche Kerntemperatur in °C (wo verfügbar) |
| Memory Usage | RAM-Auslastung in % |
| Swap / Page File | Swap- oder Windows-Auslagerungsdatei in % |
| Disk Usage | Festplattenauslastung in % (pro konfiguriertem Pfad/Laufwerk) |

> **Hinweis zu CPU-Temperatur auf VMs:** VMware ESXi gibt Temperatursensoren nicht an Gast-VMs weiter. Die Temperatur-Metrik wird in diesem Fall einfach weggelassen — alle anderen Metriken funktionieren normal.

---

## Wie funktioniert die Home Assistant Integration?

Der Monitor nutzt **MQTT Discovery**: Sobald er läuft, erscheinen alle Sensoren **automatisch** in Home Assistant unter einem Gerät mit dem Hostnamen des Servers. Es muss nichts manuell in HA konfiguriert werden.

---

## Voraussetzungen

- Python 3.9 oder neuer
- Ein laufender **MQTT Broker** (z.B. Mosquitto als HA Add-on)
- Home Assistant mit aktivierter **MQTT Integration**

---

## Teil 1: Home Assistant vorbereiten

### 1.1 Mosquitto MQTT Broker installieren

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store**
2. Suche nach **Mosquitto broker** und installieren
3. Nach der Installation: Add-on starten und **"Start on boot"** aktivieren

### 1.2 MQTT-Benutzer erstellen

1. **Einstellungen → Personen → Benutzer** (oben rechts auf "Benutzer" wechseln)
2. Klick auf **"Benutzer hinzufügen"**
3. Name: z.B. `mqtt_monitor`, Benutzername: `mqtt_monitor`, Passwort vergeben
4. Diese Zugangsdaten später in der `config.yaml` eintragen

### 1.3 MQTT Integration aktivieren

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Suche nach **MQTT** und hinzufügen
3. Broker: `localhost` (oder IP des HA-Servers), Port: `1883`
4. Benutzername und Passwort vom gerade erstellten Benutzer eingeben
5. Speichern

Nach diesen Schritten ist HA bereit. Die Sensoren erscheinen automatisch sobald der Monitor das erste Mal läuft.

---

## Teil 2: Installation auf Ubuntu / Debian

Diese Anleitung gilt für Ubuntu Server und Debian. Alle Befehle als normaler Benutzer mit `sudo`-Rechten ausführen.

### 2.1 Repo klonen

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv
```

```bash
cd /opt
sudo git clone https://github.com/Niriuqq/vm-mqtt-monitor.git
sudo chown -R $USER:$USER /opt/vm-mqtt-monitor
cd /opt/vm-mqtt-monitor
```

### 2.2 Python-Abhängigkeiten installieren

**Empfohlen — über apt (funktioniert auch hinter Firewalls/Proxies):**

```bash
sudo apt install -y python3-psutil python3-paho-mqtt python3-yaml
```

Danach venv mit System-Paketen erstellen:

```bash
python3 -m venv venv --system-site-packages
source venv/bin/activate
```

**Alternativ — über pip (nur ohne Proxy/Firewall-Einschränkungen):**

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **SSL-Proxy / Firmen-Firewall Fehler bei pip?** Falls du `CertificateError`, `SSLError` oder `404`-Fehler bekommst, verwende die apt-Methode oben. Sollte `python3-paho-mqtt` in deiner apt-Version nicht verfügbar sein, pip mit diesen Flags verwenden:
> ```bash
> pip install paho-mqtt --trusted-host pypi.org --trusted-host files.pythonhosted.org
> ```

### 2.3 Konfiguration erstellen

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Mindestens diese Werte anpassen:

```yaml
mqtt_host: "192.168.1.10"      # IP-Adresse deines Home Assistant / MQTT-Brokers
mqtt_port: 1883
mqtt_user: "mqtt_monitor"      # MQTT-Benutzer aus Schritt 1.2
mqtt_password: "dein_passwort"

interval: 60                   # Abfrageintervall in Sekunden

disk_paths:
  - "/"                        # Root-Partition
  # - "/home"                  # Weitere Partitionen nach Bedarf
```

Speichern mit `Ctrl+O`, beenden mit `Ctrl+X`.

### 2.4 Test-Lauf (einmalig ausführen)

```bash
source venv/bin/activate
python3 vm_mqtt_monitor.py --once
```

Erwartete Ausgabe:
```
2024-01-15 10:23:01 [INFO] Collecting metrics...
2024-01-15 10:23:02 [INFO]   cpu_load: 4.2
2024-01-15 10:23:02 [INFO]   memory_usage: 31.7
2024-01-15 10:23:02 [INFO]   swap_usage: 0.0
2024-01-15 10:23:02 [INFO]   disk_root: 18.4
2024-01-15 10:23:02 [INFO] Published 4 metrics.
```

Jetzt in Home Assistant unter **Einstellungen → Geräte & Dienste → MQTT** nachschauen — das Gerät sollte bereits erschienen sein.

### 2.5 Als systemd-Service einrichten (Dauerstart)

```bash
sudo bash install/install_linux.sh
```

Der Installer kopiert die Dateien nach `/opt/vm-mqtt-monitor` und richtet den Service ein.

Danach:

```bash
sudo systemctl start vm-mqtt-monitor
sudo systemctl status vm-mqtt-monitor
```

Logs ansehen:

```bash
journalctl -u vm-mqtt-monitor -f
```

#### Service-Befehle im Überblick

| Befehl | Aktion |
|---|---|
| `sudo systemctl start vm-mqtt-monitor` | Service starten |
| `sudo systemctl stop vm-mqtt-monitor` | Service stoppen |
| `sudo systemctl restart vm-mqtt-monitor` | Service neu starten |
| `sudo systemctl status vm-mqtt-monitor` | Status anzeigen |
| `sudo systemctl enable vm-mqtt-monitor` | Autostart aktivieren |
| `sudo systemctl disable vm-mqtt-monitor` | Autostart deaktivieren |
| `journalctl -u vm-mqtt-monitor -f` | Logs live verfolgen |

---

## Teil 3: Installation auf Windows Server

### 3.1 Python installieren

Falls Python noch nicht installiert ist:

1. Python von [python.org/downloads](https://www.python.org/downloads/) herunterladen (Version 3.9 oder neuer)
2. Installer starten und **"Add Python to PATH"** anhaken
3. Installation abschließen
4. Prüfen: PowerShell öffnen → `python --version`

### 3.2 Repo herunterladen

PowerShell als **Administrator** öffnen:

```powershell
cd C:\
git clone https://github.com/Niriuqq/vm-mqtt-monitor.git
cd C:\vm-mqtt-monitor
```

Falls Git nicht installiert ist, alternativ als ZIP herunterladen:
- GitHub-Seite aufrufen → **Code → Download ZIP**
- ZIP nach `C:\vm-mqtt-monitor` entpacken

### 3.3 Konfiguration erstellen

```powershell
Copy-Item config.example.yaml config.yaml
notepad config.yaml
```

Mindestens diese Werte anpassen:

```yaml
mqtt_host: "192.168.1.10"      # IP-Adresse deines Home Assistant / MQTT-Brokers
mqtt_port: 1883
mqtt_user: "mqtt_monitor"      # MQTT-Benutzer aus Schritt 1.2
mqtt_password: "dein_passwort"

interval: 60                   # Abfrageintervall in Sekunden

disk_paths:
  - "C:\\"                     # C-Laufwerk
  # - "D:\\"                   # Weitere Laufwerke nach Bedarf
```

Speichern und Notepad schließen.

### 3.4 Abhängigkeiten installieren

Pakete direkt ins System-Python installieren (kein venv nötig auf Windows):

```powershell
python -m pip install -r requirements.txt
```

> **DNS- oder SSL-Fehler bei pip?** Falls du `getaddrinfo failed`, `CertificateError` oder `SSLError` bekommst:
> ```powershell
> python -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
> ```
> **Wichtig:** Immer `python -m pip` verwenden, nie `pip install` oder `.\venv\Scripts\pip` — auf Windows Server kann das zu Konflikten führen.

### 3.5 Test-Lauf (einmalig ausführen)

```powershell
python vm_mqtt_monitor.py --config config.yaml --once
```

Erwartete Ausgabe:
```
2024-01-15 10:23:01 [INFO] Collecting metrics...
2024-01-15 10:23:02 [INFO]   cpu_load: 12.5
2024-01-15 10:23:02 [INFO]   memory_usage: 45.3
2024-01-15 10:23:02 [INFO]   swap_usage: 2.1
2024-01-15 10:23:02 [INFO]   disk_C_drive: 34.7
2024-01-15 10:23:02 [INFO] Published 4 metrics.
```

### 3.6 Als geplanten Task einrichten (Dauerstart)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install\install_windows.ps1 -InstallDir "C:\vm-mqtt-monitor"
```

Der Installer richtet einen **Windows Task Scheduler**-Eintrag ein, der jede Minute ausgeführt wird und beim Systemstart automatisch aktiv ist.

Task starten:

```powershell
Start-ScheduledTask -TaskName "vm-mqtt-monitor"
```

#### Task-Befehle im Überblick

| Befehl | Aktion |
|---|---|
| `Start-ScheduledTask -TaskName "vm-mqtt-monitor"` | Task starten |
| `Stop-ScheduledTask -TaskName "vm-mqtt-monitor"` | Task stoppen |
| `Get-ScheduledTask -TaskName "vm-mqtt-monitor"` | Status anzeigen |
| `Unregister-ScheduledTask -TaskName "vm-mqtt-monitor"` | Task entfernen |

Logs: **Ereignisanzeige → Windows-Protokolle → System** oder Task Scheduler → History.

---

## Teil 4: Home Assistant — Sensoren prüfen

Nachdem der Monitor mindestens einmal gelaufen ist:

1. **Einstellungen → Geräte & Dienste → MQTT**
2. Dort erscheint unter **"Geräte"** ein Eintrag mit dem Hostnamen des Servers
3. Klick darauf → alle Metriken als Sensoren sichtbar

### Sensoren im Dashboard anzeigen

1. Dashboard öffnen → **Bearbeiten → Karte hinzufügen**
2. **"Entitäten"**-Karte wählen
3. Sensoren des Geräts hinzufügen (z.B. `sensor.meinserver_cpu_load`)

Für eine übersichtliche Ansicht empfiehlt sich die **Gauge**-Karte oder **History Graph**-Karte.

### Automatisierungen / Alerts

Beispiel: Benachrichtigung wenn CPU-Last über 90% steigt:

1. **Einstellungen → Automatisierungen → Neu erstellen**
2. Auslöser: **Zustand** → Entität: `sensor.meinserver_cpu_load` → Über: `90`
3. Aktion: **Benachrichtigung senden**

---

## Konfigurationsreferenz

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `mqtt_host` | — | IP oder Hostname des MQTT-Brokers (Pflichtfeld) |
| `mqtt_port` | `1883` | MQTT-Port |
| `mqtt_user` | — | MQTT-Benutzername |
| `mqtt_password` | — | MQTT-Passwort |
| `mqtt_tls` | `false` | TLS/SSL aktivieren |
| `mqtt_keepalive` | `60` | Keepalive-Intervall in Sekunden |
| `discovery_prefix` | `homeassistant` | HA MQTT Discovery Prefix |
| `base_topic` | `vmmonitor` | Basis-Topic für State-Nachrichten |
| `hostname_override` | automatisch | Hostnamen manuell überschreiben |
| `interval` | `60` | Abfrageintervall in Sekunden |
| `monitor_swap` | `true` | Swap / Auslagerungsdatei überwachen |
| `disk_paths` | `["/"]` | Liste der zu überwachenden Pfade/Laufwerke |

---

## MQTT Topics (zur Info)

| Topic | Inhalt |
|---|---|
| `vmmonitor/{hostname}/status` | `online` / `offline` |
| `vmmonitor/{hostname}/cpu_load` | CPU-Last in % |
| `vmmonitor/{hostname}/cpu_temp` | CPU-Temperatur in °C |
| `vmmonitor/{hostname}/memory_usage` | RAM-Auslastung in % |
| `vmmonitor/{hostname}/swap_usage` | Swap/Auslagerung in % |
| `vmmonitor/{hostname}/disk_root` | Root-Partition in % (Linux) |
| `vmmonitor/{hostname}/disk_C_drive` | C:-Laufwerk in % (Windows) |
