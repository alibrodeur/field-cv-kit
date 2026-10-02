import cv2
import os
import csv
import time
from datetime import datetime
from ultralytics import YOLO
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. YOLO & Camera Configuration
# ==========================================
model = YOLO('yolov8n.pt')

# COCO Dataset IDs
PERSON_CLASS = 0
BIKE_CLASS = 1
VEHICLE_CLASSES = [2, 3, 5, 7] # car, motorcycle, bus, truck

# Combine them so YOLO only looks for these specific things (saves processing)
ALL_TARGET_CLASSES = [PERSON_CLASS, BIKE_CLASS] + VEHICLE_CLASSES

CAMERA_URL = "rtsp://YOUR_USER:YOUR_PASSWORD@YOUR_CAMERA_IP:554/live1s1.sdp"
CSV_FILE = "/home/volpe/counts_data.csv"
LOOP_INTERVAL = 3

# Global VideoCapture instance keeps the connection up
cap = None

# ==========================================
# Google Sheets Real-time Updating Setup
# ==========================================
SHEET_NAME = "Traffic Detections"
SERVICE_ACCOUNT_FILE = "/home/volpe/service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

sheet = None
gsheet_buffer = []
LAST_GSHEET_SYNC = time.time()
SYNC_INTERVAL_SEC = 30

try:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open(SHEET_NAME).sheet1
    if not sheet.get_all_values():
        sheet.append_row(['Timestamp', 'Vehicles', 'Pedestrians', 'Bikes'])
    print("Successfully connected to Google Sheets API.")
except Exception as e:
    print(f"Warning: Could not connect to Google Sheets on startup: {e}")

def sync_to_gsheets():
    global gsheet_buffer, LAST_GSHEET_SYNC, sheet
    if not gsheet_buffer:
        return
    try:
        if sheet is None:
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            gc = gspread.authorize(creds)
            sheet = gc.open(SHEET_NAME).sheet1
        sheet.append_rows(gsheet_buffer)
        print(f"Pushed {len(gsheet_buffer)} rows to Google Sheets.")
        gsheet_buffer.clear()
        LAST_GSHEET_SYNC = time.time()
    except Exception as e:
        print(f"Google Sheets Sync Error: {e}")


def poll_camera_and_count(rtsp_url):
    global cap, LAST_GSHEET_SYNC
    
    # Initialize connection if it hasn't started or dropped out
    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Clear old buffered frames to make space for new frame
    for _ in range(5):
        cap.grab()

    ret, frame = cap.retrieve()

    if not ret or frame is None:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Could not grab a frame from the camera.")
        cap.release()
        cap = None
        return

    # Run YOLO object detection targeting all our categories
    results = model(frame, classes=ALL_TARGET_CLASSES, conf=0.5, verbose=False)

    # Initialize counters for this frame
    pedestrian_count = 0
    bike_count = 0
    vehicle_count = 0

    # Loop through every detected object and tally them up
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        if class_id == PERSON_CLASS:
            pedestrian_count += 1
        elif class_id == BIKE_CLASS:
            bike_count += 1
        elif class_id in VEHICLE_CLASSES:
            vehicle_count += 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ==========================================
    # 2. Log to Local CSV
    # ==========================================
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode='a', newline='', buffering=1) as file:
        writer = csv.writer(file)
        # If this is the first time running, write the column headers
        if not file_exists:
            writer.writerow(['Timestamp', 'Vehicles', 'Pedestrians', 'Bikes'])

        # Write the data row
        writer.writerow([timestamp, vehicle_count, pedestrian_count, bike_count])

    print(f"Logged [{vehicle_count} Vehicles, {pedestrian_count} Pedestrians, {bike_count} Bikes] at {timestamp}")

    # ==========================================
    # 3. Buffer & Sync to Google Sheets
    # ==========================================
    gsheet_buffer.append([timestamp, vehicle_count, pedestrian_count, bike_count])
    if time.time() - LAST_GSHEET_SYNC >= SYNC_INTERVAL_SEC:
        sync_to_gsheets()

if __name__ == "__main__":
    print(f"Starting counts every {LOOP_INTERVAL}s...")
    try:
        while True:
            start_time = time.time()
            poll_camera_and_count(CAMERA_URL)
            elapsed_time = time.time() - start_time
            time.sleep(max(0.1, LOOP_INTERVAL - elapsed_time))
    except KeyboardInterrupt:
        sync_to_gsheets()
        print("\nStopping data collection.")
