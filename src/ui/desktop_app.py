"""
Main window for Object Detection & Counting application.
PyQt6-based desktop UI with clean, professional design.
"""

import os
import sys
import cv2
import threading
import time
from typing import Optional, List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSlider, QFrame,
    QProgressBar, QMessageBox, QGroupBox, QSplitter,
    QComboBox, QRadioButton, QLineEdit, QTextEdit, QStatusBar,
    QSpinBox, QSizePolicy, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen, QBrush

from .styles import STYLESHEET
from .widgets import VideoLabel
from ..core import ObjectDetector, draw_detections, DrawingCanvas, ObjectCounter


class BarChartWidget(QWidget):
    """Custom bar chart widget for displaying counts."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}  # {label: value}
        self.max_seen = {}  # Track max value seen for each label
        self.colors = [
            QColor("#238636"),  # Green
            QColor("#1f6feb"),  # Blue
            QColor("#a371f7"),  # Purple
            QColor("#f0883e"),  # Orange
            QColor("#da3633"),  # Red
            QColor("#3fb950"),  # Light Green
            QColor("#58a6ff"),  # Light Blue
        ]
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    def set_data(self, data: dict):
        """Set chart data. data = {label: value}"""
        self.data = data
        # Track maximum values seen
        for label, value in data.items():
            if label not in self.max_seen or value > self.max_seen[label]:
                self.max_seen[label] = value
        self.update()
    
    def reset(self):
        """Reset chart data and max values."""
        self.data = {}
        self.max_seen = {}
        self.update()
    
    def paintEvent(self, event):
        """Paint the bar chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor("#0d1117"))
        
        if not self.data:
            # No data message
            painter.setPen(QColor("#8b949e"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data yet")
            painter.end()
            return
        
        # Calculate dimensions
        margin = 15
        chart_width = self.width() - 2 * margin
        chart_height = self.height() - 2 * margin - 40  # Leave space for labels
        
        # Always use a minimum max value to show scale
        max_val = max(self.data.values()) if self.data.values() else 1
        max_val = max(max_val, 10)  # Minimum scale of 10 to always show bars
        
        num_bars = len(self.data)
        if num_bars == 0:
            painter.end()
            return
            
        bar_width = min(60, (chart_width - (num_bars - 1) * 15) / num_bars)
        total_bars_width = num_bars * bar_width + (num_bars - 1) * 15
        start_x = margin + (chart_width - total_bars_width) / 2
        
        # Draw baseline
        baseline_y = margin + chart_height
        painter.setPen(QPen(QColor("#30363d"), 2))
        painter.drawLine(int(margin), int(baseline_y), int(self.width() - margin), int(baseline_y))
        
        # Draw bars
        for i, (label, value) in enumerate(self.data.items()):
            x = start_x + i * (bar_width + 15)
            
            # Calculate bar height - minimum 5 pixels even for 0
            if value > 0:
                bar_height = max(10, (value / max_val) * chart_height)
            else:
                bar_height = 5  # Small stub for 0 values
            
            y = baseline_y - bar_height
            
            # Bar color
            color = self.colors[i % len(self.colors)]
            
            # Draw bar background (empty portion)
            painter.setBrush(QBrush(QColor("#21262d")))
            painter.setPen(QPen(QColor("#30363d"), 1))
            painter.drawRoundedRect(int(x), int(margin), int(bar_width), int(chart_height), 4, 4)
            
            # Draw filled bar
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(110), 1))
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 4, 4)
            
            # Draw value on top of bar (always visible)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            value_str = str(value)
            value_rect = painter.boundingRect(0, 0, 100, 20, Qt.AlignmentFlag.AlignCenter, value_str)
            painter.drawText(
                int(x + bar_width/2 - value_rect.width()/2),
                int(y - 8),
                value_str
            )
            
            # Draw label below baseline
            painter.setPen(QColor("#e6edf3"))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            # Truncate label if too long
            short_label = label[:10] if len(label) <= 10 else label[:8] + ".."
            label_rect = painter.boundingRect(0, 0, 100, 20, Qt.AlignmentFlag.AlignCenter, short_label)
            painter.drawText(
                int(x + bar_width/2 - label_rect.width()/2),
                int(self.height() - 8),
                short_label
            )
        
        painter.end()


