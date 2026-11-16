

<div align="center">

![Own your bambu Cloud](https://img.shields.io/badge/Own%20your%20bambu%20Cloud-v1.0.0-orange?style=for-the-badge&logo=cube)
[![Author](https://img.shields.io/badge/Author-Ryan%20Ben%20Hassine-blue?style=for-the-badge&logo=safari)](https://ryanbenhassine.com)
[![License](https://img.shields.io/badge/License-ryanbenhassine.com-green?style=for-the-badge)](https://ryanbenhassine.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com/)
[![Zero Database](https://img.shields.io/badge/Storage-100%25%20JSON-purple?style=for-the-badge&logo=json)](https://ryanbenhassine.com)

**An open-source, zero-database Bambu Lab farm management platform.**  
*Full local control, multi-printer telemetry, AI defect detection, filament stock tracking, and cloud video watermarking.*

**Built by [Ryan Ben Hassine](https://ryanbenhassine.com)**

[Features](#-key-features) • [Requirements](#-system--hosting-requirements) • [Remote Access](#-secure-remote-access) • [Installation](#-fast-installation) • [Docker Compose](#-docker-compose-setup) • [Architecture](#-architecture--json-storage) • [API](#-api-endpoints) • [License](#-author--license)

</div>

---

## 🚀 Overview

**Own your bambu Cloud** is a lightweight, self-hosted web operating system built specifically for 3D printing makers, creators, and farm owners using **Bambu Lab 3D printers** (P1S, X1C, P1P, A1, A1 Mini).

Unlike complex commercial cloud suites or heavy database systems, **Own your bambu Cloud**:
- Operates **100% locally** via Bambu Lab LAN Mode (MQTT over TLS & direct camera TLS).
- Requires **ZERO SQL databases** (PostgreSQL/MySQL) — all state is safely persisted in atomic **JSON files**.
- Features an **Apple-grade pure dark mode UI** with a responsive collapsible left sidebar navigation.
- Runs anywhere with a single Docker container.

---

## 🖥️ System & Hosting Requirements

Because this platform acts as your private, self-hosted cloud replacement, it must remain online **24/7 on your local network** to maintain live printer telemetry, AI defect monitoring, and automated video processing.

You can host it on any always-on machine capable of running **Docker**:
- **Single-Board Computers:** Raspberry Pi (Pi 4 / Pi 5 recommended) or similar ARM/x86 boards.
- **Home Server OS:** UmbrelOS, CasaOS, Unraid, Proxmox, or TrueNAS.
- **Repurposed Hardware:** An old laptop, mini PC (Intel NUC), or desktop running Linux, Windows (WSL2/Docker Desktop), or macOS.
- **Network:** Must be connected to the same local network (LAN/VLAN) as your Bambu Lab printers.

---

## 🌐 Secure Remote Access

Want to monitor your printers and manage prints from anywhere in the world without exposing your local network to risky open firewall ports? Choose one of the two zero-trust methods below:

### 🛡️ Option 1: Tailscale VPN (Safer & Recommended)
**Tailscale** creates a private, encrypted mesh network (WireGuard) exclusively between your personal devices without exposing your dashboard to the public internet at all.
1. Install **Tailscale** on your host server (Raspberry Pi, UmbrelOS, or laptop) and on your phone/remote computer.
2. Sign in to the same Tailscale account on both devices.
3. Access your printer dashboard securely from anywhere in the world using your host's private Tailscale IP or MagicDNS name (e.g., `http://bambu-server:9930`).

### ☁️ Option 2: Cloudflare Tunnel & Local AI Agents (Custom Domain)
If you prefer accessing your dashboard via your own custom domain name (e.g., `https://bambu.yourdomain.com`), you can use **Cloudflare Tunnel (`cloudflared`)**.

If you are unfamiliar with networking or reverse proxies, you can install a local AI agentic assistant on your server or laptop—such as **Antigravity** or **Claude Code**—and let it handle the entire setup automatically:
1. Install **Antigravity** or **Claude Code** locally on your host machine.
2. Ask the agent:  
   > *"Install `cloudflared` on my system and configure a Cloudflare Tunnel pointing my domain `bambu.yourdomain.com` to `http://localhost:9930`."*
3. Follow the agent's browser authentication prompt for Cloudflare, and your private 3D printing cloud will be securely accessible with automatic HTTPS and Zero Trust protection.

---

## ✨ Key Features

### 1. 🖨️ Multi-Printer Management & Clean Manual Testing
- Add unlimited Bambu Lab printers manually via local IP, LAN access code, and serial number.
- Instant switching between printers with real-time status indicators.
- Clean onboarding state: starts completely empty so you can test end-to-end configuration from scratch.

### 2. ⚡ Real-Time Telemetry & Hardware Control
- **Live Thermal Gauges**: Nozzle and Heatbed actual vs. target temperatures.
- **Cooling Metrics**: Part cooling fan, Auxiliary fan, and Chamber fan duty cycles.
- **Bed Position Tracker (0% - 100% / 0 - 256mm)**: Accurate visual slider with 1-click height presets (Top, 25%, 50%, 70%, Bottom).
- **Smart Hardware Positions**:
  - `Service`: Lowers bed to 70% and centers toolhead for ergonomic nozzle swap.
  - `Trash / Purge`: Moves head to purge chute for quick cleaning.
  - `Bump`: Cycles bed down and up to clear stray filament strings.
  - `Home & Center`: 1-click reference positioning.
- **Live Print Actions**: Pause, Resume, Stop, G-code console, and chamber light control.

### 3. 🧵 Workshop Filament Stock & 1-Click AMS Sync
- Manage your roll inventory in `data/filaments.json` (Brand, Material, Color hex swatch, and remaining grams).
- Visual spool consumption progress bars.
- **1-Click Sync to AMS**: Assign any spool from your stock directly to AMS slots (Slot 1 to 4) over LAN.

### 4. 👁️ AI Eye Guardian (Print Failure Watchdog)
- Automated computer vision to detect:
  - **Spaghetti Stringing & Air Printing**
  - **Bed Adhesion Loss & Corner Warping**
  - **Nozzle Clogs & Extrusion Starvation**
- **Dual API Support**:
  - **OpenAI API**: Uses GPT-4o / GPT-4o-mini vision models.
  - **Open-Source Local API**: Fully compatible with Ollama (`http://localhost:11434/v1`), LocalAI, or vLLM for 100% private offline inference.
- Built-in Autonomous Tier with lifetime license unlock.

### 5. 🎬 Cloud Video Studio & Brand Logo Watermarking
- Automated timelapse processor powered by integrated `ffmpeg`.
- Upload your brand logo (PNG / SVG / JPG).
- Customize position (Bottom-Right, Top-Right, Bottom-Left, Top-Left, Center) and scaling factor.
- Produces clean, professional MP4 videos ready for social media and customer handoffs.

### 6. 🌙 Apple-Grade Pure Dark Mode UI
- Locked dark aesthetic designed for workshop and factory monitors.
- Sleek collapsible left sidebar navigation.
- Zero clutter top action bar.

---

## ⚡ Fast Installation

Run the automated one-click installer:

```bash
git clone https://github.com/ryanbenhassine/own-bambu-cloud.git
cd own-bambu-cloud
chmod +x install.sh
./install.sh
```

The installer verifies your Docker setup, sets up directory structures, launches the container on **port 9930**, and checks system health.

Once started, open your browser:
👉 **`http://localhost:9930`**

---

## 🐳 Docker Compose Setup

If you prefer running Docker Compose directly:

```yaml
services:
  own-bambu-cloud:
    build: .
    image: own-bambu-cloud:latest
    container_name: own-bambu-cloud
    restart: unless-stopped
    ports:
      - "9930:9930"
    volumes:
      - ./data:/app/data
      - ./app:/app/app
      - ./static:/app/static
    environment:
      - DATA_DIR=/app/data
      - PYTHONUNBUFFERED=1
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Start the service:
```bash
docker compose up -d
```

Stop the service:
```bash
docker compose down
```

---

## 📁 Architecture & JSON Storage

All persistent configuration and runtime state reside in human-readable JSON files in `./data/`:

```
own-bambu-cloud/
├── app/
│   ├── main.py              # FastAPI server & route handlers
│   ├── json_store.py        # Atomic thread-safe JSON engine
│   ├── bambu_client.py      # Bambu LAN MQTT TLS client
│   ├── camera_streamer.py   # Port 6000 TLS chamber camera streamer
│   ├── ai_eye_engine.py     # Vision defect detection engine
│   └── video_processor.py   # ffmpeg video watermark compositing
├── data/                    # Zero-database storage (mounted to container)
│   ├── printers.json        # Configured printers (IP, access code, serial)
│   ├── filaments.json       # Filament roll inventory
│   ├── settings.json        # AI & watermark preferences
│   ├── ai_inspections.json  # Failure detection logs
│   ├── timelapses.json      # Processed video registry
│   ├── bed_state.json       # Z-height & bed positions
│   └── uploads/             # Logos and rendered MP4 files
├── static/
│   ├── css/app.css          # Apple-grade Dark Mode stylesheet
│   ├── js/app.js            # Vanilla JS frontend controller
│   └── index.html           # Single-page UI with left sidebar
├── Dockerfile               # Python 3.11 + ffmpeg container
├── docker-compose.yml       # Production Compose configuration
├── install.sh               # 1-click automated installer
├── run.sh                   # Fast startup script
└── LICENSE                  # Official licensing terms
```

---

## 🔌 API Endpoints

Interactive Swagger documentation is available out of the box at:  
👉 **`http://localhost:9930/docs`**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/printers` | List all configured printers |
| `POST` | `/api/printers` | Add a new printer manually |
| `DELETE` | `/api/printers/{id}` | Remove a printer from JSON storage |
| `GET` | `/api/printers/{id}/status` | Live telemetry, temperatures & bed state |
| `POST` | `/api/printers/{id}/action` | Hardware controls (`pause`, `resume`, `bed_pct`, `service`, `trash`, `bump`) |
| `GET` | `/api/printers/{id}/camera/stream` | Live MJPEG chamber camera video |
| `GET` | `/api/filaments` | List workshop filament spool inventory |
| `POST` | `/api/filaments` | Add new filament spool |
| `DELETE` | `/api/filaments/{id}` | Delete filament spool |
| `POST` | `/api/printers/{id}/ams/assign` | 1-Click sync spool to AMS slot (0 to 3) |
| `POST` | `/api/ai_eye/inspect` | Run AI vision inspection on current camera frame |
| `POST` | `/api/videos/upload_logo` | Upload brand watermark logo |
| `POST` | `/api/videos/demo` | Process video with custom logo overlay |

---

## 🛡️ Bambu Lab LAN Mode Setup

To obtain your printer credentials:
1. On your Bambu printer screen, navigate to **Settings ➔ WLAN**.
2. Enable **LAN Only Mode**.
3. Note your:
   - **Local IP Address** (e.g., `192.168.1.xxx`)
   - **Access Code** (8-digit alphanumeric passcode)
   - **Serial Number** (e.g., `01P00C...`)
4. Open `http://localhost:9930`, click **+ Add Printer**, and enter your details.

---

## 📜 Author & License

- **Author & Creator:** [Ryan Ben Hassine](https://ryanbenhassine.com)
- **Official Website:** [https://ryanbenhassine.com](https://ryanbenhassine.com)
- **License:** Licensed under terms by [ryanbenhassine.com](https://ryanbenhassine.com).
- **Copyright:** © 2026 [Ryan Ben Hassine](https://ryanbenhassine.com). All rights reserved.
