#!/bin/bash
# vm-mqtt-monitor installer for Linux (Debian, Ubuntu, and compatible distros)
# Run as root: sudo bash install/install_linux.sh

set -e

INSTALL_DIR="/opt/vm-mqtt-monitor"
SERVICE_NAME="vm-mqtt-monitor"
VENV_DIR="${INSTALL_DIR}/venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== vm-mqtt-monitor Linux Installer ==="

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash install/install_linux.sh)"
    exit 1
fi

# Install Python and dependencies via apt (avoids pip/proxy issues)
echo "Installing dependencies via apt..."
apt-get update -q
apt-get install -y python3 python3-pip python3-venv python3-psutil python3-yaml

# paho-mqtt: try apt first, fall back to pip
if apt-get install -y python3-paho-mqtt 2>/dev/null; then
    echo "paho-mqtt installed via apt."
    USE_SYSTEM_PKGS="--system-site-packages"
else
    echo "paho-mqtt not available via apt, will use pip..."
    USE_SYSTEM_PKGS=""
fi

# Create install directory
mkdir -p "${INSTALL_DIR}"

# Copy files only if source and destination differ
if [ "$(realpath "${SCRIPT_DIR}")" != "$(realpath "${INSTALL_DIR}")" ]; then
    echo "Copying files to ${INSTALL_DIR}..."
    cp "${SCRIPT_DIR}/vm_mqtt_monitor.py" "${INSTALL_DIR}/"
    cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"

    if [ ! -f "${INSTALL_DIR}/config.yaml" ]; then
        if [ -f "${SCRIPT_DIR}/config.yaml" ]; then
            cp "${SCRIPT_DIR}/config.yaml" "${INSTALL_DIR}/"
        else
            cp "${SCRIPT_DIR}/config.example.yaml" "${INSTALL_DIR}/config.yaml"
        fi
    fi
else
    echo "Already running from ${INSTALL_DIR}, skipping file copy."
    # Create config from example if missing
    if [ ! -f "${INSTALL_DIR}/config.yaml" ]; then
        cp "${INSTALL_DIR}/config.example.yaml" "${INSTALL_DIR}/config.yaml"
    fi
fi

if [ ! -f "${INSTALL_DIR}/config.yaml" ]; then
    echo ""
    echo "  !! config.yaml created from example — edit it before starting the service:"
    echo "     nano ${INSTALL_DIR}/config.yaml"
    echo ""
fi

# Create virtualenv (with system packages if apt provided them)
echo "Setting up Python virtual environment..."
python3 -m venv "${VENV_DIR}" ${USE_SYSTEM_PKGS}

# Only use pip if apt didn't cover all packages
if [ -z "${USE_SYSTEM_PKGS}" ]; then
    PIP_TRUSTED="--trusted-host pypi.org --trusted-host files.pythonhosted.org"
    "${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" -q $PIP_TRUSTED
fi

# Install systemd service
echo "Installing systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=VM MQTT Monitor — system metrics for Home Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${VENV_DIR}/bin/python3 ${INSTALL_DIR}/vm_mqtt_monitor.py --config ${INSTALL_DIR}/config.yaml
WorkingDirectory=${INSTALL_DIR}
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit the config:   nano ${INSTALL_DIR}/config.yaml"
echo "  2. Start the service: systemctl start ${SERVICE_NAME}"
echo "  3. Check status:      systemctl status ${SERVICE_NAME}"
echo "  4. View logs:         journalctl -u ${SERVICE_NAME} -f"
echo ""
