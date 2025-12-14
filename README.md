# Object Detection & Counting

A professional desktop application for real-time object detection and counting using YOLO models.

## 🎥 Demo Video

<video src="https://raw.githubusercontent.com/falkomeAI/YOLO-UI/main/outputs/v1.mp4"
       controls
       width="800">
</video>

🔗 [Direct video link](https://github.com/falkomeAI/YOLO-UI/blob/main/outputs/v1.mp4)



## Features

- **Object Detection**: Uses YOLOv8 models for accurate object detection
- **Line Counting**: Draw lines to count objects crossing (In/Out counting)
- **Zone Counting**: Draw polygons to count objects in zones
- **Multi-Class Selection**: Select multiple classes to detect/count
- **Real-time Statistics**: Live bar charts and count displays
- **Configuration Save/Load**: Save and load drawing configurations

## Screenshots

The UI includes:
- Left panel: Model settings, class filter, video input
- Center: Video display with drawing toolbar
- Right panel: Statistics graph and count details

## Installation

### Prerequisites

- Python 3.10+
- Conda environment (recommended)

### Setup

```bash
# Activate conda environment
conda activate ml

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

## Usage

### Quick Start

1. Run `python app.py`
2. Video and model auto-load if `test_video.mp4` and `yolov8n.pt` exist
3. Select LINE or ZONE mode
4. Draw on video
5. Click "Process Video"

### Drawing Controls

| Button | Action |
|--------|--------|
| OFF | Disable drawing |
| LINE | Draw counting lines (2 clicks) |
| ZONE | Draw counting zones (3+ clicks, click near first to close) |
| DONE | Finish current drawing |
| UNDO | Cancel current drawing |
| CLEAR | Remove all drawings |

### Class Filter

- **ALL**: Detect all 80 YOLO classes
- **NONE**: Detect nothing
- **COMMON**: Detect person, car, truck, bus, motorcycle, bicycle, dog, cat

### Zoom & Config

- **−/+**: Zoom in/out on video display
- **SAVE**: Save drawing configuration to JSON
- **LOAD**: Load drawing configuration from JSON

## Project Structure

```
.
├── app.py                  # Application entry point
├── requirements.txt        # Python dependencies
├── run.sh                  # Launcher script
├── README.md               # Documentation
├── config/                 # Configuration files
│   ├── classes.txt         # Custom class names
│   └── example_drawing.json
├── models/                 # Model weights directory
├── outputs/                # Output directory
└── src/
    ├── __init__.py
    ├── core/               # Core functionality
    │   ├── __init__.py
    │   ├── detector.py     # YOLO detector
    │   ├── counter.py      # Object counting & tracking
    │   └── drawing_tools.py # Line/polygon drawing
    └── ui/                 # User interface
        ├── __init__.py
        ├── desktop_app.py  # Main window
        ├── widgets.py      # Custom widgets
        └── styles.py       # UI styling
```

## Dependencies

| Package | Purpose |
|---------|---------|
| ultralytics | YOLO model framework |
| opencv-python | Video processing |
| PyQt6 | Desktop UI framework |
| numpy | Array operations |
| supervision | Detection utilities |
| Pillow | Image processing |

## License

MIT License
