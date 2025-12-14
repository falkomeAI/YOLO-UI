"""
Object Counting Logic
Handles line crossing detection and zone counting
"""

from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import numpy as np

from .drawing_tools import CountingLine, CountingPolygon


@dataclass
class TrackedObject:
    """Represents a tracked object with history."""
    track_id: int
    class_id: int
    class_name: str
    current_center: Tuple[int, int]
    previous_center: Optional[Tuple[int, int]] = None
    bbox: Optional[List[int]] = None
    confidence: float = 0.0

    # Crossing state for each line
    line_sides: Dict[str, int] = None
    crossed_lines: Set[str] = None

    # Zone state
    in_zones: Set[str] = None

    def __post_init__(self):
        if self.line_sides is None:
            self.line_sides = {}
        if self.crossed_lines is None:
            self.crossed_lines = set()
        if self.in_zones is None:
            self.in_zones = set()

    def update_position(self, new_center: Tuple[int, int], bbox: List[int], confidence: float):
        """Update object position."""
        self.previous_center = self.current_center
        self.current_center = new_center
        self.bbox = bbox
        self.confidence = confidence


class ObjectCounter:
    """
    Counts objects crossing lines and entering/exiting zones.
    Uses simple centroid tracking for object persistence.
    """

    def __init__(self, max_distance: int = 100, max_frames_missing: int = 30):
        """
        Initialize counter.

        Args:
            max_distance: Maximum distance to associate detection with existing track
            max_frames_missing: Number of frames before removing missing track
        """
        self.max_distance = max_distance
        self.max_frames_missing = max_frames_missing

        # Tracked objects
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_track_id = 1
        self.frames_missing: Dict[int, int] = {}

        # Counting lines and zones
        self.lines: List[CountingLine] = []
        self.polygons: List[CountingPolygon] = []

        # Counts
        self.line_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {'in': 0, 'out': 0, 'total': 0}
        )
        self.zone_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {'count': 0, 'entered': 0, 'exited': 0}
        )

        # Class-specific counts
        self.line_class_counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: {'in': 0, 'out': 0})
        )
        self.zone_class_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def set_lines(self, lines: List[CountingLine]):
        """Set counting lines."""
        self.lines = lines

    def set_polygons(self, polygons: List[CountingPolygon]):
        """Set counting zones/polygons."""
        self.polygons = polygons

    def reset_counts(self):
        """Reset all counts."""
        self.line_counts.clear()
        self.zone_counts.clear()
        self.line_class_counts.clear()
        self.zone_class_counts.clear()

        for line in self.lines:
            self.line_counts[line.id] = {'in': 0, 'out': 0, 'total': 0}
        for poly in self.polygons:
            self.zone_counts[poly.id] = {'count': 0, 'entered': 0, 'exited': 0}

    def reset_tracking(self):
        """Reset all tracking state."""
        self.tracked_objects.clear()
        self.frames_missing.clear()
        self.next_track_id = 1
        self.reset_counts()
    
    def reset(self):
        """Alias for reset_tracking."""
        self.reset_tracking()
    
    def get_counts(self) -> Dict[str, int]:
        """Get simple count summary for display."""
        counts = {}
        
        # Line counts
        for line in self.lines:
            lc = self.line_counts.get(line.id, {})
            counts[f"{line.name}"] = lc.get('total', 0)
        
        # Zone counts
        for poly in self.polygons:
            zc = self.zone_counts.get(poly.id, {})
            counts[f"{poly.name}"] = zc.get('count', 0)
        
        return counts

    def update(self, detections: List[dict], lines: List = None, polygons: List = None) -> Dict[int, TrackedObject]:
        """
        Update tracking with new detections.

        Args:
            detections: List of detection dicts
            lines: Optional list of counting lines
            polygons: Optional list of counting polygons

        Returns:
            Dictionary of track_id -> TrackedObject
        """
        # Update lines and polygons if provided
        if lines is not None:
            self.lines = lines
        if polygons is not None:
            self.polygons = polygons
        
        matched_tracks, unmatched_detections = self._associate_detections(detections)

        # Update matched tracks
        for track_id, det in matched_tracks:
            track = self.tracked_objects[track_id]
            track.update_position(det['center'], det['bbox'], det['confidence'])
            self.frames_missing[track_id] = 0

        # Create new tracks for unmatched detections
        for det in unmatched_detections:
            track = TrackedObject(
                track_id=self.next_track_id,
                class_id=det['class_id'],
                class_name=det['class_name'],
                current_center=det['center'],
                bbox=det['bbox'],
                confidence=det['confidence']
            )
            self.tracked_objects[self.next_track_id] = track
            self.frames_missing[self.next_track_id] = 0
            self.next_track_id += 1

        # Increment missing frames for unmatched tracks
        matched_ids = {t[0] for t in matched_tracks}
        for track_id in list(self.tracked_objects.keys()):
            if track_id not in matched_ids:
                self.frames_missing[track_id] = self.frames_missing.get(track_id, 0) + 1

                if self.frames_missing[track_id] > self.max_frames_missing:
                    del self.tracked_objects[track_id]
                    del self.frames_missing[track_id]

        self._check_line_crossings()
        self._check_zone_occupancy()

        return self.tracked_objects

    def _associate_detections(self, detections: List[dict]) -> Tuple[List, List]:
        """Associate detections with existing tracks."""
        matched = []
        unmatched = list(detections)

        if not self.tracked_objects:
            return matched, unmatched

        track_ids = list(self.tracked_objects.keys())
        tracks = [self.tracked_objects[tid] for tid in track_ids]

        det_centers = [d['center'] for d in detections]
        track_centers = [t.current_center for t in tracks]

        if not det_centers or not track_centers:
            return matched, unmatched

        distances = np.zeros((len(track_centers), len(det_centers)))
        for i, tc in enumerate(track_centers):
            for j, dc in enumerate(det_centers):
                distances[i, j] = np.sqrt((tc[0] - dc[0])**2 + (tc[1] - dc[1])**2)

        used_detections = set()
        used_tracks = set()

        pairs = []
        for i in range(len(track_centers)):
            for j in range(len(det_centers)):
                if distances[i, j] < self.max_distance:
                    if tracks[i].class_id == detections[j]['class_id']:
                        pairs.append((distances[i, j], i, j))

        pairs.sort(key=lambda x: x[0])

        for dist, track_idx, det_idx in pairs:
            if track_idx not in used_tracks and det_idx not in used_detections:
                matched.append((track_ids[track_idx], detections[det_idx]))
                used_tracks.add(track_idx)
                used_detections.add(det_idx)

        unmatched = [d for i, d in enumerate(detections) if i not in used_detections]

        return matched, unmatched

    def _check_line_crossings(self):
        """Check if any tracked objects crossed counting lines."""
        for track in self.tracked_objects.values():
            if track.previous_center is None:
                continue

            for line in self.lines:
                if line.id in track.crossed_lines:
                    continue

                prev_side = track.line_sides.get(line.id)
                current_side = line.point_side(track.current_center)

                track.line_sides[line.id] = current_side

                if prev_side is not None and prev_side != 0 and current_side != 0:
                    if prev_side != current_side:
                        direction = 'in' if current_side > 0 else 'out'

                        self.line_counts[line.id][direction] += 1
                        self.line_counts[line.id]['total'] += 1
                        self.line_class_counts[line.id][track.class_name][direction] += 1

                        track.crossed_lines.add(line.id)

    def _check_zone_occupancy(self):
        """Check zone occupancy for all tracked objects."""
        for poly in self.polygons:
            current_in_zone = set()

            for track in self.tracked_objects.values():
                if poly.contains_point(track.current_center):
                    current_in_zone.add(track.track_id)

                    if poly.id not in track.in_zones:
                        track.in_zones.add(poly.id)
                        self.zone_counts[poly.id]['entered'] += 1
                        self.zone_class_counts[poly.id][track.class_name] += 1
                else:
                    if poly.id in track.in_zones:
                        track.in_zones.remove(poly.id)
                        self.zone_counts[poly.id]['exited'] += 1
                        self.zone_class_counts[poly.id][track.class_name] -= 1

            self.zone_counts[poly.id]['count'] = len(current_in_zone)

    def get_line_counts(self) -> Dict[str, Dict[str, int]]:
        """Get counts for all lines."""
        return dict(self.line_counts)

    def get_zone_counts(self) -> Dict[str, Dict[str, int]]:
        """Get counts for all zones."""
        return dict(self.zone_counts)

    def get_all_counts(self) -> Dict[str, dict]:
        """Get all counts combined."""
        counts = {}
        counts.update(self.line_counts)
        counts.update(self.zone_counts)
        return counts

    def get_count_summary(self) -> str:
        """Get a formatted summary of all counts."""
        lines_summary = []

        for line in self.lines:
            counts = self.line_counts.get(line.id, {})
            lines_summary.append(
                f"📍 {line.name}: In={counts.get('in', 0)}, "
                f"Out={counts.get('out', 0)}, Total={counts.get('total', 0)}"
            )

        for poly in self.polygons:
            counts = self.zone_counts.get(poly.id, {})
            lines_summary.append(
                f"📦 {poly.name}: Current={counts.get('count', 0)}, "
                f"Entered={counts.get('entered', 0)}, Exited={counts.get('exited', 0)}"
            )

        return "\n".join(lines_summary) if lines_summary else "No counting zones defined"

    def get_class_breakdown(self) -> str:
        """Get counts broken down by class."""
        summary = []

        for line in self.lines:
            class_counts = self.line_class_counts.get(line.id, {})
            if class_counts:
                summary.append(f"\n📍 {line.name}:")
                for cls_name, counts in class_counts.items():
                    summary.append(f"  - {cls_name}: In={counts['in']}, Out={counts['out']}")

        for poly in self.polygons:
            class_counts = self.zone_class_counts.get(poly.id, {})
            if class_counts:
                summary.append(f"\n📦 {poly.name}:")
                for cls_name, count in class_counts.items():
                    if count > 0:
                        summary.append(f"  - {cls_name}: {count}")

        return "\n".join(summary) if summary else "No counts yet"

