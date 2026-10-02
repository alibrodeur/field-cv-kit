# field-cv-kit
Autonomous Edge Computer Vision and Video Streaming Hub

An edge-deployed computer vision and streaming system built for Raspberry Pi (Debian 12 Bookworm). The system ingests an RTSP video feed from a Vivotek IP camera, performs continuous real-time object detection (vehicles, pedestrians, bicycles) using YOLOv8, logs counts locally to CSV, updates Google Sheets in real-time via API, streams low-latency WebRTC/RTSP video, and automatically syncs logs and hourly snapshots to Google Drive.

---

## Architecture and Dual-Stream Strategy

Commercial IP cameras often limit high-resolution RTSP streams to a single concurrent socket. To prevent camera processor saturation and FFmpeg memory corruption (`av_frame_get_buffer! out of memory`), workloads are strictly segregated across dual streams:

```text
                       ┌──────────────────────────────────────────┐
                       │            Vivotek IP Camera             │
                       │             (169.254.9.206)              │
                       └────────────────────┬─────────────────────┘
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    │                                               │
  Primary Stream (High-Res: 1080p+)              Sub-Stream (Low-Res: 480p/720p)
  rtsp://.../live1s1.sdp                          rtsp://.../live1s2.sdp
                    │                                               │
                    ▼                                               ▼
┌───────────────────────────────────────┐       ┌───────────────────────────────────────┐
│     volpe_counter.py (YOLOv8)         │       │          MediaMTX Service             │
│   - Object detection (3s loop)        │       │   - Sub-stream proxy                  │
│   - Writes to counts_data.csv & Sheets│       │   - WebRTC / RTSP / HLS re-stream     │
└───────────────────┬───────────────────┘       └───────────────────┬───────────────────┘
                    │                                               │
                    ▼                                               ▼
┌───────────────────────────────────────┐       ┌───────────────────────────────────────┐
│     Automated Google Drive Sync       │       │           Remote Viewers              │
│ - counts_data.csv (Every 1m)          │       │ - WebRTC: http://<pi-ip>:8889/cam     │
│ - password_screengrab.py (Every 1h)   │       │ - RTSP: rtsp://<pi-ip>:8554/cam       │
└───────────────────────────────────────┘       └───────────────────────────────────────┘
Primary Stream (live1s1.sdp): Dedicated exclusively to volpe_counter.py for maximum YOLOv8 detection accuracy.

Secondary Stream (live1s2.sdp): Multiplexed into MediaMTX for low-overhead WebRTC/RTSP live streaming and accessed briefly by password_screengrab.py for hourly snapshots.

Repository Structure
Plaintext
.
├── volpe_counter.py          # Primary YOLOv8 object detection and logging engine
├── password_screengrab.py    # Sub-stream snapshot capture utility
├── test_cam.py               # RTSP camera authentication test script
├── mediamtx.yml              # MediaMTX RTSP/WebRTC proxy configuration
├── mediamtx.service          # Systemd unit file for MediaMTX auto-start
├── requirements.txt          # Python dependencies
├── LICENSE.md                # CC0 1.0 Universal Public Domain License
└── README.md                 # Project documentation
Setup Guide
1. System Preparation
Update system packages and install required dependencies:

Bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv ffmpeg rclone git iptables-persistent
Clone the repository and set up the Python virtual environment:

Bash
git clone [https://github.com/YOUR_USERNAME/raspberry-pi-ai-camera.git](https://github.com/YOUR_USERNAME/raspberry-pi-ai-camera.git)
cd raspberry-pi-ai-camera

python3 -m venv myenv
source myenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
2. Network Configuration (NAT and Port Forwarding)
If your IP camera uses an Ethernet link-local IP (169.254.x.x), route traffic from your Pi's Wi-Fi hotspot interface to the camera:

Bash
# Enable IPv4 Packet Forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Forward HTTP (80) and RTSP (554) traffic to the camera IP
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 169.254.9.206:80
sudo iptables -t nat -A PREROUTING -p tcp --dport 554 -j DNAT --to-destination 169.254.9.206:554
sudo iptables -t nat -A POSTROUTING -j MASQUERADE

# Save rules to persist across reboots
sudo netfilter-persistent save
3. MediaMTX Live Stream Proxy
Download the mediamtx binary matching your architecture (e.g., Linux ARM64) into the root directory.

Update mediamtx.yml with your camera credentials and IP address:

YAML
paths:
  cam:
    source: rtsp://YOUR_USER:YOUR_PASSWORD@YOUR_CAMERA_IP:554/live1s2.sdp
To run MediaMTX automatically as a system service:

Bash
sudo cp mediamtx.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
4. Cloud Integration
Google Drive (rclone)
Run rclone config to link your Google Drive account under the remote name gdrive:.

Ensure target directories (e.g., StarlinkProject/ and StarlinkProject/Images/) exist in Google Drive.

Google Sheets API
Save your Google Cloud Service Account key to /home/volpe/service_account.json.

Create a Google Sheet named "Traffic Detections" and grant edit access to the Service Account email address.

5. Automated Jobs (crontab)
Open the crontab editor (crontab -e) and add the following entries:

Bash
# Sync local CSV detection logs to Google Drive every minute
* * * * * /usr/bin/rclone copy /home/volpe/counts_data.csv gdrive:StarlinkProject/ --drive-use-trash=false --ignore-times >> /home/volpe/rclone.log 2>&1

# Start YOLO counter automatically on boot (with a 10-second network delay)
@reboot sleep 10 && /home/volpe/myenv/bin/python3 /home/volpe/volpe_counter.py >> /home/volpe/volpe_counter.log 2>&1

# Capture hourly snapshot, assign timestamp, upload to Drive, and clean local temp file
0 * * * * /home/volpe/myenv/bin/python3 /home/volpe/password_screengrab.py >> /home/volpe/screengrab.log 2>&1 && FILE_TIME=$(/bin/date +\%Y\%m\%d_\%H\%M\%S) && /bin/cp /home/volpe/screengrab.jpg /home/volpe/screengrab_$FILE_TIME.jpg && /usr/bin/rclone copy /home/volpe/screengrab_$FILE_TIME.jpg gdrive:StarlinkProject/Images/ && rm -f /home/volpe/screengrab_$FILE_TIME.jpg
Technical Notes and Bug Fixes
OpenCV RTSP UDP Interrupts: Enforced RTSP over TCP with explicit timeouts (os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000") to resolve 30-second socket hangs during network drops.

FFmpeg Memory Leaks: Added an open-grab-retrieve-release cycle to frame collection. The script calls cap.grab() to clear hardware buffers before frame retrieval, and cap.release() frees RAM immediately afterward.

Cron Execution Environment: Full binary paths (/usr/bin/rclone, /bin/cp, /bin/date) are explicitly defined to avoid issues caused by cron's minimal default PATH.

Subshell Timestamp Consistency: Assigned the timestamp to a variable (FILE_TIME) before copying, uploading, and removing image files to prevent file-not-found errors caused by clock ticks during execution.

License
This project is licensed under the Creative Commons 1.0 Universal (CC0 1.0) License - see the LICENSE.md file for details.
