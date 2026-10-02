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
