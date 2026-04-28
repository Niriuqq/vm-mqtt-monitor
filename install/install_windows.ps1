# vm-mqtt-monitor installer for Windows Server
# Run in PowerShell as Administrator:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install\install_windows.ps1

param(
    [string]$InstallDir = "C:\vm-mqtt-monitor",
    [string]$TaskName = "vm-mqtt-monitor",
    [int]$IntervalMinutes = 1
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSScriptRoot

Write-Host "=== vm-mqtt-monitor Windows Installer ===" -ForegroundColor Cyan

# Check admin
$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Please run PowerShell as Administrator."
    exit 1
}

# Check Python
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "Found: $pythonVersion"
} catch {
    Write-Error "Python not found. Install Python 3.9+ from https://python.org and ensure it is in PATH."
    exit 1
}

# Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

# Copy files (skip if already running from install dir)
$sourceResolved = (Resolve-Path $ScriptDir).Path
$destResolved = (Resolve-Path $InstallDir).Path
if ($sourceResolved -ne $destResolved) {
    Write-Host "Copying files to $InstallDir..."
    Copy-Item "$ScriptDir\vm_mqtt_monitor.py" "$InstallDir\" -Force
    Copy-Item "$ScriptDir\requirements.txt" "$InstallDir\" -Force
} else {
    Write-Host "Already running from $InstallDir, skipping file copy."
}

# Copy or create config
$configDest = "$InstallDir\config.yaml"
if (-not (Test-Path $configDest)) {
    if (Test-Path "$ScriptDir\config.yaml") {
        Copy-Item "$ScriptDir\config.yaml" $configDest -Force
    } else {
        Copy-Item "$ScriptDir\config.example.yaml" $configDest -Force
        Write-Host ""
        Write-Host "  !! config.yaml created from example - edit it before starting:" -ForegroundColor Yellow
        Write-Host "     notepad $configDest" -ForegroundColor Yellow
        Write-Host ""
    }
}

# Install dependencies into system Python
Write-Host "Installing Python dependencies..."
& python -m pip install -r "$InstallDir\requirements.txt" --trusted-host pypi.org --trusted-host files.pythonhosted.org -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed. Ensure Python has internet access or install psutil, paho-mqtt and PyYAML manually."
    exit 1
}

# Get system Python executable path
$pythonExe = (Get-Command python).Source

# Create wrapper script that Task Scheduler will call
$wrapperScript = "$InstallDir\run_monitor.ps1"
$wrapperContent = @'
Set-Location 'INSTALL_DIR'
& 'PYTHON_EXE' 'INSTALL_DIR\vm_mqtt_monitor.py' --config 'CONFIG_DEST' --once
'@
$wrapperContent = $wrapperContent.Replace('INSTALL_DIR', $InstallDir).Replace('PYTHON_EXE', $pythonExe).Replace('CONFIG_DEST', $configDest)
$wrapperContent | Out-File -FilePath $wrapperScript -Encoding utf8

# Register Scheduled Task (runs every N minutes)
Write-Host "Registering Scheduled Task '$TaskName' (every $IntervalMinutes min)..."
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -Once -At (Get-Date)
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$wrapperScript`""
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal | Out-Null

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit the config:  notepad $configDest"
Write-Host "  2. Start the task:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  3. Check status:     Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "  4. Run manually:     python '$InstallDir\vm_mqtt_monitor.py' --config '$configDest' --once"
Write-Host ""
