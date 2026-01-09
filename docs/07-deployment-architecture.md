# 07 - Deployment Architecture

> **Document Type:** Deployment Architecture  
> **Status:** Draft  
> **Version:** 1.0  
> **Last Updated:** 2025-01-08  
> **Depends On:** 01-System Context, 02-Security Architecture, 03-Component Architecture  
> **Blocks:** Production Deployment

---

## 1. Executive Summary

This document specifies how to deploy the Anova Control Server in both development and production environments. The production target is a Raspberry Pi Zero 2 W with Cloudflare Tunnel for HTTPS exposure.

**Key Deployment Characteristics:**
- **Zero recurring costs** - Free tier Cloudflare Tunnel, self-hosted hardware
- **Auto-recovery** - systemd ensures restart after power outage or crash
- **Minimal maintenance** - Log rotation, health checks, months of unattended operation
- **Remote administration** - SSH-only, no physical access required

---

## 2. Environment Overview

| Environment | Hardware | Network Exposure | Purpose | Duration |
|-------------|----------|------------------|---------|----------|
| **Development** | macOS/Linux workstation | ngrok (temporary URL) | Build, test, iterate | Phase 1 (days) |
| **Production** | Raspberry Pi Zero 2 W | Cloudflare Tunnel (permanent URL) | 24/7 operation | Phase 2+ (months) |

---

## 3. Development Environment Setup

### 3.1 Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Runtime |
| pip | Latest | Package management |
| ngrok | 3.x | Temporary HTTPS tunnel |
| Git | Any | Version control |

### 3.2 Initial Setup

```bash
# 1. Clone the repository (or create from scratch)
mkdir anova-assistant
cd anova-assistant

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install flask requests python-dotenv gunicorn pytest

# 4. Create environment file
cat > .env << 'EOF'
# Anova Credentials (get from Anova app account)
ANOVA_EMAIL=your-email@example.com
ANOVA_PASSWORD=your-anova-password
DEVICE_ID=your-device-id

# API Key for ChatGPT authentication (generate a secure random key)
API_KEY=sk-anova-$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Development mode
DEBUG=true
EOF

# 5. IMPORTANT: Add to .gitignore
echo ".env" >> .gitignore
echo "credentials.enc" >> .gitignore
echo "*.pyc" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "venv/" >> .gitignore
```

### 3.3 Running the Development Server

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run Flask development server
python -m server.app
# Or with auto-reload:
FLASK_DEBUG=1 flask --app server.app run --host=0.0.0.0 --port=5000
```

### 3.4 Exposing with ngrok

```bash
# In a separate terminal
ngrok http 5000

# ngrok will output something like:
# Forwarding  https://abc123.ngrok.io -> http://localhost:5000
```

**Use the ngrok HTTPS URL** in your Custom GPT Actions configuration during development.

⚠️ **Note:** ngrok URLs change each time you restart. For stable testing, use ngrok's paid tier or proceed to Cloudflare Tunnel setup.

### 3.5 Finding Your Device ID

The `DEVICE_ID` is needed to identify your specific Anova cooker. To find it:

```python
# Run this once to discover your device ID
# (Requires your Anova email/password)

import requests

# Authenticate with Firebase
auth_response = requests.post(
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
    params={"key": "AIzaSyDQiOP2fTR9zvFcag2kSbcmG9zPh6gZhHw"},  # Anova's Firebase key
    json={
        "email": "your-email@example.com",
        "password": "your-password",
        "returnSecureToken": True
    }
)
token = auth_response.json()["idToken"]

# Get devices
devices_response = requests.get(
    "https://api.anovaculinary.com/devices",  # Verify this endpoint
    headers={"Authorization": f"Bearer {token}"}
)
print(devices_response.json())
```

The device ID will be in the response. Update your `.env` file with it.

---

## 4. Production Environment Setup

### 4.1 Hardware Requirements

| Component | Specification | Notes |
|-----------|---------------|-------|
| **Board** | Raspberry Pi Zero 2 W | Quad-core ARM, WiFi built-in |
| **RAM** | 512 MB | Sufficient for Flask |
| **Storage** | 16GB+ MicroSD | Class 10 or faster |
| **Power** | 5V/2.5A USB | Official Pi power supply recommended |
| **Case** | Optional | Protects from dust |

**Total hardware cost:** ~$25-40 USD

### 4.2 Operating System Setup

#### 4.2.1 Flash Raspberry Pi OS

1. Download **Raspberry Pi Imager** from raspberrypi.com
2. Select **Raspberry Pi OS Lite (64-bit)** (no desktop needed)
3. Click gear icon (⚙️) for advanced options:
   - Set hostname: `anova-server`
   - Enable SSH (password or key authentication)
   - Set username/password (or upload SSH public key)
   - Configure WiFi (SSID and password)
   - Set timezone
4. Flash to MicroSD card
5. Insert card into Pi and power on

#### 4.2.2 Initial SSH Connection

```bash
# Find the Pi on your network (may take 1-2 minutes after boot)
# Option 1: If you set hostname to anova-server
ssh pi@anova-server.local

