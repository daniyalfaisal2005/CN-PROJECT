#!/usr/bin/env python3
"""
Unified Logger GUI - Displays all system logs in a centralized window.
Integrates with the logging system to show real-time updates.
"""
import sys
import os
import logging
from datetime import datetime
from collections import deque
import threading

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat

from network.logging_util import add_log_callback, setup_logging


class LogSignalEmitter(QObject):
    """Emits signals for log updates (thread-safe)."""
    log_received = pyqtSignal(str, str, str)  # level, logger_name, message


class UnifiedLoggerGUI(QMainWindow):
    """Unified logger GUI window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📋 Unified Logger - P2P Election System")
        self.setGeometry(100, 100, 1200, 700)
        
        self.log_buffer = deque(maxlen=5000)  # Keep last 5000 logs
        self.log_emitter = LogSignalEmitter()
        self.log_emitter.log_received.connect(self.on_log_received)
        
        # Setup UI
        self.setup_ui()
        
        # Register callback with logging system
        add_log_callback(self.on_log_event)
        
        # Apply styling
        self.apply_stylesheet()
        
        self.show()
    
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        # Log level filter
        level_label = QLabel("Filter Level:")
        self.level_filter = QComboBox()
        self.level_filter.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.currentTextChanged.connect(self.update_display)
        
        header_layout.addWidget(level_label)
        header_layout.addWidget(self.level_filter)
        header_layout.addStretch()
        
        # Clear button
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        header_layout.addWidget(clear_btn)
        
        # Auto-scroll checkbox
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        header_layout.addWidget(self.auto_scroll)
        
        layout.addLayout(header_layout)
        
        # Log display area
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas" if sys.platform == "win32" else "Courier", 9))
        layout.addWidget(self.log_display)
        
        # Status bar
        self.statusBar().showMessage("Logger ready - waiting for logs...")
    
    def apply_stylesheet(self):
        """Apply dark theme stylesheet."""
        stylesheet = """
        QMainWindow {
            background-color: #1e1e1e;
        }
        QTextEdit {
            background-color: #252526;
            color: #d4d4d4;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 5px;
        }
        QComboBox {
            background-color: #3c3c3c;
            color: #d4d4d4;
            border: 1px solid #3e3e42;
            padding: 5px;
            border-radius: 4px;
        }
        QPushButton {
            background-color: #0e639c;
            color: white;
            border: none;
            padding: 6px 15px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1177bb;
        }
        QPushButton:pressed {
            background-color: #094771;
        }
        QCheckBox {
            color: #d4d4d4;
        }
        QLabel {
            color: #d4d4d4;
        }
        """
        self.setStyleSheet(stylesheet)
    
    def on_log_event(self, level: str, logger_name: str, message: str):
        """Called when a log event occurs (from logging system)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'logger': logger_name,
            'message': message
        }
        self.log_buffer.append(log_entry)
        
        # Emit signal to update GUI (thread-safe)
        self.log_emitter.log_received.emit(level, logger_name, f"[{timestamp}] {logger_name}: {message}")
    
    def on_log_received(self, level: str, logger_name: str, formatted_message: str):
        """Handle log received signal (runs on main thread)."""
        filter_level = self.level_filter.currentText()
        
        # Apply level filter
        if filter_level != "ALL":
            if level != filter_level:
                return
        
        # Format the log entry
        color = self.get_color_for_level(level)
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_display.setTextCursor(cursor)
        
        # Format text
        format = QTextCharFormat()
        format.setForeground(color)
        
        # Add level indicator
        if level == "ERROR":
            format.setForeground(QColor("#f48771"))  # Red
            prefix = "❌ ERROR"
        elif level == "WARNING":
            format.setForeground(QColor("#dcdcaa"))  # Yellow
            prefix = "⚠️  WARNING"
        elif level == "DEBUG":
            format.setForeground(QColor("#858585"))  # Gray
            prefix = "🔍 DEBUG"
        elif level == "INFO":
            format.setForeground(QColor("#569cd6"))  # Blue
            prefix = "ℹ️  INFO"
        elif level == "CRITICAL":
            format.setForeground(QColor("#ff0000"))  # Bright Red
            prefix = "🔴 CRITICAL"
        else:
            prefix = level
        
        # Insert formatted text
        self.log_display.setCurrentCharFormat(format)
        self.log_display.insertPlainText(f"{prefix} {formatted_message}\n")
        
        # Auto-scroll to bottom
        if self.auto_scroll.isChecked():
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)
    
    def get_color_for_level(self, level: str) -> QColor:
        """Get color for log level."""
        colors = {
            "DEBUG": QColor("#858585"),
            "INFO": QColor("#569cd6"),
            "WARNING": QColor("#dcdcaa"),
            "ERROR": QColor("#f48771"),
            "CRITICAL": QColor("#ff0000"),
        }
        return colors.get(level, QColor("#d4d4d4"))
    
    def update_display(self):
        """Update log display based on current filter."""
        self.log_display.clear()
        filter_level = self.level_filter.currentText()
        
        for entry in self.log_buffer:
            if filter_level != "ALL" and entry['level'] != filter_level:
                continue
            
            formatted_msg = f"[{entry['timestamp']}] {entry['logger']}: {entry['message']}"
            color = self.get_color_for_level(entry['level'])
            
            format = QTextCharFormat()
            format.setForeground(color)
            
            self.log_display.setCurrentCharFormat(format)
            self.log_display.insertPlainText(f"{formatted_msg}\n")
    
    def clear_logs(self):
        """Clear log display and buffer."""
        self.log_buffer.clear()
        self.log_display.clear()
        self.statusBar().showMessage("Logs cleared")


def main():
    """Launch the unified logger GUI."""
    app = QApplication(sys.argv)
    
    # Setup logging (this also registers the callback handlers)
    setup_logging()
    logger = logging.getLogger('UnifiedLogger')
    logger.info("Unified Logger started")
    
    # Create logger window
    window = UnifiedLoggerGUI()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
