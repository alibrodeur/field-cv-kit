import cv2

ip = "YOUR_CAMERA_IP"
path = "live1s1.sdp"

# Standard Vivotek factory defaults
test_auths = [
    ("root", "YOUR_PASSWORD"),
    ("root", ""),          # Factory default: root with NO password
    ("root", "root"),      # Factory default: root / root
    ("admin", "admin"),    # Admin / admin
    ("root", "1234")       # Root / 1234
]

success = False
for user, pwd in test_auths:
    auth_str = f"{user}:{pwd}@" if pwd else f"{user}@"
    url = f"rtsp://{auth_str}{ip}:554/{path}"
    print(f"Trying: rtsp://{user}:{'****' if pwd else '<empty>'}@{ip}:554/{path}")
    
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"\nSUCCESS! Connected with user '{user}' and password '{pwd}'!")
            print(f"Frame resolution: {frame.shape[1]}x{frame.shape[0]}")
            print(f"\nYour working RTSP URL is:\n{url}")
            success = True
            cap.release()
            break
        cap.release()

if not success:
    print("\nCould not connect with standard defaults.")