# Option 2: Find IP via router admin page

# Option 3: Scan network
nmap -sn 192.168.1.0/24 | grep -i raspberry
```

#### 4.2.3 Initial System Configuration

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv git

# (Optional) Disable password authentication for SSH
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 4.3 Application Deployment

#### 4.3.1 Create Application Directory

```bash
# Create directory structure
sudo mkdir -p /opt/anova-assistant
sudo chown pi:pi /opt/anova-assistant
cd /opt/anova-assistant

# Clone or copy your code
# Option 1: Git clone (if using a private repo)
git clone https://github.com/yourusername/anova-assistant.git .

# Option 2: SCP from development machine
# (Run this from your dev machine)
scp -r ./server pi@anova-server.local:/opt/anova-assistant/
scp requirements.txt pi@anova-server.local:/opt/anova-assistant/
```

#### 4.3.2 Set Up Python Environment

```bash
cd /opt/anova-assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask requests python-dotenv gunicorn cryptography
```

#### 4.3.3 Create Production Configuration

```bash
# Create config directory
mkdir -p /opt/anova-assistant/config

# Create credentials file (will be encrypted later)
cat > /opt/anova-assistant/config/credentials.json << 'EOF'
{
    "anova_email": "your-email@example.com",
    "anova_password": "your-anova-password",
    "device_id": "your-device-id",
    "api_key": "sk-anova-YOUR-GENERATED-KEY-HERE"
}
EOF

# CRITICAL: Restrict permissions
chmod 600 /opt/anova-assistant/config/credentials.json
```

⚠️ **Security Note:** In production, this file should be encrypted. For initial deployment, use the plain JSON file but ensure file permissions are set correctly. Encryption can be added as an enhancement.

### 4.4 Cloudflare Tunnel Setup

#### 4.4.1 Create Cloudflare Tunnel

1. Create a free Cloudflare account at cloudflare.com
2. Go to **Zero Trust** → **Networks** → **Tunnels**
3. Click **Create a tunnel**
4. Name: `anova-assistant`
5. Select **Cloudflared** as the connector

#### 4.4.2 Install cloudflared on Pi

```bash
# Download cloudflared for ARM
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
# For Pi Zero 2 W (32-bit OS), use:
# wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm

# Install
sudo mv cloudflared-linux-arm64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Verify installation
cloudflared --version
```

#### 4.4.3 Configure the Tunnel

```bash
# Login to Cloudflare (opens browser for auth)
cloudflared tunnel login

# Create tunnel (if not done in web UI)
cloudflared tunnel create anova-assistant

# Configure routing
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: YOUR-TUNNEL-ID-HERE
credentials-file: /home/pi/.cloudflared/YOUR-TUNNEL-ID-HERE.json

ingress:
  - hostname: anova-YOUR-SUBDOMAIN.cfargotunnel.com
    service: http://localhost:5000
  - service: http_status:404
EOF
```

#### 4.4.4 Install cloudflared as a Service

```bash
# Install as systemd service
sudo cloudflared service install

# Enable and start
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# Check status
sudo systemctl status cloudflared
```

Your tunnel URL will be something like: `https://anova-abc123.cfargotunnel.com`

### 4.5 Create systemd Service for Flask

```bash
sudo cat > /etc/systemd/system/anova-server.service << 'EOF'
[Unit]
Description=Anova Sous Vide Control Server
After=network.target cloudflared.service
Wants=cloudflared.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/anova-assistant
Environment="PATH=/opt/anova-assistant/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/anova-assistant/venv/bin/gunicorn \
    --bind 127.0.0.1:5000 \
    --workers 2 \
    --timeout 30 \
    --access-logfile /var/log/anova-server/access.log \
    --error-logfile /var/log/anova-server/error.log \
    "server.app:create_app()"
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/log/anova-server
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

### 4.6 Create Log Directory

```bash
# Create log directory
sudo mkdir -p /var/log/anova-server
sudo chown pi:pi /var/log/anova-server
```

### 4.7 Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable anova-server

# Start service
sudo systemctl start anova-server

# Check status
sudo systemctl status anova-server

# View logs
sudo journalctl -u anova-server -f
```

