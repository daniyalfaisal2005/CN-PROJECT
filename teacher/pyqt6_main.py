"""
Beautiful PyQt6 GUI for Teacher Dashboard.
Professional, modern election management interface.
"""
import sys
import os
import subprocess
import threading
from typing import Dict, List, Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QStatusBar, QTextEdit, QListWidget, QListWidgetItem,
    QComboBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.logging_util import setup_logging, get_logger
from network.chat_manager import ChatManager


class TeacherGUIQt(QMainWindow):
    """Beautiful PyQt6 Teacher GUI."""
    
    def __init__(self, num_students: int = 0):
        super().__init__()
        self.num_students = num_students
        self.logger = get_logger('TeacherGUI-PyQt6')
        
        # State
        self.teacher_port = 55108  # Fixed port for file-based communication
        self.students: Dict[str, Dict] = {}
        self.enrolled_students: List[str] = []
        self.last_enrolled_students = set()
        self.voted_students: List[str] = []
        self.last_voted_students = set()
        self.student_processes: List[subprocess.Popen] = []  # Track spawned processes
        
        # Chat system
        self.chat_manager = ChatManager("teacher", self.teacher_port, is_teacher=True)
        self.last_message_count = 0
        
        # Initialize routing table with teacher itself (direct route, metric=0)
        self.chat_manager.update_routing_metric("teacher", self.teacher_port, 0)
        
        # Clear old enrollment and phase files
        self._clear_old_files()
        
        # Setup UI
        self.setWindowTitle("👨‍🏫 Teacher Dashboard - P2P Election System")
        self.setGeometry(100, 100, 1400, 900)
        self.setup_ui()
        self.apply_stylesheet()
        self.show()
        
        # Start polling for enrollment updates
        self.enrollment_timer = QTimer()
        self.enrollment_timer.timeout.connect(self.check_enrollment_updates)
        self.enrollment_timer.start(500)  # Check every 500ms for faster updates
        
        # Start polling for voting updates
        self.voting_timer = QTimer()
        self.voting_timer.timeout.connect(self.check_voting_updates)
        self.voting_timer.start(500)  # Check every 500ms for faster updates
        
        # Start polling for chat updates
        self.chat_timer = QTimer()
        self.chat_timer.timeout.connect(self.update_chat_display)
        self.chat_timer.start(1000)  # Check every 1000ms for new messages
        
        # Start polling for recipient list updates
        self.recipient_timer = QTimer()
        self.recipient_timer.timeout.connect(self.update_recipient_list)
        self.recipient_timer.start(500)  # Update recipient list every 500ms
        
        # ==================== NETWORK RELIABILITY FEATURES ====================
        
        # Heartbeat timer - broadcast alive signal every 5 seconds
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(5000)
        
        # Peer monitoring timer - check active peers every 5 seconds for faster detection
        self.peer_monitor_timer = QTimer()
        self.peer_monitor_timer.timeout.connect(self.monitor_peer_health)
        self.peer_monitor_timer.start(5000)
        
        # RIP broadcast timer - broadcast routing table every 30 seconds
        self.rip_broadcast_timer = QTimer()
        self.rip_broadcast_timer.timeout.connect(self.broadcast_routes)
        self.rip_broadcast_timer.start(30000)
        
        # RIP processing timer - process received routing updates every 5 seconds
        self.rip_process_timer = QTimer()
        self.rip_process_timer.timeout.connect(self.process_routing_updates)
        self.rip_process_timer.start(5000)
        
        # Initial check
        self.check_enrollment_updates()
    
    def _clear_old_files(self):
        """Clear old enrollment, phase, chat, and student registry files from previous runs."""
        try:
            import tempfile
            from pathlib import Path
            temp_dir = tempfile.gettempdir()
            
            # Specific files to clear
            files_to_clear = [
                f"enrollments_{self.teacher_port}.txt",
                f"election_phase_{self.teacher_port}.txt",
                f"votes_{self.teacher_port}.txt",
                f"selected_cr_{self.teacher_port}.txt",  # Clear CR file from previous election
                f"broadcast_messages_{self.teacher_port}.txt",  # Old port-specific version
                "broadcast_messages.txt",  # New shared broadcast file
                f"student_registry_{self.teacher_port}.txt",  # Old port-specific registry
                "student_registry.txt"  # New shared registry
            ]
            
            for filename in files_to_clear:
                filepath = os.path.join(temp_dir, filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        self.logger.info(f"Cleared old file: {filepath}")
                    except Exception as e:
                        self.logger.warning(f"Could not clear {filepath}: {e}")
            
            # Clear all private message files (both old port-specific and new naming)
            try:
                # Old pattern: private_messages_{port}_*_to_*.txt
                pattern = f"private_messages_{self.teacher_port}_*_to_*.txt"
                for filepath in Path(temp_dir).glob(pattern):
                    try:
                        filepath.unlink()
                        self.logger.info(f"Cleared old file: {filepath}")
                    except Exception as e:
                        self.logger.warning(f"Could not clear {filepath}: {e}")
                
                # New pattern: private_messages_*_to_*.txt (no port)
                pattern = "private_messages_*_to_*.txt"
                for filepath in Path(temp_dir).glob(pattern):
                    try:
                        filepath.unlink()
                        self.logger.info(f"Cleared old file: {filepath}")
                    except Exception as e:
                        self.logger.warning(f"Could not clear {filepath}: {e}")
            except Exception as e:
                self.logger.warning(f"Error clearing private message files: {e}")
        except Exception as e:
            self.logger.warning(f"Error clearing old files: {e}")
        
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("👨‍🏫 TEACHER DASHBOARD")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #e1e8f0;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Control Toolbar - horizontal layout for all controls
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)
        
        # Spawn section
        spawn_label = QLabel("📚 Students:")
        spawn_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        spawn_label.setStyleSheet("color: #00d9ff;")
        toolbar_layout.addWidget(spawn_label)
        
        self.num_students_spin = QSpinBox()
        self.num_students_spin.setMinimum(0)
        self.num_students_spin.setMaximum(50)
        self.num_students_spin.setValue(1)
        self.num_students_spin.setMaximumWidth(60)
        toolbar_layout.addWidget(self.num_students_spin)
        
        spawn_btn = QPushButton("Spawn")
        spawn_btn.clicked.connect(self.spawn_students)
        spawn_btn.setStyleSheet("background-color: #5b4bef; color: white; padding: 8px 16px; border-radius: 4px;")
        spawn_btn.setMaximumHeight(35)
        toolbar_layout.addWidget(spawn_btn)
        
        toolbar_layout.addSpacing(20)
        
        # Election control buttons
        control_label = QLabel("🎛️ Control:")
        control_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        control_label.setStyleSheet("color: #00d9ff;")
        toolbar_layout.addWidget(control_label)
        
        enroll_btn = QPushButton("Start Enrollment")
        enroll_btn.clicked.connect(self.start_enrollment)
        enroll_btn.setStyleSheet("background-color: #ffa94d; color: white; padding: 8px 16px; border-radius: 4px;")
        enroll_btn.setMaximumHeight(35)
        toolbar_layout.addWidget(enroll_btn)
        
        vote_btn = QPushButton("Start Voting")
        vote_btn.clicked.connect(self.start_voting)
        vote_btn.setStyleSheet("background-color: #4dabf7; color: white; padding: 8px 16px; border-radius: 4px;")
        vote_btn.setMaximumHeight(35)
        toolbar_layout.addWidget(vote_btn)
        
        end_btn = QPushButton("End Election")
        end_btn.clicked.connect(self.end_election)
        end_btn.setStyleSheet("background-color: #ff6b6b; color: white; padding: 8px 16px; border-radius: 4px;")
        end_btn.setMaximumHeight(35)
        toolbar_layout.addWidget(end_btn)
        
        toolbar_layout.addSpacing(20)
        
        # Status indicators
        status_label = QLabel("📊")
        status_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        status_label.setStyleSheet("color: #00d9ff;")
        toolbar_layout.addWidget(status_label)
        
        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet("color: #51cf66;")
        toolbar_layout.addWidget(self.status_text)
        
        toolbar_layout.addSpacing(10)
        
        self.enrolled_label = QLabel("Enrolled: 0")
        self.enrolled_label.setStyleSheet("color: #51cf66;")
        toolbar_layout.addWidget(self.enrolled_label)
        
        self.voted_label = QLabel("Voted: 0")
        self.voted_label.setStyleSheet("color: #4dabf7;")
        toolbar_layout.addWidget(self.voted_label)
        
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)
        
        # Content layout with splitter for responsive design
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Students table (was right panel, now full width)
        students_layout = QVBoxLayout()
        
        table_label = QLabel("👥 Active Students")
        table_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        table_label.setStyleSheet("color: #00d9ff;")
        students_layout.addWidget(table_label)
        
        self.students_table = QTableWidget()
        self.students_table.setColumnCount(5)
        self.students_table.setHorizontalHeaderLabels(["Student ID", "Status", "Phase", "Enrolled", "Voted"])
        self.students_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f1419;
                alternate-background-color: #1a2a3a;
                gridline-color: #2a3a4a;
                border: 1px solid #3d4556;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 10px;
                color: #e1e8f0;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #00d9ff;
                color: #0f1419;
            }
            QHeaderView::section {
                background-color: #0a1a2a;
                color: #00d9ff;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #00d9ff;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.students_table.horizontalHeader().setStretchLastSection(True)
        self.students_table.setAlternatingRowColors(True)
        self.students_table.setRowHeight(0, 35)
        self.students_table.setColumnWidth(0, 100)
        self.students_table.setColumnWidth(1, 90)
        self.students_table.setColumnWidth(2, 100)
        self.students_table.setColumnWidth(3, 90)
        self.students_table.setColumnWidth(4, 90)
        students_layout.addWidget(self.students_table)
        
        students_widget = QWidget()
        students_widget.setLayout(students_layout)
        
        main_layout.addWidget(students_widget, 2)  # Students table gets more space
        
        # Election Results Section
        results_layout = QVBoxLayout()
        
        results_label = QLabel("📊 Election Results")
        results_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        results_label.setStyleSheet("color: #00d9ff;")
        results_layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(2)
        self.results_table.setHorizontalHeaderLabels(["Candidate", "Votes"])
        self.results_table.setMinimumHeight(150)
        self.results_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f1419;
                gridline-color: #2a3a4a;
                border: 1px solid #3d4556;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 10px;
                color: #e1e8f0;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #0a1a2a;
                color: #00d9ff;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #00d9ff;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(self.results_table, 1)  # Give results table flex space
        
        main_layout.addLayout(results_layout, 1)  # Results section gets flex space
        
        # Chat section at bottom
        chat_layout = QVBoxLayout()
        
        chat_label = QLabel("💬 Classroom Chat")
        chat_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        chat_label.setStyleSheet("color: #00d9ff;")
        chat_layout.addWidget(chat_label)
        
        chat_display_layout = QHBoxLayout()
        
        # Message display
        self.chat_display = QListWidget()
        self.chat_display.setMinimumHeight(150)
        self.chat_display.setStyleSheet("""
            QListWidget {
                background-color: #1e2139;
                border: 1px solid #3d4556;
                border-radius: 4px;
                color: #e1e8f0;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                line-height: 1.4;
            }
        """)
        chat_display_layout.addWidget(self.chat_display)
        chat_layout.addLayout(chat_display_layout, 1)  # Chat display gets flex space
        
        # Message mode selector (Broadcast vs Private)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: #e1e8f0;")
        mode_layout.addWidget(mode_label)
        
        self.message_mode = QComboBox()
        self.message_mode.addItem("📢 Broadcast", "broadcast")
        self.message_mode.addItem("🔒 Private", "private")
        self.message_mode.setStyleSheet("""
            QComboBox {
                background-color: #1e2139;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                padding: 5px;
                border-radius: 4px;
            }
        """)
        self.message_mode.currentIndexChanged.connect(self.on_message_mode_changed)
        mode_layout.addWidget(self.message_mode)
        
        # Recipient selector (hidden by default)
        recipient_label = QLabel("To:")
        recipient_label.setStyleSheet("color: #e1e8f0;")
        mode_layout.addWidget(recipient_label)
        
        self.recipient_selector = QComboBox()
        self.recipient_selector.setStyleSheet("""
            QComboBox {
                background-color: #1e2139;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                padding: 5px;
                border-radius: 4px;
            }
        """)
        self.recipient_selector.setMaximumWidth(150)
        self.recipient_selector.hide()  # Hidden by default
        mode_layout.addWidget(self.recipient_selector)
        
        mode_layout.addStretch()
        chat_layout.addLayout(mode_layout)
        
        # Message input area
        input_layout = QHBoxLayout()
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(40)
        self.message_input.setPlaceholderText("Type a message... (Shift+Enter to send)")
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #1e2139;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
            }
        """)
        
        # Override keyPressEvent to send on Shift+Enter
        original_keyPressEvent = self.message_input.keyPressEvent
        def message_input_keyPressEvent(event):
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self.send_message()
            else:
                original_keyPressEvent(event)
        self.message_input.keyPressEvent = message_input_keyPressEvent
        
        input_layout.addWidget(self.message_input)
        
        send_btn = QPushButton("Send")
        send_btn.setMaximumWidth(100)
        send_btn.clicked.connect(self.send_message)
        send_btn.setStyleSheet("background-color: #51cf66; color: white; padding: 8px;")
        input_layout.addWidget(send_btn)
        
        chat_layout.addLayout(input_layout)
        
        main_layout.addLayout(chat_layout, 1)  # Chat section gets flex space
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def apply_stylesheet(self):
        """Apply dark theme stylesheet."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a0e27;
                color: #e1e8f0;
            }
            QLabel {
                color: #e1e8f0;
            }
            QPushButton {
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
            QSpinBox {
                background-color: #1e2139;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                padding: 5px;
                border-radius: 4px;
            }
            QTableWidget {
                background-color: #232d45;
                alternate-background-color: #1e2139;
            }
        """)
        
    def spawn_students(self):
        """Spawn student processes (capture output to logger, no console windows)."""
        num = self.num_students_spin.value()
        if num <= 0:
            QMessageBox.warning(self, "Warning", "Please enter a number greater than 0")
            return
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        current_count = len(self.students)
        
        self.logger.info(f"Starting to spawn {num} students...")
        
        for i in range(num):
            student_num = current_count + i + 1
            student_id = f'student_{student_num}'
            
            if student_id in self.students:
                continue
            
            self.students[student_id] = {
                'status': 'Online',
                'enrolled': False,
                'voted': False,
                'phase': 'Idle'
            }
            
            try:
                cmd = [
                    sys.executable, 'main_pyqt6_student.py',
                    '--student_id', student_id,
                    '--teacher_port', str(self.teacher_port)
                ]
                
                # Spawn without visible console - capture output to logger
                if sys.platform == 'win32':
                    # Windows: hide console window and capture output
                    process = subprocess.Popen(
                        cmd,
                        cwd=project_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        text=True
                    )
                else:
                    # On Linux/Mac, suppress console and capture output
                    process = subprocess.Popen(
                        cmd,
                        cwd=project_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        text=True,
                        preexec_fn=None
                    )
                
                # Track the process
                self.student_processes.append(process)
                self.logger.info(f'✓ Spawned: {student_id} (PID: {process.pid}) - output captured to logger')
                
                # Start a thread to capture output from this student
                self._start_output_capture(student_id, process)
            except Exception as e:
                self.logger.error(f'Error spawning {student_id}: {e}')
        
        self.update_students_table()
        self.statusBar().showMessage(f'✓ Spawned {num} students (output captured in logger)')
    
    def _start_output_capture(self, student_id: str, process: subprocess.Popen):
        """Capture stdout/stderr from student process and log it."""
        def read_output():
            """Read process output in background thread."""
            try:
                # Read stdout
                if process.stdout:
                    for line in process.stdout:
                        if line.strip():
                            self.logger.info(f'[{student_id} OUT] {line.strip()}')
                
                # Read stderr
                if process.stderr:
                    for line in process.stderr:
                        if line.strip():
                            self.logger.warning(f'[{student_id} ERR] {line.strip()}')
                
                # Wait for process to finish
                process.wait()
                self.logger.info(f'[{student_id}] Process ended (exit code: {process.returncode})')
            except Exception as e:
                self.logger.error(f'Error capturing output from {student_id}: {e}')
        
        # Start capture thread as daemon
        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()
    
    def closeEvent(self, event):
        """Handle window close event - terminate all student processes."""
        self.logger.info("Teacher GUI closing - terminating all student processes...")
        
        try:
            # Stop timers
            if hasattr(self, 'enrollment_timer'):
                self.enrollment_timer.stop()
            if hasattr(self, 'voting_timer'):
                self.voting_timer.stop()
            if hasattr(self, 'chat_timer'):
                self.chat_timer.stop()
            if hasattr(self, 'recipient_timer'):
                self.recipient_timer.stop()
            
            # Terminate all spawned student processes
            for i, process in enumerate(self.student_processes):
                try:
                    if process.poll() is None:  # Process is still running
                        process.terminate()
                        self.logger.info(f"Terminated student process {i+1}")
                        
                        # Wait a bit for graceful termination
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            # Force kill if graceful termination times out
                            process.kill()
                            self.logger.warning(f"Force killed student process {i+1}")
                except Exception as e:
                    self.logger.error(f"Error terminating process {i+1}: {e}")
            
            self.logger.info(f"All {len(self.student_processes)} student processes terminated")
        except Exception as e:
            self.logger.error(f"Error in closeEvent: {e}")
        
        # Accept the close event
        event.accept()
        
    def start_enrollment(self):
        """Start enrollment phase."""
        self.broadcast_phase("enrollment")
        self.status_text.setText("✓ Enrollment Started")
        self.statusBar().showMessage("Enrollment phase started")
        
    def start_voting(self):
        """Start voting phase."""
        self.broadcast_phase("voting")
        self.status_text.setText("✓ Voting Started")
        self.statusBar().showMessage("Voting phase started")
        
    def end_election(self):
        """End election and announce class representative."""
        self.broadcast_phase("ended")
        
        # Calculate election results
        vote_results = self.calculate_election_results()
        
        # Determine winner(s)
        if vote_results:
            # Sort by vote count in descending order
            sorted_results = sorted(vote_results.items(), key=lambda x: x[1], reverse=True)
            winner = sorted_results[0][0]
            winner_votes = sorted_results[0][1]
            
            # Announce winner
            announcement = f"🎉 ELECTION RESULTS 🎉\n\n👑 Class Representative: {winner}\n📊 Votes: {winner_votes}\n\nCongratulations to our newly elected class representative!"
            msg_id = self.chat_manager.send_broadcast(announcement)
            self.logger.info(f"✓ Announced winner: {winner} with {winner_votes} votes (msg_id: {msg_id})")
            self.status_text.setText(f"✓ Election Ended - Winner: {winner}")
            # Broadcast CR selection to all screens
            self.broadcast_cr_selection(winner)
        elif self.enrolled_students:
            # Fallback: No votes cast - select first enrolled student as representative
            winner = self.enrolled_students[0]
            announcement = f"🎉 ELECTION RESULTS 🎉\n\n👑 Class Representative: {winner}\n📊 No votes were cast - First enrolled student selected.\n\nCongratulations to our newly elected class representative!"
            msg_id = self.chat_manager.send_broadcast(announcement)
            self.logger.info(f"✓ No votes cast - Auto-selected first enrolled student: {winner} (msg_id: {msg_id})")
            self.status_text.setText(f"✓ Election Ended - Winner (Auto-selected): {winner}")
            # Update results table to show the auto-selected candidate
            self.results_data = {winner: 0}
            self.update_results_table()
            # Broadcast CR selection to all screens
            self.broadcast_cr_selection(winner)
        else:
            self.status_text.setText("✓ Election Ended - No votes recorded")
        
        self.statusBar().showMessage("Election ended")
    
    def broadcast_cr_selection(self, cr_name: str):
        """Broadcast CR selection to all students via temp file."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            cr_file = os.path.join(temp_dir, f"selected_cr_{self.teacher_port}.txt")
            
            with open(cr_file, 'w') as f:
                f.write(cr_name)
            
            self.logger.info(f"✓ Broadcasted CR selection: {cr_name}")
        except Exception as e:
            self.logger.error(f"Error broadcasting CR selection: {e}")
        
    def calculate_election_results(self) -> Dict[str, int]:
        """Calculate vote counts for each candidate."""
        vote_results = {}
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            votes_file = os.path.join(temp_dir, f"votes_{self.teacher_port}.txt")
            
            if os.path.exists(votes_file):
                try:
                    with open(votes_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            vote_entries = content.split('\n')
                            # Format: student_id,candidate
                            for entry in vote_entries:
                                if ',' in entry:
                                    parts = entry.split(',', 1)
                                    candidate = parts[1].strip()
                                    vote_results[candidate] = vote_results.get(candidate, 0) + 1
                except Exception as e:
                    self.logger.error(f"Error reading votes file: {e}")
        except Exception as e:
            self.logger.error(f"Error calculating election results: {e}")
        
        return vote_results
        
    def broadcast_phase(self, phase: str):
        """Broadcast election phase to all students via temp file."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            phase_file = os.path.join(temp_dir, f"election_phase_{self.teacher_port}.txt")
            
            with open(phase_file, 'w') as f:
                f.write(phase)
            
            # Update phase for all students
            phase_display = "Enrollment" if phase == "enrollment" else ("Voting" if phase == "voting" else "Complete")
            for student_id in self.students:
                self.students[student_id]['phase'] = phase_display
            
            self.update_students_table()
            self.logger.info(f"✓ Broadcasted phase '{phase}' to students")
        except Exception as e:
            self.logger.error(f"Error broadcasting phase: {e}")
            
    def check_enrollment_updates(self):
        """Check for enrollment updates from students."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            enrollment_file = os.path.join(temp_dir, f"enrollments_{self.teacher_port}.txt")
            
            if os.path.exists(enrollment_file):
                try:
                    with open(enrollment_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            enrolled_students = set(content.split('\n'))
                            enrolled_students = {s for s in enrolled_students if s}
                        else:
                            enrolled_students = set()
                    
                    if enrolled_students != self.last_enrolled_students:
                        self.last_enrolled_students = enrolled_students
                        self.enrolled_students = list(enrolled_students)
                        
                        # Update student records
                        for student_id in self.students:
                            if student_id in enrolled_students:
                                self.students[student_id]['enrolled'] = True
                            else:
                                self.students[student_id]['enrolled'] = False
                        
                        self.update_students_table()
                        self.enrolled_label.setText(f'Enrolled: {len(enrolled_students)}')
                        self.logger.info(f'Enrollment updated: {len(enrolled_students)} students - {enrolled_students}')
                except Exception as e:
                    self.logger.error(f"Error reading enrollment file {enrollment_file}: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error checking enrollment updates: {e}", exc_info=True)
            
    def update_students_table(self):
        """Update the students table display."""
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import Qt
        
        self.students_table.setRowCount(0)
        
        for row, (student_id, data) in enumerate(self.students.items()):
            self.students_table.insertRow(row)
            self.students_table.setRowHeight(row, 32)  # Set consistent row height
            
            # Column 0: Student ID
            id_item = QTableWidgetItem(student_id)
            id_item.setForeground(QColor('#00d9ff'))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.students_table.setItem(row, 0, id_item)
            
            # Column 1: Status (Online/Offline)
            status_item = QTableWidgetItem(data['status'])
            status_color = QColor('#51cf66') if data['status'] == 'Online' else QColor('#ff6b6b')
            status_item.setForeground(status_color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.students_table.setItem(row, 1, status_item)
            
            # Column 2: Phase (Idle/Enrollment/Voting/Complete)
            phase_item = QTableWidgetItem(data.get('phase', 'Idle'))
            phase_color = QColor('#ffa500')  # Default orange for Idle
            if data.get('phase') == 'Enrollment':
                phase_color = QColor('#ffa500')
            elif data.get('phase') == 'Voting':
                phase_color = QColor('#4dabf7')
            elif data.get('phase') == 'Complete':
                phase_color = QColor('#51cf66')
            phase_item.setForeground(phase_color)
            phase_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.students_table.setItem(row, 2, phase_item)
            
            # Column 3: Enrolled status
            enrolled_item = QTableWidgetItem("✓ Yes" if data['enrolled'] else "✗ No")
            enrolled_color = QColor('#51cf66') if data['enrolled'] else QColor('#ff6b6b')
            enrolled_item.setForeground(enrolled_color)
            enrolled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.students_table.setItem(row, 3, enrolled_item)
            
            # Column 4: Voted status
            voted_item = QTableWidgetItem("✓ Yes" if data['voted'] else "✗ No")
            voted_color = QColor('#51cf66') if data['voted'] else QColor('#ff6b6b')
            voted_item.setForeground(voted_color)
            voted_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.students_table.setItem(row, 4, voted_item)
    
    def update_results_table(self):
        """Update the election results table with current vote counts."""
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import Qt
        
        vote_results = self.calculate_election_results()
        self.results_table.setRowCount(0)
        
        if vote_results:
            # Sort by vote count in descending order
            sorted_results = sorted(vote_results.items(), key=lambda x: x[1], reverse=True)
            
            for row, (candidate, votes) in enumerate(sorted_results):
                self.results_table.insertRow(row)
                self.results_table.setRowHeight(row, 28)
                
                # Column 0: Candidate name
                candidate_item = QTableWidgetItem(candidate)
                candidate_item.setForeground(QColor('#00d9ff'))
                candidate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_table.setItem(row, 0, candidate_item)
                
                # Column 1: Vote count
                votes_item = QTableWidgetItem(str(votes))
                # Color code: winner in green, others in cyan
                if row == 0:
                    votes_item.setForeground(QColor('#51cf66'))  # Green for winner
                else:
                    votes_item.setForeground(QColor('#4dabf7'))  # Blue for others
                votes_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_table.setItem(row, 1, votes_item)
    
    def check_voting_updates(self):
        """Check for voting updates from students."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            votes_file = os.path.join(temp_dir, f"votes_{self.teacher_port}.txt")
            
            if os.path.exists(votes_file):
                try:
                    with open(votes_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            vote_entries = content.split('\n')
                            vote_entries = [v for v in vote_entries if v]
                            # Extract student IDs from vote entries (format: student_id,candidate)
                            voted_students = set(v.split(',')[0] for v in vote_entries if ',' in v)
                        else:
                            voted_students = set()
                    
                    if voted_students != self.last_voted_students:
                        self.last_voted_students = voted_students
                        self.voted_students = list(voted_students)
                        
                        # Update student records
                        for student_id in self.students:
                            if student_id in voted_students:
                                self.students[student_id]['voted'] = True
                            else:
                                self.students[student_id]['voted'] = False
                        
                        self.update_students_table()
                        self.update_results_table()  # Update results table with new votes
                        self.voted_label.setText(f'Voted: {len(voted_students)}')
                        self.logger.info(f'Voting updated: {len(voted_students)} students - {voted_students}')
                except Exception as e:
                    self.logger.error(f"Error reading votes file {votes_file}: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error checking voting updates: {e}", exc_info=True)
    
    def send_broadcast_message(self):
        """Send a broadcast message to all students."""
        message_text = self.message_input.toPlainText().strip()
        if not message_text:
            return
        
        try:
            msg_id = self.chat_manager.send_broadcast(message_text)
            self.logger.info(f"Broadcast message sent (msg_id: {msg_id})")
            self.message_input.clear()
            self.update_chat_display()
        except Exception as e:
            self.logger.error(f"Error sending broadcast message: {e}")
    
    def on_message_mode_changed(self):
        """Handle message mode change (broadcast vs private)."""
        mode = self.message_mode.currentData()
        if mode == "private":
            # Refresh recipient list when switching to private mode
            self.update_recipient_list()
            self.recipient_selector.show()
        else:
            self.recipient_selector.hide()
    
    def update_recipient_list(self):
        """Update the recipient selector with current student list."""
        try:
            mode = self.message_mode.currentData()
            if mode == "private":
                # Get current recipient
                current_recipient = self.recipient_selector.currentData()
                
                # Get list of student IDs
                student_ids = sorted(self.students.keys())
                
                # Only update if the list changed
                current_items = [self.recipient_selector.itemData(i) for i in range(self.recipient_selector.count())]
                
                if student_ids != current_items:
                    # Clear and repopulate
                    self.recipient_selector.clear()
                    for student_id in student_ids:
                        self.recipient_selector.addItem(student_id, student_id)
                    
                    # Try to restore previous selection
                    if current_recipient and current_recipient in student_ids:
                        index = self.recipient_selector.findData(current_recipient)
                        if index >= 0:
                            self.recipient_selector.setCurrentIndex(index)
        except Exception as e:
            self.logger.debug(f"Error updating recipient list: {e}")
    
    def send_message(self):
        """Send message (broadcast or private based on mode)."""
        mode = self.message_mode.currentData()
        message = self.message_input.toPlainText().strip()
        
        if not message:
            return
        
        if mode == "broadcast":
            self.send_broadcast_message_internal(message)
        else:
            self.send_private_message(message)
    
    def send_broadcast_message_internal(self, message: str):
        """Internal method to send broadcast message."""
        try:
            msg_id = self.chat_manager.send_broadcast(message)
            self.logger.info(f"Broadcast message sent (msg_id: {msg_id})")
            self.message_input.clear()
            self.update_chat_display()
        except Exception as e:
            self.logger.error(f"Error sending broadcast: {e}")
    
    def send_private_message(self, message: str):
        """Send a private message to selected student."""
        recipient = self.recipient_selector.currentData()
        
        if not recipient:
            return
        
        try:
            msg_id = self.chat_manager.send_private(recipient, message)
            self.logger.info(f"Private message sent to {recipient} (msg_id: {msg_id})")
            self.message_input.clear()
            self.update_chat_display()
        except Exception as e:
            self.logger.error(f"Error sending private message: {e}")
    
    def update_chat_display(self):
        """Update the chat display with all messages (broadcast + private unified)."""
        try:
            # Get all messages (both broadcast and private combined)
            messages = self.chat_manager.get_all_messages()
            
            if len(messages) != self.last_message_count:
                self.last_message_count = len(messages)
                
                self.chat_display.clear()
                
                # Show header
                header = QListWidgetItem("📬 All Messages (Broadcast + Private)")
                header.setForeground(__import__('PyQt6.QtGui', fromlist=['QColor']).QColor('#00d9ff'))
                self.chat_display.addItem(header)
                
                # Show last 15 messages
                display_messages = messages[-15:]
                for message in display_messages:
                    item = QListWidgetItem(message)
                    # Color code: private messages in orange, broadcast in light blue
                    if "🔒" in message or "->" in message:
                        item.setForeground(__import__('PyQt6.QtGui', fromlist=['QColor']).QColor('#ffa94d'))
                    else:
                        item.setForeground(__import__('PyQt6.QtGui', fromlist=['QColor']).QColor('#e1e8f0'))
                    self.chat_display.addItem(item)
                
                # Auto-scroll to bottom
                self.chat_display.scrollToBottom()
        except Exception as e:
            self.logger.debug(f"Error updating chat display: {e}")
    
    # ==================== NETWORK RELIABILITY FEATURES ====================
    
    def send_heartbeat(self):
        """Send heartbeat to indicate teacher is alive."""
        try:
            self.chat_manager.send_heartbeat()
            self.logger.debug("Heartbeat sent")
        except Exception as e:
            self.logger.error(f"Error sending heartbeat: {e}")
    
    def monitor_peer_health(self):
        """Monitor health of active peers and update student status display."""
        try:
            # Use 12-second timeout (allows 2-3 missed heartbeats before marking offline)
            active_peers = self.chat_manager.get_active_peers(heartbeat_timeout=12)
            active_peer_ids = {p['user_id'] for p in active_peers}
            
            # Update student status based on heartbeat data
            for student_id in self.students:
                if student_id in active_peer_ids:
                    self.students[student_id]['status'] = 'Online'
                else:
                    self.students[student_id]['status'] = 'Offline'
            
            # Update the display
            self.update_students_table()
            
            if active_peers:
                peer_list = ', '.join([f"{p['user_id']}({p['response_time']:.1f}s)" for p in active_peers])
                self.logger.info(f"Active peers: {len(active_peers)} - {peer_list}")
                
                # Update health indicator in title or status
                self.statusBar().showMessage(f"Health: {len(active_peers)} peers active | Avg response: {active_peers[0]['response_time']:.2f}s")
            else:
                self.logger.warning("No active peers detected")
                self.statusBar().showMessage("Health: No active peers")
        except Exception as e:
            self.logger.error(f"Error monitoring peer health: {e}")
    
    def broadcast_routes(self):
        """Broadcast RIP routing table to all peers."""
        try:
            self.chat_manager.broadcast_rip_update()
            routes_count = len(self.chat_manager.routing_table)
            self.logger.info(f"RIP: Broadcast routing table ({routes_count} known routes)")
        except Exception as e:
            self.logger.error(f"Error broadcasting RIP updates: {e}")
    
    def process_routing_updates(self):
        """Process received RIP updates and update local routing table."""
        try:
            updated = self.chat_manager.process_rip_updates()
            if updated:
                routes_count = len(self.chat_manager.routing_table)
                self.logger.info(f"RIP: Routing table updated ({routes_count} routes now known)")
        except Exception as e:
            self.logger.error(f"Error processing RIP updates: {e}")

