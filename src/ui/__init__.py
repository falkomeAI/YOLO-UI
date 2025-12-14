"""
UI components for Object Detection & Counting application.
"""

from .desktop_app import MainWindow, run_desktop_app
from .widgets import VideoLabel
from .styles import STYLESHEET, COLORS

__all__ = [
    "MainWindow",
    "run_desktop_app",
    "VideoLabel",
    "STYLESHEET",
    "COLORS",
]