---

## 5. Log Rotation

### 5.1 Configure logrotate

```bash
sudo cat > /etc/logrotate.d/anova-server << 'EOF'
/var/log/anova-server/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 pi pi
    postrotate
        systemctl reload anova-server > /dev/null 2>&1 || true
    endscript
}
EOF
```

This configuration:
- Rotates logs daily
- Keeps 7 days of history
- Compresses old logs
- Prevents logs from exceeding ~50MB total

### 5.2 Verify Log Rotation

```bash
# Force a rotation to test
sudo logrotate -f /etc/logrotate.d/anova-server

# Check results
ls -la /var/log/anova-server/
```

---

## 6. Health Monitoring

### 6.1 External Uptime Monitoring

Use a free uptime monitoring service to detect outages:

**Recommended: UptimeRobot (free tier)**

1. Create account at uptimerobot.com
2. Add new monitor:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Anova Server
   - **URL:** `https://your-tunnel-url/health`
   - **Monitoring Interval:** 5 minutes
3. Configure alerts (email, SMS, etc.)

### 6.2 Local Health Check Script

```bash
cat > /opt/anova-assistant/healthcheck.sh << 'EOF'
#!/bin/bash
# Simple health check script

HEALTH_URL="http://localhost:5000/health"
TIMEOUT=5

response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT $HEALTH_URL)

if [ "$response" = "200" ]; then
    echo "OK: Server is healthy"
    exit 0
else
    echo "CRITICAL: Server returned $response"
    exit 1
fi
EOF

chmod +x /opt/anova-assistant/healthcheck.sh
```

### 6.3 Add to Cron for Local Alerts (Optional)

```bash
# Edit crontab
crontab -e

# Add line to check every 5 minutes and log failures
*/5 * * * * /opt/anova-assistant/healthcheck.sh >> /var/log/anova-server/healthcheck.log 2>&1 || echo "Health check failed at $(date)" >> /var/log/anova-server/healthcheck.log
```

---

## 7. Backup and Recovery

### 7.1 What to Back Up

| Item | Location | Criticality | Backup Method |
|------|----------|-------------|---------------|
| Credentials | `/opt/anova-assistant/config/` | Critical | Encrypted copy |
| Application code | `/opt/anova-assistant/server/` | High | Git repository |
| Cloudflare config | `~/.cloudflared/` | High | Manual copy |
| Service files | `/etc/systemd/system/anova-server.service` | Medium | Version control |

### 7.2 Backup Script

```bash
cat > /opt/anova-assistant/backup.sh << 'EOF'
#!/bin/bash
# Backup critical configuration

BACKUP_DIR="/home/pi/backups"
DATE=$(date +%Y%m%d)
BACKUP_FILE="$BACKUP_DIR/anova-backup-$DATE.tar.gz"

mkdir -p $BACKUP_DIR

# Create backup (excludes venv, logs)
tar -czf $BACKUP_FILE \
    --exclude='venv' \
    --exclude='*.log' \
    --exclude='__pycache__' \
    /opt/anova-assistant/config \
    /opt/anova-assistant/server \
    /home/pi/.cloudflared \
    /etc/systemd/system/anova-server.service

# Keep only last 5 backups
ls -t $BACKUP_DIR/anova-backup-*.tar.gz | tail -n +6 | xargs -r rm

echo "Backup created: $BACKUP_FILE"
ls -lh $BACKUP_FILE
EOF

chmod +x /opt/anova-assistant/backup.sh
```

### 7.3 Schedule Weekly Backups

```bash
# Add to crontab
crontab -e

# Add line for weekly backup (Sunday at 2am)
0 2 * * 0 /opt/anova-assistant/backup.sh >> /var/log/anova-server/backup.log 2>&1
```

### 7.4 Full Recovery Procedure

If the SD card fails or you need to rebuild:

1. **Flash new SD card** with Raspberry Pi OS Lite (Section 4.2.1)
2. **SSH into Pi** and update system
3. **Install packages:** `sudo apt install -y python3-pip python3-venv git`
4. **Restore from backup:**
   ```bash
   # Copy backup file to new Pi
   scp /path/to/anova-backup-YYYYMMDD.tar.gz pi@anova-server.local:~
   
   # On Pi, extract
   sudo tar -xzf ~/anova-backup-*.tar.gz -C /
   ```
