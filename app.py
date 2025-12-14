#!/usr/bin/env python3
"""
Object Detection & Counting Application

A desktop application for real-time object detection and counting
using YOLO models with line crossing and zone counting capabilities.

Usage:
    python app.py
"""

from src.ui import run_desktop_app


def main():
    """Main entry point."""
    run_desktop_app()


if __name__ == "__main__":
    main()
