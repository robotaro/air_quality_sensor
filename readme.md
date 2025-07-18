# Mosquitto MQTT Broker Setup Guide

This guide covers the installation and configuration of Mosquitto MQTT broker for the Air Quality Monitor project on both Windows and Linux platforms.

## Table of Contents
- [Windows Installation](#windows-installation)
- [Linux Installation](#linux-installation)
- [Configuration for Network Access](#configuration-for-network-access)
- [Testing the Installation](#testing-the-installation)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

---

## Windows Installation

### Method 1: Install as Windows Service (Recommended)

1. **Download Mosquitto**
   - Visit: https://mosquitto.org/download/
   - Download: `mosquitto-2.0.18-install-windows-x64.exe` (or latest version)
   - Choose the 64-bit Windows installer

2. **Install Mosquitto**
   - Run the installer as Administrator (right-click → Run as administrator)
   - During installation:
     - ✅ Check "Service" to install as Windows service
     - ✅ Use default installation path: `C:\Program Files\mosquitto`
   - Complete the installation

3. **Start Mosquitto Service**
   
   Open Command Prompt as Administrator:
   ```cmd
   net start mosquitto
   ```

   To verify it's running:
   ```cmd
   sc query mosquitto
   ```

   You should see `STATE: 4 RUNNING`

### Method 2: Manual Installation (Portable)

1. **Download Mosquitto**
   - Download the Windows binary (ZIP file, not installer)
   - Extract to a folder like `C:\mosquitto`

2. **Run Mosquitto Manually**
   ```cmd
   cd C:\mosquitto
   mosquitto.exe -v
   ```

   Keep this Command Prompt window open while using the broker.

---

## Linux Installation

### Ubuntu/Debian

1. **Update package list**
   ```bash
   sudo apt update
   ```

2. **Install Mosquitto and client tools**
   ```bash
   sudo apt install mosquitto mosquitto-clients
   ```

3. **Start and enable Mosquitto service**
   ```bash
   sudo systemctl start mosquitto
   sudo systemctl enable mosquitto
   ```

4. **Verify installation**
   ```bash
   sudo systemctl status mosquitto
   ```

### CentOS/RHEL/Fedora

1. **Install from EPEL repository**
   ```bash
   sudo yum install epel-release
   sudo yum install mosquitto
   ```

2. **Start and enable service**
   ```bash
   sudo systemctl start mosquitto
   sudo systemctl enable mosquitto
   ```

### macOS (using Homebrew)

1. **Install Mosquitto**
   ```bash
   brew install mosquitto
   ```

2. **Start Mosquitto**
   ```bash
   brew services start mosquitto
   ```

---

## Configuration for Network Access

By default, Mosquitto only listens on localhost. To accept connections from ESP32 devices on your network, you need to configure it.

### Create Configuration File

#### Windows
Create `mosquitto.conf` in `C:\Program Files\mosquitto\`:

#### Linux
Create/edit `/etc/mosquitto/mosquitto.conf`:

```conf
# Mosquitto Configuration for Air Quality Monitor

# Listen on all network interfaces
listener 1883 0.0.0.0

# Allow anonymous connections (for testing)
# For production, set to false and configure authentication
allow_anonymous true

# Logging
log_type all
log_dest stdout

# Persistence (optional)
persistence true
persistence_location /var/lib/mosquitto/

# For Windows, use:
# persistence_location C:\ProgramData\mosquitto\
```

### Apply Configuration

#### Windows

**If running as service:**
```cmd
net stop mosquitto
net start mosquitto
```

**If running manually:**
```cmd
cd "C:\Program Files\mosquitto"
mosquitto.exe -c mosquitto.conf -v
```

#### Linux

```bash
sudo systemctl restart mosquitto
```

To check logs:
```bash
sudo journalctl -u mosquitto -f
```

---

## Testing the Installation

### 1. Check if Mosquitto is Listening

#### Windows
```cmd
netstat -an | findstr :1883
```

#### Linux
```bash
sudo netstat -tlnp | grep 1883
# or
sudo ss -tlnp | grep 1883
```

You should see:
```
0.0.0.0:1883    LISTENING
```

### 2. Test with Mosquitto Client Tools

#### Subscribe to a test topic:
```bash
mosquitto_sub -h localhost -t test/topic -v
```

#### In another terminal, publish a message:
```bash
mosquitto_pub -h localhost -t test/topic -m "Hello MQTT"
```

### 3. Find Your Network IP Address

#### Windows
```cmd
ipconfig
```
Look for IPv4 Address under your active network adapter.

#### Linux
```bash
ip addr show
# or
ifconfig
```

Common LAN IP ranges:
- 192.168.x.x
- 10.x.x.x
- 172.16.x.x to 172.31.x.x

### 4. Test Network Access

From another device on the same network:
```bash
mosquitto_pub -h YOUR_PC_IP -t test/topic -m "Network test"
```

---

## Troubleshooting

### Windows Issues

#### "Access Denied" Error
- Must run Command Prompt as Administrator
- Right-click Command Prompt → Run as administrator

#### "The service name is invalid"
- Mosquitto not installed as service
- Use manual installation method

#### Windows Firewall Blocking
1. Open Windows Security
2. Go to Firewall & network protection
3. Click "Allow an app through firewall"
4. Click "Change settings" then "Allow another app"
5. Browse to `C:\Program Files\mosquitto\mosquitto.exe`
6. Check both Private and Public networks

#### Port 1883 Already in Use
```cmd
netstat -ano | findstr :1883
tasklist /FI "PID eq [PID_NUMBER]"
```

### Linux Issues

#### Permission Denied
```bash
sudo systemctl start mosquitto
```

#### Port Already in Use
```bash
sudo lsof -i :1883
# or
sudo netstat -tlnp | grep 1883
```

#### Check Mosquitto Logs
```bash
sudo journalctl -u mosquitto -n 50
# or
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### Common Network Issues

#### ESP32 Can't Connect
1. Verify both devices are on the same network
2. Check if Mosquitto is listening on 0.0.0.0 (not just 127.0.0.1)
3. Disable firewall temporarily to test
4. Try ping from ESP32 network to PC

#### Connection Refused
- Mosquitto not running
- Firewall blocking port 1883
- Wrong IP address in ESP32 code

---

## Security Considerations

### For Production Use

1. **Disable Anonymous Access**
   ```conf
   allow_anonymous false
   ```

2. **Set up Username/Password**
   ```bash
   mosquitto_passwd -c /etc/mosquitto/passwd username
   ```

3. **Update Configuration**
   ```conf
   password_file /etc/mosquitto/passwd
   ```

4. **Use TLS/SSL**
   ```conf
   listener 8883
   certfile /path/to/cert.pem
   keyfile /path/to/key.pem
   ```

5. **Restrict Network Access**
   ```conf
   listener 1883 192.168.1.0/24
   ```

### Basic Security Checklist
- [ ] Change default ports if exposed to internet
- [ ] Enable authentication
- [ ] Use strong passwords
- [ ] Enable TLS for production
- [ ] Regularly update Mosquitto
- [ ] Monitor logs for suspicious activity

---

## Quick Reference

### Start/Stop Commands

#### Windows (Service)
```cmd
net start mosquitto
net stop mosquitto
net restart mosquitto
```

#### Linux (systemd)
```bash
sudo systemctl start mosquitto
sudo systemctl stop mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

### Test Commands
```bash
# Subscribe to all topics
mosquitto_sub -h localhost -t '#' -v

# Subscribe to air quality data
mosquitto_sub -h localhost -t 'airquality/sensor/data' -v

# Publish test message
mosquitto_pub -h localhost -t 'test/topic' -m 'Test message'
```

### Default Locations

#### Windows
- Installation: `C:\Program Files\mosquitto\`
- Config: `C:\Program Files\mosquitto\mosquitto.conf`
- Data: `C:\ProgramData\mosquitto\`

#### Linux
- Installation: `/usr/sbin/mosquitto`
- Config: `/etc/mosquitto/mosquitto.conf`
- Data: `/var/lib/mosquitto/`
- Logs: `/var/log/mosquitto/`

---

## Next Steps

1. Configure Mosquitto for network access using the configuration above
2. Update ESP32 code with your PC's IP address:
   ```cpp
   const char* MQTT_SERVER = "YOUR_PC_IP";
   ```
3. Run the Python collector and visualizer scripts
4. Monitor data flow using `mosquitto_sub`

For project-specific setup, refer to the main Air Quality Monitor documentation.