5. **Reinstall cloudflared** (Section 4.4.2)
6. **Recreate venv:** `cd /opt/anova-assistant && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
7. **Enable services:** `sudo systemctl enable anova-server cloudflared && sudo systemctl start anova-server cloudflared`
8. **Verify:** `curl http://localhost:5000/health`

---

## 8. Update/Deployment Procedure

### 8.1 Deploying Code Updates

```bash
# On development machine: push changes to git
git add -A
git commit -m "Description of changes"
git push

# On Pi: pull changes
ssh pi@anova-server.local
cd /opt/anova-assistant
git pull

# Restart service to pick up changes
sudo systemctl restart anova-server

# Verify
curl http://localhost:5000/health
```

### 8.2 One-Line Update Command

```bash
# Run from development machine
ssh pi@anova-server.local "cd /opt/anova-assistant && git pull && sudo systemctl restart anova-server && curl -s http://localhost:5000/health"
```

### 8.3 Updating Dependencies

```bash
# On Pi
cd /opt/anova-assistant
source venv/bin/activate
pip install -U -r requirements.txt
sudo systemctl restart anova-server
```

### 8.4 Updating the API Key

If the API key needs rotation:

1. Generate new key on development machine:
   ```bash
   python3 -c "import secrets; print(f'sk-anova-{secrets.token_urlsafe(32)}')"
   ```

2. Update on Pi:
   ```bash
   ssh pi@anova-server.local
   # Edit config file with new key
   nano /opt/anova-assistant/config/credentials.json
   # Restart service
   sudo systemctl restart anova-server
   ```

3. Update Custom GPT:
   - Edit Custom GPT → Actions → Authentication
   - Enter new API key
   - Save

---

## 9. Network Architecture

### 9.1 Network Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            NETWORK ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────────────┘

    INTERNET                           LOCAL NETWORK
    ────────────────────────────────────────────────────────────────────────

    ┌──────────────┐                   ┌──────────────────────────────────┐
    │   ChatGPT    │                   │      Raspberry Pi Zero 2 W       │
    │   (OpenAI)   │                   │                                  │
    └──────┬───────┘                   │  ┌─────────────┐                 │
           │                           │  │cloudflared  │◄────────────────┤
           │ HTTPS                     │  │   daemon    │  Outbound only  │
           │                           │  └──────┬──────┘  (no inbound)   │
           ▼                           │         │                        │
    ┌──────────────┐                   │         │ localhost:5000         │
    │  Cloudflare  │◄──────────────────┤         ▼                        │
    │    Edge      │  Tunnel Protocol  │  ┌─────────────┐                 │
    │              │  (outbound from   │  │   Flask     │                 │
    └──────────────┘   Pi, encrypted)  │  │   Server    │                 │
                                       │  └──────┬──────┘                 │
                                       │         │                        │
                                       │         │ HTTPS                  │
                                       │         ▼                        │
                                       │  ┌─────────────┐                 │
                                       │  │Anova Cloud  │ ────────────────┤
                                       │  │   API       │    WiFi         │
                                       │  └─────────────┘                 │
                                       │                                  │
                                       └──────────────────────────────────┘

KEY POINTS:
• No inbound ports opened on router (Cloudflare Tunnel is outbound-only)
• All traffic encrypted (HTTPS/TLS)
• Pi only needs outbound internet access
• Anova device controlled via cloud API (not local network)
```

### 9.2 Firewall Configuration (Optional)

The Pi doesn't require any inbound ports. For additional security:

```bash
# Install UFW (Uncomplicated Firewall)
sudo apt install -y ufw

# Default deny incoming, allow outgoing
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (for admin access)
sudo ufw allow ssh

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## 10. Troubleshooting

### 10.1 Service Won't Start

```bash
# Check service status
sudo systemctl status anova-server

# View detailed logs
sudo journalctl -u anova-server -n 100

# Common issues:
# - Missing dependencies: source venv/bin/activate && pip install -r requirements.txt
# - Permission denied: Check file ownership (should be pi:pi)
# - Port in use: Check with `sudo lsof -i :5000`
```

### 10.2 Tunnel Not Connecting

```bash
# Check cloudflared service
sudo systemctl status cloudflared

# View cloudflared logs
sudo journalctl -u cloudflared -n 100

# Common issues:
# - Invalid credentials: Re-run `cloudflared tunnel login`
# - DNS not propagated: Wait 5 minutes, then retry
# - Config syntax error: Validate ~/.cloudflared/config.yml
```

