# YOLO11 Webcam Object Detection

This project performs real-time object detection using the YOLO11n (nano) model and your computer's webcam.

## Requirements

- Python 3.8+
- Webcam

## Installation

1.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main script to start object detection:

```bash
python main.py
```

-   The application will open a window showing the live video feed.
-   Bounding boxes, class labels, and confidence scores will be drawn on detected objects.
-   The FPS (Frames Per Second) is displayed in the top-left corner.
-   Press **'q'** to quit the application.

## Testing

To run the unit tests:

```bash
python -m unittest tests/test_app.py
```

## Performance

The project uses the `yolo11n` model and processing at 640x480 resolution to achieve real-time performance (~15-25 FPS on Apple Silicon M1/M2).
