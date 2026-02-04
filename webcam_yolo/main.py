import cv2
import time
from ultralytics import YOLO

def load_model(model_path="yolo11n.pt"):
    """Loads the YOLOv8 model."""
    return YOLO(model_path)

def process_frame(model, frame):
    """
    Runs inference on the frame and returns the annotated frame.
    """
    results = model(frame)
    # Visualize the results on the frame
    annotated_frame = results[0].plot()
    return annotated_frame

def calculate_fps(prev_time, curr_time):
    """Calculates FPS based on time difference."""
    if curr_time == prev_time:
        return 0.0
    return 1 / (curr_time - prev_time)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="YOLO11 Webcam Object Detection")
    parser.add_argument("--source", type=int, default=1, help="Camera source index (default: 1)")
    args = parser.parse_args()

    # Load the YOLOv8 model
    model = load_model()

    # Open the webcam
    print(f"Opening camera source: {args.source}")
    cap = cv2.VideoCapture(args.source)

    # Set resolution to 640x480 for speed
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_time = 0

    print("Starting YOLO11 Webcam Object Detection...")
    print("Press 'q' to quit.")

    while True:
        # Capture frame-by-frame
        ret, frame = cap.read()
        if not ret:
            print(f"Error: Failed to capture image from source {args.source}.")
            break

        curr_time = time.time()
        
        # Process the frame
        annotated_frame = process_frame(model, frame)
        
        # Calculate FPS
        fps = calculate_fps(prev_time, curr_time)
        prev_time = curr_time

        # Display FPS on frame
        cv2.putText(annotated_frame, f"FPS: {fps:.2f}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Display the resulting frame
        cv2.imshow("YOLO11 Webcam Object Detection", annotated_frame)

        # Break loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the capture and close windows
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
