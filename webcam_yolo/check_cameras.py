import cv2

def test_cameras():
    print("Testing camera indices 0 to 4...")
    for index in range(5):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            print(f"Index {index}: Opened successfully.")
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                print(f"Index {index}: Capture successful. Resolution: {w}x{h}")
                # Save a frame to verify visually if needed, or just rely on dimensions/success
                cv2.imwrite(f"camera_test_{index}.jpg", frame)
            else:
                print(f"Index {index}: Opened but failed to capture frame (blank/timeout).")
            cap.release()
        else:
            print(f"Index {index}: Failed to open.")

if __name__ == "__main__":
    test_cameras()
