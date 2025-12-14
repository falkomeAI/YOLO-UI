"""
Stylesheet and theme configuration for the PyQt6 application.
"""

# Dark theme color palette
COLORS = {
    "bg_main": "#0d1117",
    "bg_panel": "#161b22",
    "bg_input": "#21262d",
    "bg_hover": "#30363d",
    "border": "#30363d",
    "text": "#e6edf3",
    "text_secondary": "#8b949e",
    "primary": "#238636",
    "primary_hover": "#2ea043",
    "blue": "#1f6feb",
    "blue_hover": "#388bfd",
    "danger": "#da3633",
    "danger_hover": "#f85149",
    "warning": "#d29922",
}

# Main application stylesheet
STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
}

QFrame {
    background-color: #161b22;
    border-radius: 8px;
}

QLabel {
    color: #e6edf3;
    font-size: 13px;
}

QLabel[class="title"] {
    font-size: 18px;
    font-weight: bold;
}

QLabel[class="heading"] {
    font-size: 14px;
    font-weight: bold;
}

QLabel[class="section"] {
    font-size: 11px;
    font-weight: bold;
    color: #8b949e;
}

QLabel[class="info"] {
    color: #8b949e;
    font-size: 12px;
}

QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #30363d;
}

QPushButton:pressed {
    background-color: #484f58;
}

QPushButton[class="primary"] {
    background-color: #238636;
    border-color: #238636;
}

QPushButton[class="primary"]:hover {
    background-color: #2ea043;
}

QPushButton[class="danger"] {
    background-color: #da3633;
    border-color: #da3633;
}

QPushButton[class="danger"]:hover {
    background-color: #f85149;
}

QPushButton[class="blue"] {
    background-color: #1f6feb;
    border-color: #1f6feb;
}

QPushButton[class="blue"]:hover {
    background-color: #388bfd;
}

QLineEdit {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
}

QLineEdit:focus {
    border-color: #1f6feb;
}

QComboBox {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}

QComboBox:hover {
    background-color: #30363d;
}

QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    selection-background-color: #30363d;
}

QRadioButton {
    color: #e6edf3;
    font-size: 13px;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-size: 13px;
    font-weight: bold;
    color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background-color: #161b22;
    color: #58a6ff;
}

QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #238636;
    border-radius: 4px;
}

QSlider::groove:horizontal {
    background: #21262d;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #1f6feb;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::sub-page:horizontal {
    background: #1f6feb;
    border-radius: 3px;
}

QTextEdit {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-size: 12px;
    font-family: monospace;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: #161b22;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #484f58;
}
"""

