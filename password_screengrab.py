import cv2
import time

url = "rtsp://YOUR_USER:YOUR_PASSWORD@YOUR_CAMERA_IP:554/live1s2.sdp"
output_file = "/home/volpe/screengrab.jpg"

print("Connecting to high-resolution stream...")
cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print("Error: Could not open the video stream.")
    exit(1)

print("Clearing frame buffer...")
# Give the stream a brief moment to initialize its buffer
time.sleep(1)

# Manually grab frames to empty the buffer just like volpe_counter.py does
for i in range(5):
    cap.grab()

print("Retrieving final clean image...")
ret, frame = cap.retrieve()

if ret and frame is not None:
    cv2.imwrite(output_file, frame)
    print(f"🎉 SUCCESS! Saved clean snapshot to: {output_file}")
else:
    print("Error: Could not retrieve a decoded frame from the camera buffer.")

cap.release()
