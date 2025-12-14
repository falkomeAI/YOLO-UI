"""
Object Detection Engine
Supports any YOLO weight file and custom class definitions
"""

import os
from typing import List, Optional, Tuple
import numpy as np
import cv2
from ultralytics import YOLO


class ObjectDetector:
    """
    Flexible object detector that works with any YOLO weight file
    and custom class definitions.
    """

    def __init__(
        self,
        weights_path: str = "yolov8n.pt",
        classes_path: Optional[str] = None,
        confidence: float = 0.5,
        device: str = "auto"
    ):
        """
        Initialize the detector.

        Args:
            weights_path: Path to YOLO weights file (.pt)
            classes_path: Path to classes.txt file (optional, uses model default if None)
            confidence: Detection confidence threshold
            device: Device to run inference on ('cpu', 'cuda', or 'auto')
        """
        self.weights_path = weights_path
        self.confidence = confidence
        self.device = device

        # Load the model
        self.model = self._load_model(weights_path)

        # Load custom classes if provided
        self.custom_classes = None
        if classes_path and os.path.exists(classes_path):
            self.custom_classes = self._load_classes(classes_path)

        # Get class names from model or custom file
        self.class_names = self.custom_classes if self.custom_classes else self.model.names

    def _load_model(self, weights_path: str) -> YOLO:
        """Load YOLO model from weights file."""
        if not os.path.exists(weights_path):
            print(f"Weights file not found at {weights_path}, attempting to download...")

        model = YOLO(weights_path)
        return model

    def _load_classes(self, classes_path: str) -> dict:
        """Load class names from text file."""
        classes = {}
        with open(classes_path, 'r') as f:
            for idx, line in enumerate(f):
                class_name = line.strip()
                if class_name:
                    classes[idx] = class_name
        return classes

    def detect(
        self,
        frame: np.ndarray,
        target_classes: Optional[List[int]] = None
    ) -> List[dict]:
        """
        Run detection on a single frame.

        Args:
            frame: Input image/frame as numpy array (BGR format)
            target_classes: List of class IDs to detect (None = all classes)

        Returns:
            List of detection dictionaries
        """
        results = self.model(
            frame,
            conf=self.confidence,
            classes=target_classes,
            verbose=False
        )

        detections = []

        if len(results) > 0:
            result = results[0]

            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)

                for i, (box, conf, cls_id) in enumerate(zip(boxes, confidences, class_ids)):
                    x1, y1, x2, y2 = box
                    class_name = self.class_names.get(cls_id, f"class_{cls_id}")

                    detections.append({
                        'id': i,
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'confidence': float(conf),
                        'class_id': int(cls_id),
                        'class_name': class_name,
                        'center': (int((x1 + x2) / 2), int((y1 + y2) / 2))
                    })

        return detections

    def update_confidence(self, confidence: float):
        """Update confidence threshold."""
        self.confidence = max(0.0, min(1.0, confidence))

    def reload_model(self, weights_path: str, classes_path: Optional[str] = None):
        """Reload model with new weights and classes."""
        self.weights_path = weights_path
        self.model = self._load_model(weights_path)

        if classes_path and os.path.exists(classes_path):
            self.custom_classes = self._load_classes(classes_path)
            self.class_names = self.custom_classes
        else:
            self.custom_classes = None
            self.class_names = self.model.names

    def get_class_names(self) -> List[str]:
        """Get list of all class names."""
        return list(self.class_names.values())

    def get_class_id(self, class_name: str) -> Optional[int]:
        """Get class ID from class name."""
        for idx, name in self.class_names.items():
            if name.lower() == class_name.lower():
                return idx
        return None


def draw_detections(
    frame: np.ndarray,
    detections: List[dict],
    color_map: Optional[dict] = None,
    thickness: int = 2,
    font_scale: float = 0.6
) -> np.ndarray:
    """
    Draw detection boxes and labels on frame.

    Args:
        frame: Input frame
        detections: List of detection dictionaries
        color_map: Optional dictionary mapping class_id to BGR color tuple
        thickness: Line thickness
        font_scale: Font scale for labels

    Returns:
        Annotated frame
    """
    annotated = frame.copy()

    if color_map is None:
        color_map = {}

    for det in detections:
        cls_id = det['class_id']

        # Generate consistent color for class
        if cls_id not in color_map:
            # Use simple hash for consistent colors
            r = ((cls_id * 123) % 200) + 55
            g = ((cls_id * 456) % 200) + 55
            b = ((cls_id * 789) % 200) + 55
            color_map[cls_id] = (b, g, r)  # BGR for OpenCV

        color = color_map[cls_id]
        bbox = det['bbox']
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        # Draw bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

        # Draw label background
        label = f"{det['class_name']} {det['confidence']:.2f}"
        (label_w, label_h), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )

        cv2.rectangle(
            annotated,
            (x1, y1 - label_h - 10),
            (x1 + label_w + 5, y1),
            color,
            -1
        )

        # Draw label text
        cv2.putText(
            annotated,
            label,
            (x1 + 2, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness
        )

        # Draw center point
        center = (int(det['center'][0]), int(det['center'][1]))
        cv2.circle(annotated, center, 4, color, -1)

    return annotated

