"""
Drawing Tools for Lines and Polygons
Used for defining counting zones and crossing lines
"""

import json
from typing import List, Tuple, Optional, Dict
import numpy as np
import cv2
from dataclasses import dataclass, asdict


@dataclass
class CountingLine:
    """Represents a line for counting objects crossing it."""
    id: str
    start: Tuple[int, int]
    end: Tuple[int, int]
    name: str = "Line"
    color: Tuple[int, int, int] = (255, 165, 0)  # Orange in BGR (more visible)
    thickness: int = 3
    direction: str = "both"  # 'in', 'out', 'both'

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CountingLine':
        return cls(**data)

    def get_line_equation(self) -> Tuple[float, float, float]:
        """Get line equation coefficients (ax + by + c = 0)."""
        x1, y1 = self.start
        x2, y2 = self.end
        a = y2 - y1
        b = x1 - x2
        c = x2 * y1 - x1 * y2
        return a, b, c

    def point_side(self, point: Tuple[int, int]) -> int:
        """
        Determine which side of line a point is on.
        Returns: -1 (left/above), 0 (on line), 1 (right/below)
        """
        a, b, c = self.get_line_equation()
        value = a * point[0] + b * point[1] + c
        if abs(value) < 1e-6:
            return 0
        return 1 if value > 0 else -1


@dataclass
class CountingPolygon:
    """Represents a polygon zone for counting objects inside."""
    id: str
    points: List[Tuple[int, int]]
    name: str = "Zone"
    color: Tuple[int, int, int] = (255, 0, 255)  # Magenta in BGR
    thickness: int = 2
    fill_alpha: float = 0.3

    def to_dict(self) -> dict:
        data = asdict(self)
        data['points'] = [list(p) for p in self.points]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'CountingPolygon':
        data['points'] = [tuple(p) for p in data['points']]
        return cls(**data)

    def contains_point(self, point: Tuple[int, int]) -> bool:
        """Check if a point is inside the polygon."""
        if len(self.points) < 3:
            return False

        pts = np.array(self.points, dtype=np.int32)
        result = cv2.pointPolygonTest(pts, point, False)
        return result >= 0