class MainWindow(QMainWindow):
    """Main application window for Object Detection & Counting."""
    
    # Signal for thread-safe UI updates (frame_count, total, percent)
    progress_signal = pyqtSignal(int, int, int)
    
    def __init__(self):
        super().__init__()
        self._init_window()
        self._init_state()
        self._build_ui()
    
    def _init_window(self):
        """Initialize window properties."""
        self.setWindowTitle("Object Detection & Counting")
        self.setMinimumSize(1600, 900)
        self.setGeometry(20, 20, 1700, 950)
    
    def _init_state(self):
        """Initialize application state."""
        self.video_path = ""
        self.cap = None
        self.detector: Optional[ObjectDetector] = None
        self.drawing_canvas = DrawingCanvas()
        self.counter = ObjectCounter()
        self.selected_classes: Optional[List[int]] = None  # None = all classes
        self.processing = False
        self.stop_flag = False
        self.current_frame = None
        
        # Display settings
        self.zoom_level = 100  # percentage
        self.base_display_w = 620
        self.base_display_h = 480
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        
        # Connect progress signal
        self.progress_signal.connect(self._on_progress_update)
        
        # Store frames for display
        self._orig_frame = None
        self._result_frame = None
        
        # Video saving state
        self._should_save_video = False
        self._last_output_path = None
        
        # Auto-load default video after UI is built
        QTimer.singleShot(500, self._auto_load_defaults)
    
    @property
    def display_w(self):
        return int(self.base_display_w * self.zoom_level / 100)
    
    @property
    def display_h(self):
        return int(self.base_display_h * self.zoom_level / 100)
    
    def _build_ui(self):
        """Build the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Top area with panels
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)
        
        self._build_sidebar(content_layout)
        self._build_center(content_layout)
        self._build_results_panel(content_layout)
        
        main_layout.addLayout(content_layout, 1)
        
        # Status bar at bottom
        self._build_status_bar()
    
    def _build_status_bar(self):
        """Build status bar at bottom of window."""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.setStyleSheet("""
            QStatusBar {
                background-color: #161b22;
                color: #e6edf3;
                font-size: 12px;
                padding: 4px;
            }
        """)
        
        # Status message
        self.status_msg = QLabel("Ready")
        self.status_msg.setStyleSheet("color: #7ee787;")
        self.statusBar.addWidget(self.status_msg, 1)
        
        # Drawing info
        self.draw_info = QLabel("Lines: 0 | Polygons: 0")
        self.draw_info.setStyleSheet("color: #8b949e;")
        self.statusBar.addPermanentWidget(self.draw_info)
        
        # Frame counter
        self.frame_label = QLabel("Frame: 0/0")
        self.frame_label.setStyleSheet("color: #ffa500; font-weight: bold;")
        self.statusBar.addPermanentWidget(self.frame_label)
        
        # Video info
        self.video_status = QLabel("No video")
        self.video_status.setStyleSheet("color: #8b949e;")
        self.statusBar.addPermanentWidget(self.video_status)
        
        # Zoom level
        self.zoom_label = QLabel(f"Zoom: {self.zoom_level}%")
        self.zoom_label.setStyleSheet("color: #1f6feb;")
        self.statusBar.addPermanentWidget(self.zoom_label)
    
    # ==================== Sidebar ====================
    
    def _build_sidebar(self, layout):
        """Build left sidebar with settings."""
        sidebar = QFrame()
        sidebar.setFixedWidth(300)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(10, 10, 10, 10)
        s_layout.setSpacing(6)
        
        # Title
        title = QLabel("Object Detection")
        title.setProperty("class", "title")
        s_layout.addWidget(title)
        
        subtitle = QLabel("& Counting")
        subtitle.setStyleSheet("color: #1f6feb; font-size: 14px; font-weight: bold;")
        s_layout.addWidget(subtitle)
        
        s_layout.addSpacing(12)
        
        # Settings groups
        self._build_model_settings(s_layout)
        self._build_class_filter(s_layout)
        self._build_video_input(s_layout)
        
        s_layout.addStretch()
        layout.addWidget(sidebar)
    
    def _build_model_settings(self, layout):
        """Build model settings group."""
        group = QGroupBox("Model Settings")
        g_layout = QVBoxLayout(group)
        g_layout.setSpacing(6)
        
        # Weights file
        g_layout.addWidget(QLabel("Weights File:"))
        
        w_row = QHBoxLayout()
        self.weights_edit = QLineEdit()
        self.weights_edit.setPlaceholderText("yolov8n.pt")
        w_row.addWidget(self.weights_edit)
        
        w_btn = QPushButton("...")
        w_btn.setFixedWidth(40)
        w_btn.clicked.connect(self._browse_weights)
        w_row.addWidget(w_btn)
        g_layout.addLayout(w_row)
        
        # Classes file
        g_layout.addWidget(QLabel("Classes File:"))
        
        c_row = QHBoxLayout()
        self.classes_edit = QLineEdit()
        self.classes_edit.setPlaceholderText("classes.txt (optional)")
        c_row.addWidget(self.classes_edit)
        
        c_btn = QPushButton("...")
        c_btn.setFixedWidth(40)
        c_btn.clicked.connect(self._browse_classes)
        c_row.addWidget(c_btn)
        g_layout.addLayout(c_row)
        
        # Confidence slider
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence:"))
        self.conf_label = QLabel("50%")
        self.conf_label.setStyleSheet("color: #1f6feb; font-weight: bold;")
        conf_row.addWidget(self.conf_label)
        g_layout.addLayout(conf_row)
        
        self.conf_slider = QSlider(Qt.Orientation.Horizontal)
        self.conf_slider.setRange(10, 100)
        self.conf_slider.setValue(50)
        self.conf_slider.valueChanged.connect(self._on_conf_change)
        g_layout.addWidget(self.conf_slider)
        
        # Load button
        self.load_btn = QPushButton("Load Model")
        self.load_btn.setProperty("class", "blue")
        self.load_btn.clicked.connect(self._load_model)
        g_layout.addWidget(self.load_btn)
        
        layout.addWidget(group)
    
    def _build_class_filter(self, layout):
        """Build class filter group with multi-select support."""
        group = QGroupBox()
        group.setStyleSheet("""
            QGroupBox {
                background-color: #161b22;
                border: 2px solid #1f6feb;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 5px;
            }
        """)
        g_layout = QVBoxLayout(group)
        g_layout.setSpacing(6)
        
        # Title
        title_label = QLabel("CLASS FILTER (Multi-Select)")
        title_label.setStyleSheet("""
            color: #58a6ff;
            font-size: 14px;
            font-weight: bold;
            padding: 2px;
        """)
        g_layout.addWidget(title_label)
        
        # Quick filter buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        # Button style template
        btn_style = """
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """
        
        self.all_btn = QPushButton("SELECT ALL")
        self.all_btn.clicked.connect(self._select_all_classes)
        self.all_btn.setStyleSheet(btn_style.format(bg="#238636", hover="#2ea043"))
        btn_row.addWidget(self.all_btn)
        
        self.none_btn = QPushButton("CLEAR")
        self.none_btn.clicked.connect(self._select_no_classes)
        self.none_btn.setStyleSheet(btn_style.format(bg="#da3633", hover="#f85149"))
        btn_row.addWidget(self.none_btn)
        
        self.common_btn = QPushButton("COMMON")
        self.common_btn.clicked.connect(self._select_common_classes)
        self.common_btn.setStyleSheet(btn_style.format(bg="#1f6feb", hover="#388bfd"))
        btn_row.addWidget(self.common_btn)
        
        g_layout.addLayout(btn_row)
        
        # Help label
        help_label = QLabel("✓ Check the classes you want to detect:")
        help_label.setStyleSheet("color: #e6edf3; font-size: 12px; margin-top: 4px;")
        g_layout.addWidget(help_label)
        
        # Class list with checkboxes
        self.class_list = QListWidget()
        self.class_list.setFixedHeight(130)
        self.class_list.setStyleSheet("""
            QListWidget {
                background-color: #0d1117;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QListWidget::item {
                padding: 5px;
                color: #ffffff;
                border-bottom: 1px solid #21262d;
            }
            QListWidget::item:selected {
                background-color: #238636;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #21262d;
            }
        """)
        self.class_list.itemChanged.connect(self._on_class_list_change)
        g_layout.addWidget(self.class_list)
        
        # Selected count label
        self.class_count_label = QLabel("Selected: 0 classes")
        self.class_count_label.setStyleSheet("""
            color: #7ee787;
            font-size: 13px;
            font-weight: bold;
            background-color: #21262d;
            padding: 5px;
            border-radius: 4px;
        """)
        g_layout.addWidget(self.class_count_label)
        
        layout.addWidget(group)
    
    def _build_video_input(self, layout):
        """Build video input group."""
        group = QGroupBox("Video Input")
        g_layout = QVBoxLayout(group)
        
        self.open_btn = QPushButton("Open Video")
        self.open_btn.setProperty("class", "primary")
        self.open_btn.clicked.connect(self._browse_video)
        g_layout.addWidget(self.open_btn)
        
        self.video_info = QLabel("No video loaded")
        self.video_info.setProperty("class", "info")
        self.video_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_info.setWordWrap(True)
        g_layout.addWidget(self.video_info)
        
        layout.addWidget(group)
    
    # ==================== Center Panel ====================
    
    def _build_center(self, layout):
        """Build center area with video displays."""
        center = QFrame()
        center.setStyleSheet("background-color: transparent;")
        c_layout = QVBoxLayout(center)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(8)
        
        self._build_toolbar(c_layout)
        self._build_video_panels(c_layout)
        self._build_controls(c_layout)
        
        layout.addWidget(center, 1)
    
    def _build_toolbar(self, layout):
        """Build drawing toolbar with clear, non-overlapping elements."""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 2px solid #30363d;
                border-radius: 8px;
            }
        """)
        toolbar.setFixedHeight(50)
        
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(10, 5, 10, 5)
        t_layout.setSpacing(6)
        
        # Common button style (fixed width)
        btn_style = """
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """
        
        # Common radio style (fixed width)
        radio_style = """
            QRadioButton {{
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                background-color: {bg};
                padding: 4px 8px;
                border-radius: 4px;
                border: 1px solid {border};
            }}
            QRadioButton:checked {{
                background-color: {checked_bg};
                border-color: {checked_border};
            }}
            QRadioButton::indicator {{ width: 0; height: 0; }}
        """
        
        # DRAW MODE
        draw_label = QLabel("DRAW:")
        draw_label.setFixedWidth(45)
        draw_label.setStyleSheet("color: #ffd700; font-weight: bold; font-size: 11px;")
        t_layout.addWidget(draw_label)
        
        self.none_radio = QRadioButton("OFF")
        self.none_radio.setFixedWidth(45)
        self.none_radio.setChecked(True)
        self.none_radio.setStyleSheet(radio_style.format(
            bg="#484f58", border="#6e7681", checked_bg="#da3633", checked_border="#f85149"
        ))
        self.none_radio.toggled.connect(self._on_draw_mode)
        t_layout.addWidget(self.none_radio)
        
        self.line_radio = QRadioButton("LINE")
        self.line_radio.setFixedWidth(50)
        self.line_radio.setStyleSheet(radio_style.format(
            bg="#484f58", border="#6e7681", checked_bg="#1f6feb", checked_border="#58a6ff"
        ))
        self.line_radio.toggled.connect(self._on_draw_mode)
        t_layout.addWidget(self.line_radio)
        
        self.poly_radio = QRadioButton("ZONE")
        self.poly_radio.setFixedWidth(55)
        self.poly_radio.setStyleSheet(radio_style.format(
            bg="#484f58", border="#6e7681", checked_bg="#8b5cf6", checked_border="#a78bfa"
        ))
        self.poly_radio.toggled.connect(self._on_draw_mode)
        t_layout.addWidget(self.poly_radio)
        
        # Color pickers
        t_layout.addSpacing(5)
        
        # Line color button
        self.line_color_btn = QPushButton()
        self.line_color_btn.setFixedSize(24, 24)
        self.line_color_btn.setToolTip("Line Color")
        self._line_color = (255, 165, 0)  # Orange BGR
        self._update_color_button(self.line_color_btn, self._line_color)
        self.line_color_btn.clicked.connect(lambda: self._pick_color("line"))
        t_layout.addWidget(self.line_color_btn)
        
        line_lbl = QLabel("L")
        line_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        t_layout.addWidget(line_lbl)
        
        # Zone color button
        self.zone_color_btn = QPushButton()
        self.zone_color_btn.setFixedSize(24, 24)
        self.zone_color_btn.setToolTip("Zone Color")
        self._zone_color = (255, 0, 255)  # Magenta BGR
        self._update_color_button(self.zone_color_btn, self._zone_color)
        self.zone_color_btn.clicked.connect(lambda: self._pick_color("zone"))
        t_layout.addWidget(self.zone_color_btn)
        
        zone_lbl = QLabel("Z")
        zone_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        t_layout.addWidget(zone_lbl)
        
        # Separator
        t_layout.addWidget(self._make_separator())
        
        # ACTIONS
        finish_btn = QPushButton("DONE")
        finish_btn.setFixedWidth(55)
        finish_btn.setStyleSheet(btn_style.format(bg="#238636", border="#2ea043", hover="#2ea043"))
        finish_btn.clicked.connect(self._finish_drawing)
        t_layout.addWidget(finish_btn)
        
        cancel_btn = QPushButton("UNDO")
        cancel_btn.setFixedWidth(55)
        cancel_btn.setStyleSheet(btn_style.format(bg="#6e7681", border="#8b949e", hover="#8b949e"))
        cancel_btn.clicked.connect(self._cancel_current_drawing)
        t_layout.addWidget(cancel_btn)
        
        clear_btn = QPushButton("CLEAR")
        clear_btn.setFixedWidth(55)
        clear_btn.setStyleSheet(btn_style.format(bg="#da3633", border="#f85149", hover="#f85149"))
        clear_btn.clicked.connect(self._clear_drawings)
        t_layout.addWidget(clear_btn)
        
        # Separator
        t_layout.addWidget(self._make_separator())
        
        # Show drawings checkbox
        from PyQt6.QtWidgets import QCheckBox
        self.show_draw_check = QCheckBox("SHOW")
        self.show_draw_check.setChecked(True)
        self.show_draw_check.setToolTip("Show/Hide drawings on left video")
        self.show_draw_check.setStyleSheet("""
            QCheckBox {
                color: #7ee787;
                font-size: 11px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:checked {
                background-color: #238636;
                border: 2px solid #2ea043;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #21262d;
                border: 2px solid #30363d;
                border-radius: 3px;
            }
        """)
        self.show_draw_check.stateChanged.connect(self._on_show_draw_changed)
        t_layout.addWidget(self.show_draw_check)
        
        # Separator
        t_layout.addWidget(self._make_separator())
        
        # ZOOM
        zoom_label = QLabel("ZOOM:")
        zoom_label.setFixedWidth(45)
        zoom_label.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 11px;")
        t_layout.addWidget(zoom_label)
        
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(30, 30)
        zoom_out_btn.setStyleSheet(btn_style.format(bg="#1f6feb", border="#58a6ff", hover="#388bfd"))
        zoom_out_btn.clicked.connect(self._zoom_out)
        t_layout.addWidget(zoom_out_btn)
        
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(50, 200)
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setFixedSize(60, 30)
        self.zoom_spin.setStyleSheet("""
            QSpinBox {
                background-color: #0d1117;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid #30363d;
                border-radius: 4px;
            }
        """)
        self.zoom_spin.valueChanged.connect(self._on_zoom_change)
        t_layout.addWidget(self.zoom_spin)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(30, 30)
        zoom_in_btn.setStyleSheet(btn_style.format(bg="#238636", border="#2ea043", hover="#2ea043"))
        zoom_in_btn.clicked.connect(self._zoom_in)
        t_layout.addWidget(zoom_in_btn)
        
        # Separator
        t_layout.addWidget(self._make_separator())
        
        # CONFIG
        config_label = QLabel("CFG:")
        config_label.setFixedWidth(30)
        config_label.setStyleSheet("color: #f0883e; font-weight: bold; font-size: 11px;")
        t_layout.addWidget(config_label)
        
        save_btn = QPushButton("SAVE")
        save_btn.setFixedWidth(50)
        save_btn.setStyleSheet(btn_style.format(bg="#484f58", border="#6e7681", hover="#6e7681"))
        save_btn.clicked.connect(self._save_config)
        t_layout.addWidget(save_btn)
        
        load_btn = QPushButton("LOAD")
        load_btn.setFixedWidth(50)
        load_btn.setStyleSheet(btn_style.format(bg="#484f58", border="#6e7681", hover="#6e7681"))
        load_btn.clicked.connect(self._load_config)
        t_layout.addWidget(load_btn)
        
        t_layout.addStretch()
        
        layout.addWidget(toolbar)
    
    def _build_video_panels(self, layout):
        """Build video display panels."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left video (original)
        left_frame = QFrame()
        l_layout = QVBoxLayout(left_frame)
        l_layout.setContentsMargins(8, 8, 8, 8)
        
        left_title = QLabel("Original Video (Click to draw)")
        left_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        left_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l_layout.addWidget(left_title)
        
        self.left_video = VideoLabel()
        self.left_video.setMinimumSize(600, 450)
        self.left_video.clicked.connect(self._on_video_click)
        l_layout.addWidget(self.left_video, 1)
        
        splitter.addWidget(left_frame)
        
        # Right video (detection result)
        right_frame = QFrame()
        r_layout = QVBoxLayout(right_frame)
        r_layout.setContentsMargins(8, 8, 8, 8)
        
        right_title = QLabel("Detection Result")
        right_title.setStyleSheet("color: #238636; font-size: 14px; font-weight: bold;")
        right_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.addWidget(right_title)
        
        self.right_video = VideoLabel()
        self.right_video.setMinimumSize(600, 450)
        self.right_video.set_border_color("#238636")
        r_layout.addWidget(self.right_video, 1)
        
        splitter.addWidget(right_frame)
        splitter.setSizes([600, 600])
        
        layout.addWidget(splitter, 1)
    
    def _build_controls(self, layout):
        """Build processing controls."""
        ctrl_frame = QFrame()
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)
        
        # Progress bar with percentage label
        progress_row = QHBoxLayout()
        
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #21262d;
                border: none;
                border-radius: 4px;
                height: 20px;
                text-align: center;
                font-weight: bold;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 4px;
            }
        """)
        progress_row.addWidget(self.progress)
        
        self.progress_label = QLabel("0%")
        self.progress_label.setFixedWidth(60)
        self.progress_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #7ee787;")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_row.addWidget(self.progress_label)
        
        ctrl_layout.addLayout(progress_row)
        
        # Save video checkbox
        save_row = QHBoxLayout()
        from PyQt6.QtWidgets import QCheckBox
        self.save_video_check = QCheckBox("Save Output Video")
        self.save_video_check.setStyleSheet("""
            QCheckBox {
                color: #e6edf3;
                font-size: 12px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                background-color: #238636;
                border: 2px solid #2ea043;
                border-radius: 4px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #21262d;
                border: 2px solid #30363d;
                border-radius: 4px;
            }
        """)
        save_row.addWidget(self.save_video_check)
        
        self.output_path_label = QLabel("Output: outputs/")
        self.output_path_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        save_row.addWidget(self.output_path_label)
        save_row.addStretch()
        ctrl_layout.addLayout(save_row)
        
        # Main action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        self.process_btn = QPushButton("▶ Process")
        self.process_btn.setProperty("class", "primary")
        self.process_btn.setFixedSize(110, 36)
        self.process_btn.clicked.connect(self._start_processing)
        btn_row.addWidget(self.process_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setProperty("class", "danger")
        self.stop_btn.setFixedSize(90, 36)
        self.stop_btn.clicked.connect(self._stop_processing)
        btn_row.addWidget(self.stop_btn)
        
        # Screenshot button
        self.screenshot_btn = QPushButton("📷")
        self.screenshot_btn.setToolTip("Save current frame (Ctrl+S)")
        self.screenshot_btn.setFixedSize(40, 36)
        self.screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb;
                color: white;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #388bfd; }
        """)
        self.screenshot_btn.clicked.connect(self._save_screenshot)
        btn_row.addWidget(self.screenshot_btn)
        
        # Export stats button
        self.export_btn = QPushButton("📊")
        self.export_btn.setToolTip("Export statistics to CSV")
        self.export_btn.setFixedSize(40, 36)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #a78bfa; }
        """)
        self.export_btn.clicked.connect(self._export_stats)
        btn_row.addWidget(self.export_btn)
        
        # Reset counters button
        self.reset_counts_btn = QPushButton("🔄")
        self.reset_counts_btn.setToolTip("Reset all counters")
        self.reset_counts_btn.setFixedSize(40, 36)
        self.reset_counts_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0883e;
                color: white;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #ffa657; }
        """)
        self.reset_counts_btn.clicked.connect(self._reset_counters)
        btn_row.addWidget(self.reset_counts_btn)
        
        btn_row.addStretch()
        ctrl_layout.addLayout(btn_row)
        
        # Video seek slider
        seek_row = QHBoxLayout()
        
        self.frame_label = QLabel("0 / 0")
        self.frame_label.setFixedWidth(80)
        self.frame_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        seek_row.addWidget(self.frame_label)
        
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setValue(0)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #21262d;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #58a6ff;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #238636;
                border-radius: 3px;
            }
        """)
        self.seek_slider.sliderMoved.connect(self._seek_video)
        seek_row.addWidget(self.seek_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(90)
        self.time_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        seek_row.addWidget(self.time_label)
        
        ctrl_layout.addLayout(seek_row)
        
        layout.addWidget(ctrl_frame)
    
    # ==================== Results Panel ====================
    
    def _build_results_panel(self, layout):
        """Build right results panel with graphical stats."""
        panel = QFrame()
        panel.setFixedWidth(300)
        p_layout = QVBoxLayout(panel)
        p_layout.setContentsMargins(10, 10, 10, 10)
        p_layout.setSpacing(10)
        
        title = QLabel("Statistics")
        title.setProperty("class", "title")
        p_layout.addWidget(title)
        
        # Bar Chart for Counts
        chart_grp = QGroupBox("Live Counts (Graph)")
        chart_layout = QVBoxLayout(chart_grp)
        
        self.counts_chart = BarChartWidget()
        self.counts_chart.setMinimumHeight(180)
        chart_layout.addWidget(self.counts_chart)
        
        p_layout.addWidget(chart_grp)
        
        # Detailed counts text
        detail_grp = QGroupBox("Details")
        detail_layout = QVBoxLayout(detail_grp)
        
        self.counts_text = QTextEdit()
        self.counts_text.setReadOnly(True)
        self.counts_text.setFixedHeight(100)
        self.counts_text.setText("Process video to see counts")
        self.counts_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        detail_layout.addWidget(self.counts_text)
        
        p_layout.addWidget(detail_grp)
        
        # Drawings info
        draw_grp = QGroupBox("Drawings")
        dr_layout = QVBoxLayout(draw_grp)
        
        self.drawings_text = QTextEdit()
        self.drawings_text.setReadOnly(True)
        self.drawings_text.setFixedHeight(80)
        self.drawings_text.setText("Lines: 0\nPolygons: 0")
        self.drawings_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #7ee787;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        dr_layout.addWidget(self.drawings_text)
        
        p_layout.addWidget(draw_grp)
        
        p_layout.addStretch()
        layout.addWidget(panel)
    
    # ==================== Event Handlers ====================
    
    def _on_conf_change(self, value):
        """Handle confidence slider change."""
        self.conf_label.setText(f"{value}%")
        # Update detector confidence
        if self.detector:
            self.detector.update_confidence(value / 100.0)
    
    def _on_class_list_change(self, item):
        """Handle class checkbox change."""
        self._update_selected_classes()
    
    def _update_selected_classes(self):
        """Update selected_classes based on checked items."""
        checked_ids = []
        all_checked = True
        
        for i in range(self.class_list.count()):
            item = self.class_list.item(i)
            class_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                checked_ids.append(class_id)
            else:
                all_checked = False
        
        # If all are checked, use None (all classes)
        if all_checked:
            self.selected_classes = None
        elif len(checked_ids) == 0:
            self.selected_classes = []  # Nothing selected
        else:
            self.selected_classes = checked_ids
        
        self._update_class_count()
    
    def _update_class_count(self):
        """Update the class count label."""
        count = 0
        for i in range(self.class_list.count()):
            if self.class_list.item(i).checkState() == Qt.CheckState.Checked:
                count += 1
        
        total = self.class_list.count()
        if count == total and total > 0:
            self.class_count_label.setText(f"Selected: All {total} classes")
            self.class_count_label.setStyleSheet("color: #7ee787; font-size: 11px;")
        elif count == 0:
            self.class_count_label.setText("Selected: None (nothing will be detected)")
            self.class_count_label.setStyleSheet("color: #f85149; font-size: 11px;")
        else:
            self.class_count_label.setText(f"Selected: {count}/{total} classes")
            self.class_count_label.setStyleSheet("color: #58a6ff; font-size: 11px;")
    
    def _select_all_classes(self):
        """Select all classes."""
        self.class_list.blockSignals(True)
        for i in range(self.class_list.count()):
            self.class_list.item(i).setCheckState(Qt.CheckState.Checked)
        self.class_list.blockSignals(False)
        self._update_selected_classes()
        self.status_msg.setText("Filter: All classes selected")
        self.status_msg.setStyleSheet("color: #7ee787;")
    
    def _select_no_classes(self):
        """Deselect all classes."""
        self.class_list.blockSignals(True)
        for i in range(self.class_list.count()):
            self.class_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.class_list.blockSignals(False)
        self._update_selected_classes()
        self.status_msg.setText("Filter: No classes selected")
        self.status_msg.setStyleSheet("color: #f85149;")
    
    def _select_common_classes(self):
        """Select common classes (person, car, truck, bus, motorcycle, bicycle)."""
        common = ['person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'dog', 'cat']
        self.class_list.blockSignals(True)
        for i in range(self.class_list.count()):
            item = self.class_list.item(i)
            if item.text().lower() in common:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.class_list.blockSignals(False)
        self._update_selected_classes()
        self.status_msg.setText("Filter: Common classes selected")
        self.status_msg.setStyleSheet("color: #58a6ff;")
    
    def _on_draw_mode(self, checked=True):
        """Handle draw mode change - preserves existing drawings."""
        # Only process when a button is checked (not unchecked)
        if not checked:
            return
        
        if self.line_radio.isChecked():
            self.drawing_canvas.set_mode("line")
            self.status_msg.setText("Line mode: Click 2 points")
            self.status_msg.setStyleSheet("color: #58a6ff;")
        elif self.poly_radio.isChecked():
            self.drawing_canvas.set_mode("polygon")
            self.status_msg.setText("Zone mode: Click 3+ points, click first to close")
            self.status_msg.setStyleSheet("color: #a78bfa;")
        else:
            self.drawing_canvas.set_mode(None)
            self.status_msg.setText("Ready")
            self.status_msg.setStyleSheet("color: #7ee787;")
        
        # Redraw to show current drawings
        if self.current_frame is not None:
            self._show_frame()
    
    def _on_show_draw_changed(self, state):
        """Handle show/hide drawings checkbox change."""
        if self.current_frame is not None:
            self._show_frame()
        self.status_msg.setText("Drawings: " + ("Visible" if state else "Hidden"))
        self.status_msg.setStyleSheet("color: #7ee787;" if state else "color: #ffa500;")
    
    def _on_timer(self):
        """Timer callback."""
        pass
    
    def _auto_load_defaults(self):
        """Auto-load default video and model on startup."""
        import os
        
        # Default paths
        default_video = "highway_cars.mp4"  # Highway car video for demo
        default_weights = "yolov8n.pt"
        
        # Check if default video exists
        if os.path.exists(default_video):
            print(f"Auto-loading video: {default_video}")
            self._load_video(default_video)
        
        # Check if default weights exists
        if os.path.exists(default_weights):
            print(f"Auto-loading model: {default_weights}")
            self.weights_edit.setText(default_weights)
            self._load_model()
        
        # Set Line mode as default for easier drawing
        self.line_radio.setChecked(True)
        self.drawing_canvas.set_mode("line")
        self.status_msg.setText("Ready - Line mode active")
        self.status_msg.setStyleSheet("color: #7ee787;")
    
    def _on_zoom_change(self, value):
        """Handle zoom level change."""
        self.zoom_level = value
        self.zoom_label.setText(f"Zoom: {value}%")
        if self.current_frame is not None:
            self._show_frame()
    
    def _make_separator(self):
        """Create a visual separator for the toolbar."""
        sep = QLabel("|")
        sep.setFixedWidth(15)
        sep.setStyleSheet("color: #484f58; font-size: 16px; background: transparent;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return sep
    
    def _update_color_button(self, btn, bgr_color):
        """Update color button with the given BGR color."""
        r, g, b = bgr_color[2], bgr_color[1], bgr_color[0]  # BGR to RGB
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid #ffffff;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #58a6ff;
            }}
        """)
    
    def _pick_color(self, color_type):
        """Open color picker dialog."""
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        
        if color_type == "line":
            current = self._line_color
            title = "Select Line Color"
        else:
            current = self._zone_color
            title = "Select Zone Color"
        
        # BGR to RGB for dialog
        initial = QColor(current[2], current[1], current[0])
        
        color = QColorDialog.getColor(initial, self, title)
        if color.isValid():
            # RGB to BGR for OpenCV
            bgr = (color.blue(), color.green(), color.red())
            
            if color_type == "line":
                self._line_color = bgr
                self._update_color_button(self.line_color_btn, bgr)
                self.drawing_canvas.set_line_color(bgr)
            else:
                self._zone_color = bgr
                self._update_color_button(self.zone_color_btn, bgr)
                self.drawing_canvas.set_zone_color(bgr)
            
            self.status_msg.setText(f"{color_type.title()} color updated")
            self.status_msg.setStyleSheet("color: #7ee787;")
    
    def _zoom_in(self):
        """Increase zoom level."""
        self.zoom_spin.setValue(min(200, self.zoom_level + 10))
    
    def _zoom_out(self):
        """Decrease zoom level."""
        self.zoom_spin.setValue(max(50, self.zoom_level - 10))
    
    def _browse_weights(self):
        """Browse for weights file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Weights", "", "PyTorch Model (*.pt)"
        )
        if path:
            self.weights_edit.setText(path)
    
    def _browse_classes(self):
        """Browse for classes file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Classes", "", "Text File (*.txt)"
        )
        if path:
            self.classes_edit.setText(path)
    
    def _browse_video(self):
        """Browse for video file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Video (*.mp4 *.avi *.mov *.mkv *.webm)"
        )
        if path:
            self._load_video(path)
    
    def _load_video(self, path: str):
        """Load a video file."""
        if self.cap:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", "Cannot open video")
            return
        
        self.video_path = path
        
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total / fps
        
        self.video_info.setText(f"{w}x{h}\n{fps:.0f}fps | {total} frames\n{duration:.1f}s")
        self.video_status.setText(f"{os.path.basename(path)} | {w}x{h}")
        self.status_msg.setText(f"Loaded: {os.path.basename(path)}")
        self.status_msg.setStyleSheet("color: #7ee787;")
        
        # Setup seek slider
        self.seek_slider.setMaximum(max(1, total - 1))
        self.seek_slider.setValue(0)
        self._update_time_display()
        
        # Update drawing canvas dimensions
        self.drawing_canvas.update_dimensions(w, h)
        
        self._show_frame(0)
    
    def _load_model(self):
        """Load the YOLO model."""
        weights = self.weights_edit.text().strip() or "yolov8n.pt"
        classes = self.classes_edit.text().strip() or None
        conf = self.conf_slider.value() / 100.0
        
        self.status_msg.setText("Loading model...")
        self.status_msg.setStyleSheet("color: #ffa500;")
        QApplication.processEvents()
        
        try:
            self.detector = ObjectDetector(weights, classes, conf)
            
            # Populate class list with checkboxes
            self.class_list.clear()
            self.class_list.blockSignals(True)  # Prevent multiple signals
            
            num_classes = len(self.detector.class_names)
            for class_id, class_name in self.detector.class_names.items():
                item = QListWidgetItem(class_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)  # All selected by default
                item.setData(Qt.ItemDataRole.UserRole, class_id)  # Store class ID
                self.class_list.addItem(item)
            
            self.class_list.blockSignals(False)
            
            # Default to all classes (None = all)
            self.selected_classes = None
            self._update_class_count()
            
            self.status_msg.setText(f"Model loaded: {num_classes} classes")
            self.status_msg.setStyleSheet("color: #7ee787;")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.status_msg.setText("Model load failed")
            self.status_msg.setStyleSheet("color: #f85149;")
    
    def _show_frame(self, n: int = None):
        """Show a video frame with drawings."""
        if not self.cap:
            return
        
        if n is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            
            # Draw existing lines and polygons on frame if checkbox is checked
            if self.show_draw_check.isChecked():
                display = self.drawing_canvas.draw_on_frame(frame.copy())
            else:
                display = frame.copy()
            self._update_video_label(self.left_video, display)
            
            # Also show in right panel (will be replaced during processing)
            self._update_video_label(self.right_video, frame.copy())
    
    def _update_video_label(self, label: VideoLabel, frame):
        """Update a video label with a frame."""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame_rgb.shape
        
        # Apply zoom
        new_w = int(w * self.zoom_level / 100)
        new_h = int(h * self.zoom_level / 100)
        
        # Limit to reasonable size
        max_w, max_h = 800, 600
        scale = min(max_w / new_w, max_h / new_h, 1.0)
        new_w = int(new_w * scale)
        new_h = int(new_h * scale)
        
        frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
        
        qimg = QImage(
            frame_resized.data, new_w, new_h, 
            new_w * 3, QImage.Format.Format_RGB888
        )
        label.setPixmap(QPixmap.fromImage(qimg))
        
        # Store display size for coordinate conversion
        self._current_display_w = new_w
        self._current_display_h = new_h
    
    def _on_video_click(self, x: int, y: int):
        """Handle click on video label."""
        if self.current_frame is None:
            self.status_msg.setText("Load a video first!")
            self.status_msg.setStyleSheet("color: #f85149;")
            return
        
        if self.drawing_canvas.drawing_mode == "none":
            self.status_msg.setText("Select Line or Polygon mode first!")
            self.status_msg.setStyleSheet("color: #f85149;")
            return
        
        # Get frame dimensions
        frame_h, frame_w = self.current_frame.shape[:2]
        
        # Get current display dimensions
        display_w = getattr(self, '_current_display_w', frame_w)
        display_h = getattr(self, '_current_display_h', frame_h)
        
        # Get label dimensions
        label_w = self.left_video.width()
        label_h = self.left_video.height()
        
        # Calculate offset (image is centered in label)
        offset_x = (label_w - display_w) // 2
        offset_y = (label_h - display_h) // 2
        
        # Convert to frame coordinates
        rel_x = x - offset_x
        rel_y = y - offset_y
        
        if rel_x < 0 or rel_y < 0 or rel_x >= display_w or rel_y >= display_h:
            return
        
        frame_x = int(rel_x * frame_w / display_w)
        frame_y = int(rel_y * frame_h / display_h)
        
        # Add point to drawing canvas
        self.drawing_canvas.add_point(frame_x, frame_y)
        
        # Update status with helpful message
        mode = self.drawing_canvas.drawing_mode
        pts = len(self.drawing_canvas.current_points)
        
        if mode == "polygon":
            if pts < 3:
                self.status_msg.setText(f"Polygon: {pts} points (need 3+ to close)")
            else:
                self.status_msg.setText(f"Polygon: {pts} points - Click near first point to close OR Finish")
        else:
            self.status_msg.setText(f"{mode.capitalize()}: {pts} point(s)")
        self.status_msg.setStyleSheet("color: #ffa500;")
        
        # Redraw frame with new point
        self._show_frame()
        self._update_drawings_text()
    
    def _finish_drawing(self):
        """Finish current drawing."""
        result = self.drawing_canvas.finish_current()
        if result:
            self.status_msg.setText(f"Created: {result}")
            self.status_msg.setStyleSheet("color: #7ee787;")
        else:
            self.status_msg.setText("Need more points to finish")
            self.status_msg.setStyleSheet("color: #f85149;")
        
        if self.current_frame is not None:
            self._show_frame()
        self._update_drawings_text()
    
    def _cancel_current_drawing(self):
        """Cancel current drawing (clear points being drawn but keep mode)."""
        # Remember current mode
        current_mode = self.drawing_canvas.drawing_mode
        
        # Clear only current points, not completed drawings
        self.drawing_canvas.current_points = []
        
        # Keep the drawing mode active (don't set to "none")
        self.drawing_canvas.drawing_mode = current_mode
        
        self.status_msg.setText(f"Points cleared - continue drawing {current_mode}")
        self.status_msg.setStyleSheet("color: #ffa500;")
        
        if self.current_frame is not None:
            self._show_frame()
        self._update_drawings_text()
    
    def _clear_drawings(self):
        """Clear all drawings."""
        
        # Clear all drawings but keep mode
        self.drawing_canvas.lines = []
        self.drawing_canvas.polygons = []
        self.drawing_canvas.current_points = []
        self.drawing_canvas.line_counter = 0
        self.drawing_canvas.polygon_counter = 0
        
        # Re-enable drawing mode based on radio button
        if self.line_radio.isChecked():
            self.drawing_canvas.drawing_mode = "line"
        elif self.poly_radio.isChecked():
            self.drawing_canvas.drawing_mode = "polygon"
        else:
            self.drawing_canvas.drawing_mode = "none"
        
        
        self.status_msg.setText("All drawings cleared - ready to draw!")
        self.status_msg.setStyleSheet("color: #7ee787;")
        
        # Update video display
        if self.current_frame is not None:
            self._show_frame()
        
        # Update info text
        self._update_drawings_text()
    
    def _save_config(self):
        """Save drawing configuration."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", "drawing_config.json", "JSON (*.json)"
        )
        if path:
            self.drawing_canvas.save_config(path)
            self.status_msg.setText(f"Saved: {os.path.basename(path)}")
            self.status_msg.setStyleSheet("color: #7ee787;")
    
    def _load_config(self):
        """Load drawing configuration."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", "", "JSON (*.json)"
        )
        if path:
            self.drawing_canvas.load_config(path)
            self.status_msg.setText(f"Loaded: {os.path.basename(path)}")
            self.status_msg.setStyleSheet("color: #7ee787;")
            
            if self.current_frame is not None:
                self._show_frame()
            self._update_drawings_text()
    
    def _update_drawings_text(self):
        """Update drawings info display."""
        lines = len(self.drawing_canvas.lines)
        polys = len(self.drawing_canvas.polygons)
        self.drawings_text.setText(f"Lines: {lines}\nPolygons: {polys}")
        self.draw_info.setText(f"Lines: {lines} | Polygons: {polys}")
    
    def _start_processing(self):
        """Start video processing."""
        import sys
        sys.stdout.flush()
        
        if not self.cap:
            QMessageBox.warning(self, "Warning", "Load a video first!")
            return
        if not self.detector:
            QMessageBox.warning(self, "Warning", "Load a model first!")
            return
        
        self.processing = True
        self.stop_flag = False
        
        # Capture save setting before thread starts (UI access must be in main thread)
        self._should_save_video = self.save_video_check.isChecked()
        
        # Reset video to start
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        self.counter.reset()
        self.progress.setValue(0)
        self.progress_label.setText("0%")
        
        if self._should_save_video:
            self.status_msg.setText("Processing & Saving...")
        else:
            self.status_msg.setText("Processing...")
        self.status_msg.setStyleSheet("color: #ffa500;")
        
        # Start processing thread
        t = threading.Thread(target=self._process_video, daemon=True)
        t.start()
    
    def _stop_processing(self):
        """Stop video processing."""
        self.stop_flag = True
        self.processing = False
        
        # Wait a bit for thread to stop
        import time
        time.sleep(0.1)
        
        # Reset video to first frame
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame
                self._show_frame()
        
        # Reset progress
        self.progress.setValue(0)
        self.progress_label.setText("0%")
        self.frame_label.setText("Frame: 0/0")
        
        # Update status
        self.status_msg.setText("Stopped - Ready to draw")
        self.status_msg.setStyleSheet("color: #ffa500;")
        
        # Re-enable drawing mode
        if self.line_radio.isChecked():
            self.drawing_canvas.set_mode("line")
        elif self.poly_radio.isChecked():
            self.drawing_canvas.set_mode("polygon")
    
    def _seek_video(self, value):
        """Seek to a specific frame in the video."""
        if not self.cap or self.processing:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, value)
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            self._show_frame()
            self._update_time_display()
    
    def _update_time_display(self):
        """Update time and frame display labels."""
        if not self.cap:
            return
        pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        
        self.frame_label.setText(f"{pos} / {total}")
        
        current_sec = pos / fps
        total_sec = total / fps
        self.time_label.setText(
            f"{int(current_sec//60):02d}:{int(current_sec%60):02d} / "
            f"{int(total_sec//60):02d}:{int(total_sec%60):02d}"
        )
    
    def _save_screenshot(self):
        """Save current frame as screenshot."""
        import os
        from datetime import datetime
        
        frame = self._result_frame if self._result_frame is not None else self.current_frame
        if frame is None:
            QMessageBox.warning(self, "Warning", "No frame to save!")
            return
        
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"outputs/screenshot_{timestamp}.png"
        
        cv2.imwrite(path, frame)
        self.status_msg.setText(f"Screenshot saved: {path}")
        self.status_msg.setStyleSheet("color: #7ee787;")
    
    def _export_stats(self):
        """Export counting statistics to CSV."""
        import os
        from datetime import datetime
        
        counts = self.counter.get_all_counts()
        if not counts:
            QMessageBox.warning(self, "Warning", "No statistics to export!")
            return
        
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"outputs/stats_{timestamp}.csv"
        
        with open(path, 'w') as f:
            f.write("Type,ID,Count\n")
            for key, value in counts.items():
                if key.startswith("line_"):
                    f.write(f"Line,{key},{value}\n")
                elif key.startswith("zone_"):
                    f.write(f"Zone,{key},{value}\n")
        
        self.status_msg.setText(f"Stats exported: {path}")
        self.status_msg.setStyleSheet("color: #7ee787;")
        QMessageBox.information(self, "Exported", f"Statistics saved to:\n{path}")
    
    def _reset_counters(self):
        """Reset all counting statistics."""
        reply = QMessageBox.question(
            self, "Reset Counters",
            "Reset all counting statistics?\n(Drawings will be preserved)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.counter.reset()
            self._update_counts({})
            self.status_msg.setText("Counters reset")
            self.status_msg.setStyleSheet("color: #ffa500;")
    
    def _process_video(self):
        """Process video frames (runs in background thread)."""
        import sys
        import os
        from datetime import datetime
        sys.stdout.flush()
        
        video_writer = None
        self._last_output_path = None
        
        try:
            total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total <= 0:
                total = 1
            frame_count = 0
            
            # Setup video writer if saving is enabled
            if self._should_save_video:
                fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                os.makedirs("outputs", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self._last_output_path = os.path.abspath(f"outputs/detection_{timestamp}.mp4")
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(self._last_output_path, fourcc, fps, (width, height))
                
                if not video_writer.isOpened():
                    print(f"ERROR: Could not open video writer for {self._last_output_path}")
                else:
                    print(f"Video writer opened: {self._last_output_path}")
            
            while self.processing and not self.stop_flag:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                self.current_frame = frame
                frame_count += 1
                
                # Calculate progress
                percent = int((frame_count / total) * 100)
                
                # Detect objects
                detections = self.detector.detect(frame, self.selected_classes)
                
                # Update counts
                self.counter.update(
                    detections,
                    self.drawing_canvas.lines,
                    self.drawing_canvas.polygons
                )
                
                # Draw results (pass None for color_map, not class_names)
                result = draw_detections(frame, detections, None)
                
                # Draw lines/polygons with counts
                counts = self.counter.get_all_counts()
                result = self.drawing_canvas.draw_on_frame(result, show_labels=True, counts=counts)
                
                # Write frame to video if saving
                if video_writer is not None:
                    video_writer.write(result)
                
                # Store frames for display and emit signal
                self._orig_frame = frame.copy()
                self._result_frame = result.copy()
                self.progress_signal.emit(frame_count, total, percent)
                
                time.sleep(0.01)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            if video_writer is not None:
                video_writer.release()
                print(f"Video saved successfully: {self._last_output_path}")
        
        self.processing = False
        QTimer.singleShot(0, lambda: self._on_processing_done())
    
    def _on_progress_update(self, frame_count, total, percent):
        """Handle progress update signal (runs in main thread)."""
        # Update progress bar and label
        self.progress.setValue(percent)
        self.progress_label.setText(f"{percent}%")
        
        if percent < 100:
            self.progress_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #7ee787;")
        else:
            self.progress_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #58a6ff;")
        
        # Update frame counter
        self.frame_label.setText(f"{frame_count} / {total}")
        
        # Update seek slider
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(frame_count)
        self.seek_slider.blockSignals(False)
        
        # Update time display
        if self.cap:
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            current_sec = frame_count / fps
            total_sec = total / fps
            self.time_label.setText(
                f"{int(current_sec//60):02d}:{int(current_sec%60):02d} / "
                f"{int(total_sec//60):02d}:{int(total_sec%60):02d}"
            )
        
        # Update status message
        self.status_msg.setText(f"Processing... {percent}%")
        self.status_msg.setStyleSheet("color: #ffa500;")
        
        # Update video displays with counts
        counts = self.counter.get_all_counts()
        if self._orig_frame is not None:
            # Show drawings only if checkbox is checked
            if self.show_draw_check.isChecked():
                display_orig = self.drawing_canvas.draw_on_frame(self._orig_frame.copy(), counts=counts)
            else:
                display_orig = self._orig_frame.copy()
            self._update_video_label(self.left_video, display_orig)
        
        if self._result_frame is not None:
            self._update_video_label(self.right_video, self._result_frame)
        
        self._update_counts()
    
    def _on_processing_done(self):
        """Called when processing is complete."""
        if hasattr(self, '_last_output_path') and self._last_output_path:
            self.status_msg.setText(f"Saved: {self._last_output_path}")
            self.output_path_label.setText(f"Output: {self._last_output_path}")
            QMessageBox.information(self, "Video Saved", f"Output saved to:\n{self._last_output_path}")
        else:
            self.status_msg.setText("Processing complete!")
        self.status_msg.setStyleSheet("color: #7ee787;")
    
    def _update_ui(self, orig, result, pos, total):
        """Update UI with processing results (runs in main thread)."""
        try:
            # Draw with counts
            counts = self.counter.get_all_counts()
            display_orig = self.drawing_canvas.draw_on_frame(orig.copy(), counts=counts)
            self._update_video_label(self.left_video, display_orig)
            self._update_video_label(self.right_video, result)
            
            # Calculate percentage
            if total > 0:
                percent = min(100, int((pos / total) * 100))
            else:
                percent = 0
            
            # Update progress bar and label
            self.progress.setValue(percent)
            self.progress_label.setText(f"{percent}%")
            self.progress_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {'#7ee787' if percent < 100 else '#58a6ff'};")
            
            # Update frame counter in status bar
            self.frame_label.setText(f"Frame: {pos}/{total}")
            
            # Update status message
            self.status_msg.setText(f"Processing... {percent}%")
            self.status_msg.setStyleSheet("color: #ffa500;")
            
            self._update_counts()
            
            # Force UI refresh
            QApplication.processEvents()
        except Exception:
            pass  # Silently handle UI update errors
    
    def _update_counts(self):
        """Update counts display with chart and text."""
        # Get counts for chart
        chart_data = {}
        
        # Line counts (in/out/total)
        for line in self.drawing_canvas.lines:
            lc = self.counter.line_counts.get(line.id, {})
            total = lc.get('total', 0)
            chart_data[line.name] = total
        
        # Zone counts (current occupancy)
        for poly in self.drawing_canvas.polygons:
            zc = self.counter.zone_counts.get(poly.id, {})
            count = zc.get('count', 0)
            chart_data[poly.name] = count
        
        # Update bar chart
        self.counts_chart.set_data(chart_data)
        
        # Update detailed text
        lines_text = []
        for line in self.drawing_canvas.lines:
            lc = self.counter.line_counts.get(line.id, {})
            lines_text.append(f"{line.name}:")
            lines_text.append(f"  In: {lc.get('in', 0)}  Out: {lc.get('out', 0)}")
            lines_text.append(f"  Total: {lc.get('total', 0)}")
        
        for poly in self.drawing_canvas.polygons:
            zc = self.counter.zone_counts.get(poly.id, {})
            lines_text.append(f"{poly.name}:")
            lines_text.append(f"  Current: {zc.get('count', 0)}")
            lines_text.append(f"  Entered: {zc.get('entered', 0)}")
        
        if lines_text:
            self.counts_text.setText("\n".join(lines_text))
        else:
            self.counts_text.setText("Draw lines/zones and process")
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        from PyQt6.QtCore import Qt
        
        key = event.key()
        modifiers = event.modifiers()
        
        # Ctrl+S = Screenshot
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_S:
            self._save_screenshot()
        # Ctrl+E = Export stats
        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_E:
            self._export_stats()
        # Space = Start/Stop processing
        elif key == Qt.Key.Key_Space:
            if self.processing:
                self._stop_processing()
            else:
                self._start_processing()
        # Escape = Stop processing
        elif key == Qt.Key.Key_Escape:
            self._stop_processing()
        # R = Reset counters
        elif key == Qt.Key.Key_R and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._reset_counters()
        # Left/Right arrows = Seek video
        elif key == Qt.Key.Key_Left and not self.processing:
            if self.cap:
                pos = max(0, int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 30)
                self._seek_video(pos)
        elif key == Qt.Key.Key_Right and not self.processing:
            if self.cap:
                total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                pos = min(total - 1, int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) + 30)
                self._seek_video(pos)
        # + / - = Zoom
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle window close."""
        if self.cap:
            self.cap.release()
        self.stop_flag = True
        event.accept()


def run_desktop_app():
    """Run the PyQt6 application."""
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    
    # Set application font
    font = QFont("Cantarell", 11)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
