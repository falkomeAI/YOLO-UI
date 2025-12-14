"""
Custom widgets for the Object Detection & Counting application.
"""

from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal


class VideoLabel(QLabel):
    """
    Custom label for displaying video frames with click detection.
    Emits clicked signal with x, y coordinates when clicked.
    """
    
    clicked = pyqtSignal(int, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(580, 420)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "background-color: #0d1117; "
            "border: 2px solid #30363d; "
            "border-radius: 8px;"
        )
        self.setText("No video loaded")
    
    def mousePressEvent(self, event):
        """Handle mouse click and emit coordinates."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.pos().x(), event.pos().y())
    
    def set_border_color(self, color: str):
        """Set the border color of the video label."""
        self.setStyleSheet(
            f"background-color: #0d1117; "
            f"border: 2px solid {color}; "
            f"border-radius: 8px;"
        )