class DrawingCanvas:
    """
    Interactive canvas for drawing lines and polygons on video frames.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.lines: List[CountingLine] = []
        self.polygons: List[CountingPolygon] = []

        # Drawing state
        self.current_points: List[Tuple[int, int]] = []
        self.drawing_mode: str = "none"  # 'line', 'polygon', 'none'
        self.line_counter = 0
        self.polygon_counter = 0
        
        # Custom colors (BGR format for OpenCV)
        self.line_color: Tuple[int, int, int] = (255, 165, 0)  # Orange
        self.zone_color: Tuple[int, int, int] = (255, 0, 255)  # Magenta
    
    def set_line_color(self, color: Tuple[int, int, int]):
        """Set color for new lines (BGR format)."""
        self.line_color = color
    
    def set_zone_color(self, color: Tuple[int, int, int]):
        """Set color for new zones (BGR format)."""
        self.zone_color = color

    def set_mode(self, mode: Optional[str]):
        """Set drawing mode: 'line', 'polygon', or None.
        
        Note: This preserves existing completed drawings (lines/polygons).
        Only the current in-progress drawing points are cleared when switching modes.
        """
        # If there's an incomplete drawing, clear it
        if len(self.current_points) > 0:
            self.current_points = []
        
        if mode == "line":
            self.drawing_mode = "line"
        elif mode == "polygon":
            self.drawing_mode = "polygon"
        else:
            self.drawing_mode = "none"
        

    def start_line(self):
        """Start drawing a new line. Preserves existing completed drawings."""
        self.drawing_mode = "line"
        self.current_points = []

    def start_polygon(self):
        """Start drawing a new polygon. Preserves existing completed drawings."""
        self.drawing_mode = "polygon"
        self.current_points = []

    def add_point(self, x: int, y: int):
        """Add a point to current drawing."""
        # Only add point if in drawing mode
        if self.drawing_mode == "none":
            return
        
        # Clamp to valid range
        x = max(0, x)
        y = max(0, y)

        # For polygon: check if clicking near the first point to close
        if self.drawing_mode == "polygon" and len(self.current_points) >= 3:
            first_pt = self.current_points[0]
            dist = ((x - first_pt[0])**2 + (y - first_pt[1])**2)**0.5
            if dist < 20:  # Within 20 pixels of first point
                self.finish_drawing()
                return

        self.current_points.append((x, y))

        # Auto-complete line when 2 points are added
        if self.drawing_mode == "line" and len(self.current_points) == 2:
            self.finish_drawing()

    def finish_drawing(self) -> Optional[str]:
        """Finish current drawing and add to collection.
        
        Returns:
            The ID of the created line/polygon, or None if nothing was created.
        """
        result_id = None

        if self.drawing_mode == "line" and len(self.current_points) >= 2:
            self.line_counter += 1
            line = CountingLine(
                id=f"line_{self.line_counter}",
                start=self.current_points[0],
                end=self.current_points[1],
                name=f"Line {self.line_counter}",
                color=self.line_color  # Use custom color
            )
            self.lines.append(line)
            result_id = line.id

        elif self.drawing_mode == "polygon" and len(self.current_points) >= 3:
            self.polygon_counter += 1
            polygon = CountingPolygon(
                id=f"zone_{self.polygon_counter}",
                points=self.current_points.copy(),
                name=f"Zone {self.polygon_counter}",
                color=self.zone_color  # Use custom color
            )
            self.polygons.append(polygon)
            result_id = polygon.id

        # Clear current points but keep mode for continuous drawing
        self.current_points = []
        
        return result_id

    def finish_current(self):
        """Alias for finish_drawing."""
        return self.finish_drawing()

    def clear(self):
        """Alias for clear_all."""
        self.clear_all()

    def cancel_drawing(self):
        """Cancel current drawing but keep the mode active."""
        self.current_points = []
        # Don't reset drawing_mode - user can continue drawing

    def remove_line(self, line_id: str):
        """Remove a line by ID."""
        self.lines = [l for l in self.lines if l.id != line_id]

    def remove_polygon(self, polygon_id: str):
        """Remove a polygon by ID."""
        self.polygons = [p for p in self.polygons if p.id != polygon_id]

    def clear_all(self):
        """Clear all drawings."""
        self.lines = []
        self.polygons = []
        self.current_points = []
        self.drawing_mode = "none"

    def update_dimensions(self, width: int, height: int):
        """Update canvas dimensions and scale existing drawings."""
        if width == self.width and height == self.height:
            return

        scale_x = width / self.width
        scale_y = height / self.height

        # Scale lines
        for line in self.lines:
            line.start = (int(line.start[0] * scale_x), int(line.start[1] * scale_y))
            line.end = (int(line.end[0] * scale_x), int(line.end[1] * scale_y))

        # Scale polygons
        for poly in self.polygons:
            poly.points = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in poly.points]

        self.width = width
        self.height = height

    def draw_on_frame(
        self,
        frame: np.ndarray,
        show_labels: bool = True,
        counts: Optional[Dict[str, dict]] = None
    ) -> np.ndarray:
        """
        Draw all lines and polygons on a frame.

        Args:
            frame: Input frame
            show_labels: Whether to show names/labels
            counts: Optional dict with counts for each line/zone

        Returns:
            Annotated frame
        """
        annotated = frame.copy()

        # Draw polygons (with fill)
        for poly in self.polygons:
            pts = np.array(poly.points, dtype=np.int32)

            # Draw filled polygon with transparency
            overlay = annotated.copy()
            cv2.fillPoly(overlay, [pts], poly.color)
            cv2.addWeighted(overlay, poly.fill_alpha, annotated, 1 - poly.fill_alpha, 0, annotated)

            # Draw polygon outline
            cv2.polylines(annotated, [pts], True, poly.color, poly.thickness)

            # Draw label
            if show_labels and len(poly.points) > 0:
                centroid_x = int(np.mean([p[0] for p in poly.points]))
                centroid_y = int(np.mean([p[1] for p in poly.points]))

                label = poly.name
                if counts and poly.id in counts:
                    label += f": {counts[poly.id].get('count', 0)}"

                self._draw_label(annotated, label, (centroid_x, centroid_y), poly.color)

        # Draw lines
        for line in self.lines:
            cv2.line(annotated, line.start, line.end, line.color, line.thickness)

            mid_x = (line.start[0] + line.end[0]) // 2
            mid_y = (line.start[1] + line.end[1]) // 2

            # Draw small circles at endpoints
            cv2.circle(annotated, line.start, 6, line.color, -1)
            cv2.circle(annotated, line.end, 6, line.color, -1)

            # Draw label
            if show_labels:
                label = line.name
                if counts and line.id in counts:
                    c = counts[line.id]
                    label += f" In:{c.get('in', 0)} Out:{c.get('out', 0)}"

                self._draw_label(annotated, label, (mid_x, mid_y - 15), line.color)

        # Draw current drawing in progress
        if self.drawing_mode != "none" and len(self.current_points) > 0:
            color = (0, 255, 0)  # Green for current drawing

            for pt in self.current_points:
                cv2.circle(annotated, pt, 5, color, -1)

            if len(self.current_points) > 1:
                pts = np.array(self.current_points, dtype=np.int32)
                if self.drawing_mode == "polygon":
                    cv2.polylines(annotated, [pts], False, color, 2)
                else:
                    cv2.line(annotated, self.current_points[0], self.current_points[1], color, 2)

        return annotated

    def _draw_label(
        self,
        frame: np.ndarray,
        text: str,
        position: Tuple[int, int],
        color: Tuple[int, int, int]
    ):
        """Draw a label with background at position."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2

        (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)

        x, y = position
        x = max(0, min(x - text_w // 2, frame.shape[1] - text_w - 5))
        y = max(text_h + 5, y)

        # Dark background for better visibility
        bg_color = (30, 30, 30)  # Dark gray/black background
        
        # Draw shadow/outline for better visibility
        cv2.rectangle(
            frame,
            (x - 4, y - text_h - 7),
            (x + text_w + 4, y + 7),
            bg_color,
            -1
        )
        
        # Draw colored border
        cv2.rectangle(
            frame,
            (x - 4, y - text_h - 7),
            (x + text_w + 4, y + 7),
            color,
            2
        )

        # White text for clear visibility
        cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 255), thickness)

    def save_config(self, filepath: str):
        """Save lines and polygons to JSON file."""
        config = {
            'width': self.width,
            'height': self.height,
            'lines': [l.to_dict() for l in self.lines],
            'polygons': [p.to_dict() for p in self.polygons]
        }
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)

    def load_config(self, filepath: str):
        """Load lines and polygons from JSON file."""
        with open(filepath, 'r') as f:
            config = json.load(f)

        self.width = config.get('width', self.width)
        self.height = config.get('height', self.height)
        self.lines = [CountingLine.from_dict(l) for l in config.get('lines', [])]
        self.polygons = [CountingPolygon.from_dict(p) for p in config.get('polygons', [])]

        self.line_counter = len(self.lines)
        self.polygon_counter = len(self.polygons)

    def get_summary(self) -> str:
        """Get a summary of all drawings."""
        summary = []
        summary.append(f"Canvas Size: {self.width}x{self.height}")
        summary.append(f"Lines: {len(self.lines)}")
        for line in self.lines:
            summary.append(f"  - {line.name}: {line.start} → {line.end}")
        summary.append(f"Zones: {len(self.polygons)}")
        for poly in self.polygons:
            summary.append(f"  - {poly.name}: {len(poly.points)} points")
        return "\n".join(summary)