### 10.3 API Returns 503 (Device Offline)

1. Check Anova device is plugged in
2. Check Anova WiFi indicator
3. Verify Anova app can connect
4. Check credentials in config file
5. Restart server: `sudo systemctl restart anova-server`

### 10.4 High Memory Usage

```bash
# Check memory
free -m

# If memory is low, reduce gunicorn workers in service file
# Change --workers 2 to --workers 1
sudo nano /etc/systemd/system/anova-server.service
sudo systemctl daemon-reload
sudo systemctl restart anova-server
```

### 10.5 SD Card Health

```bash
# Check filesystem health
sudo dmesg | grep -i error

# Check disk usage
df -h

# If over 80% full, clean logs:
sudo rm /var/log/anova-server/*.gz
sudo journalctl --vacuum-time=7d
```

---

## 11. Security Hardening Checklist

| Item | Status | Notes |
|------|--------|-------|
| SSH key authentication only | ☐ | Disable password auth |
| Credentials file permissions 600 | ☐ | `chmod 600 config/credentials.json` |
| UFW firewall enabled | ☐ | Optional but recommended |
| Automatic security updates | ☐ | `sudo apt install unattended-upgrades` |
| systemd hardening options | ☐ | Included in service file |
| No root login via SSH | ☐ | Edit `/etc/ssh/sshd_config` |

---

## 12. Performance Tuning (Optional)

### 12.1 Reduce Memory Footprint

If memory is tight on Pi Zero 2 W:

```bash
# Reduce GPU memory (headless server doesn't need it)
echo "gpu_mem=16" | sudo tee -a /boot/config.txt

# Disable Bluetooth (if not needed)
echo "dtoverlay=disable-bt" | sudo tee -a /boot/config.txt

# Reboot to apply
sudo reboot
```

### 12.2 Improve SD Card Longevity

```bash
# Reduce swap usage
echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf

# Mount logs in memory (optional, logs lost on reboot)
# Add to /etc/fstab:
# tmpfs /var/log tmpfs defaults,noatime,nosuid,mode=0755,size=50m 0 0
```

---

## 13. Verification Checklist

### 13.1 Post-Deployment Verification

| Test | Command | Expected Result | ✓ |
|------|---------|-----------------|---|
| Service running | `systemctl status anova-server` | Active (running) | ☐ |
| Health endpoint | `curl http://localhost:5000/health` | `{"status":"ok"...}` | ☐ |
| Tunnel active | `systemctl status cloudflared` | Active (running) | ☐ |
| External access | `curl https://your-tunnel-url/health` | `{"status":"ok"...}` | ☐ |
| Start cook (with API key) | Test via Custom GPT | Success response | ☐ |
| Auto-restart | `sudo systemctl restart anova-server` | Restarts cleanly | ☐ |
| Reboot recovery | `sudo reboot` | Services start automatically | ☐ |

### 13.2 Week-One Monitoring

After deployment, check these daily for the first week:

- [ ] Uptime monitor shows no outages
- [ ] Logs not growing excessively
- [ ] Memory usage stable
- [ ] Successful cook completions reported by user

---

## 14. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-08 | Claude | Initial specification |

---

## 15. Quick Reference Card

```
═══════════════════════════════════════════════════════════════
                    ANOVA SERVER QUICK REFERENCE
═══════════════════════════════════════════════════════════════

SERVICE COMMANDS
────────────────
Start:    sudo systemctl start anova-server
Stop:     sudo systemctl stop anova-server
Restart:  sudo systemctl restart anova-server
Status:   sudo systemctl status anova-server
Logs:     sudo journalctl -u anova-server -f

CLOUDFLARE TUNNEL
─────────────────
Status:   sudo systemctl status cloudflared
Restart:  sudo systemctl restart cloudflared
Logs:     sudo journalctl -u cloudflared -f

HEALTH CHECKS
─────────────
Local:    curl http://localhost:5000/health
External: curl https://YOUR-TUNNEL-URL/health

KEY PATHS
─────────
App:      /opt/anova-assistant/
Config:   /opt/anova-assistant/config/credentials.json
Logs:     /var/log/anova-server/
Service:  /etc/systemd/system/anova-server.service
Tunnel:   ~/.cloudflared/config.yml

DEPLOY UPDATE
─────────────
ssh pi@anova-server.local
cd /opt/anova-assistant && git pull
sudo systemctl restart anova-server

═══════════════════════════════════════════════════════════════
```
