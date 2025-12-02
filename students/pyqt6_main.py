"""
Beautiful PyQt6 GUI for Student Portal.
Modern interface for student participation in P2P election.
"""
import sys
import os
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QMessageBox, QTextEdit, QListWidget,
    QListWidgetItem, QDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.logging_util import setup_logging, get_logger
from network.chat_manager import ChatManager


class StudentGUIQt(QMainWindow):
    """Beautiful PyQt6 Student GUI."""
    
    def __init__(self, student_id: str, teacher_port: int):
        super().__init__()
        self.student_id = student_id
        self.student_name = f'Student {student_id.split("_")[-1]}'
        self.teacher_port = teacher_port
        
        # Calculate unique student port (55109 + student number)
        try:
            student_num = int(student_id.split('_')[-1])
            self.student_port = 55108 + student_num  # 55109, 55110, etc.
        except:
            self.student_port = 55109  # Fallback
        
        self.logger = get_logger(f'StudentGUI-PyQt6-{student_id}')
        
        # Chat manager - use student's unique port, NOT teacher_port
        self.chat_manager = ChatManager(student_id, self.student_port, is_teacher=False)
        
        # Initialize routing table with student itself (direct route, metric=0)
        self.chat_manager.update_routing_metric(student_id, self.student_port, 0)
        
        # State
        self.is_enrolled = False
        self.has_voted = False
        self.current_phase = "idle"
        self.enrollment_enabled = False
        self.candidates = []  # Will be populated dynamically from enrolled students
        self.last_message_count = 0
        
        # Setup UI
        self.setWindowTitle(f"👤 Student Portal - {student_id}")
        self.setGeometry(100, 100, 1000, 700)
        self.setup_ui()
        self.apply_stylesheet()
        self.show()
        
        # Register this student immediately so other students can discover them
        self.chat_manager.register_student()
        self.logger.info(f"Student {student_id} registered in system")
        
        # Start polling for phase updates
        self.phase_timer = QTimer()
        self.phase_timer.timeout.connect(self.check_phase_update)
        self.phase_timer.start(1000)
        
        # Start polling for chat messages
        self.chat_timer = QTimer()
        self.chat_timer.timeout.connect(self.update_chat_display)
        self.chat_timer.start(1000)
        
        # Start polling for recipient list updates (to include newly spawned students)
        self.recipient_timer = QTimer()
        self.recipient_timer.timeout.connect(self.update_recipient_list)
        self.recipient_timer.start(500)  # Poll more frequently (every 500ms instead of 1000ms)
        
        # Start polling to load candidates preemptively (even if we haven't received voting phase yet)
        self.candidates_loader_timer = QTimer()
        self.candidates_loader_timer.timeout.connect(self.preload_candidates)
        self.candidates_loader_timer.start(2000)  # Check every 2 seconds
        
        # Start polling for CR selection notification
        self.cr_notification_timer = QTimer()
        self.cr_notification_timer.timeout.connect(self.check_cr_selection)
        self.cr_notification_timer.start(1000)  # Check every 1 second
        
        # ==================== NETWORK RELIABILITY FEATURES ====================
        
        # Heartbeat timer - broadcast alive signal every 5 seconds
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(5000)
        
        # RIP broadcast timer - broadcast routing table every 30 seconds
        self.rip_broadcast_timer = QTimer()
        self.rip_broadcast_timer.timeout.connect(self.broadcast_routes)
        self.rip_broadcast_timer.start(30000)
        
        # RIP processing timer - process received routing updates every 5 seconds
        self.rip_process_timer = QTimer()
        self.rip_process_timer.timeout.connect(self.process_routing_updates)
        self.rip_process_timer.start(5000)
        
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("👤 STUDENT PORTAL")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #e1e8f0;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Content layout
        content_layout = QHBoxLayout()
        
        # Left panel
        left_layout = QVBoxLayout()
        
        # Enrollment section
        enroll_label = QLabel("✍️ Enrollment")
        enroll_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        enroll_label.setStyleSheet("color: #00d9ff;")
        left_layout.addWidget(enroll_label)
        
        self.enroll_status = QLabel("Status: Not Enrolled")
        self.enroll_status.setStyleSheet("color: #ff6b6b;")
        left_layout.addWidget(self.enroll_status)
        
        self.phase_label = QLabel("Waiting for enrollment phase...")
        self.phase_label.setStyleSheet("color: #8b95a5; font-size: 11px;")
        left_layout.addWidget(self.phase_label)
        
        self.enroll_btn = QPushButton("Enroll Now")
        self.enroll_btn.clicked.connect(self.enroll)
        self.enroll_btn.setEnabled(False)
        self.enroll_btn.setStyleSheet("""
            QPushButton {
                background-color: #5b4bef;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #3d2a7d;
                color: #8b95a5;
                opacity: 0.6;
            }
        """)
        left_layout.addWidget(self.enroll_btn)
        
        left_layout.addSpacing(10)
        
        # Voting section
        vote_label = QLabel("🎯 Voting")
        vote_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        vote_label.setStyleSheet("color: #00d9ff;")
        left_layout.addWidget(vote_label)
        
        self.vote_status = QLabel("Status: Waiting for voting phase")
        self.vote_status.setStyleSheet("color: #8b95a5;")
        left_layout.addWidget(self.vote_status)
        
        # Candidate selection
        candidate_layout = QHBoxLayout()
        candidate_layout.addWidget(QLabel("Candidate:"))
        self.candidate_combo = QComboBox()
        self.candidate_combo.addItems(self.candidates)
        self.candidate_combo.setEnabled(False)
        candidate_layout.addWidget(self.candidate_combo)
        left_layout.addLayout(candidate_layout)
        
        self.vote_btn = QPushButton("Cast Vote")
        self.vote_btn.clicked.connect(self.cast_vote)
        self.vote_btn.setEnabled(False)
        self.vote_btn.setStyleSheet("""
            QPushButton {
                background-color: #5b4bef;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #3d2a7d;
                color: #8b95a5;
                opacity: 0.6;
            }
        """)
        left_layout.addWidget(self.vote_btn)
        
        left_layout.addSpacing(10)
        
        # Status
        status_label = QLabel("📊 Status")
        status_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        status_label.setStyleSheet("color: #00d9ff;")
        left_layout.addWidget(status_label)
        
        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet("color: #51cf66;")
        left_layout.addWidget(self.status_text)
        
        left_layout.addStretch()
        
        content_layout.addLayout(left_layout, 1)
        
        # Right panel - Information
        right_layout = QVBoxLayout()
        
        info_label = QLabel("ℹ️ Information")
        info_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_label.setStyleSheet("color: #00d9ff;")
        right_layout.addWidget(info_label)
        
        # Profile Card
        profile_card = QLabel(f"<b>👤 Your Profile</b><br><br>ID: {self.student_id}<br>Name: {self.student_name}<br>Port: {self.student_port}")
        profile_card.setStyleSheet("""
            QLabel {
                background-color: #1a2a3a;
                color: #e1e8f0;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid #00d9ff;
            }
        """)
        profile_card.setFont(QFont("Segoe UI", 10))
        right_layout.addWidget(profile_card)
        
        # Status Card
        self.status_card = QLabel("<b>📊 Current Status</b><br><br>Phase: <span style='color: #ffa500;'>Idle</span><br>Enrolled: <span style='color: #ff6b6b;'>No</span><br>Voted: <span style='color: #ff6b6b;'>No</span>")
        self.status_card.setStyleSheet("""
            QLabel {
                background-color: #1a2a3a;
                color: #e1e8f0;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid #ffa500;
            }
        """)
        self.status_card.setFont(QFont("Segoe UI", 10))
        right_layout.addWidget(self.status_card)
        
        # Instructions Card
        instructions_card = QLabel("""<b>🚀 How to Participate</b><br>
1. <span style='color: #00d9ff;'>Wait</span> for enrollment phase<br>
2. <span style='color: #00d9ff;'>Enroll</span> to participate<br>
3. <span style='color: #00d9ff;'>Wait</span> for voting phase<br>
4. <span style='color: #00d9ff;'>Cast</span> your vote<br>
5. <span style='color: #00d9ff;'>View</span> results""")
        instructions_card.setStyleSheet("""
            QLabel {
                background-color: #1a2a3a;
                color: #e1e8f0;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid #00ff88;
            }
        """)
        instructions_card.setFont(QFont("Segoe UI", 10))
        right_layout.addWidget(instructions_card)
        
        right_layout.addStretch()
        
        content_layout.addLayout(right_layout, 1)
        
        main_layout.addLayout(content_layout, 1)
        
        # Chat section
        chat_layout = QVBoxLayout()
        
        chat_label = QLabel("💬 Chat")
        chat_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        chat_label.setStyleSheet("color: #00d9ff;")
        chat_layout.addWidget(chat_label)
        
        # Chat display area
        self.chat_display = QListWidget()
        self.chat_display.setStyleSheet("""
            QListWidget {
                background-color: #1e2139;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                border-radius: 4px;
            }
        """)
        self.chat_display.setMaximumHeight(120)
        chat_layout.addWidget(self.chat_display)
        
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
            QComboBox::drop-down {
                border: none;
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
        self.recipient_selector.addItem("teacher", "teacher")
        self.recipient_selector.setMaximumWidth(150)
        self.recipient_selector.hide()  # Hidden by default
        mode_layout.addWidget(self.recipient_selector)
        
        mode_layout.addStretch()
        chat_layout.addLayout(mode_layout)
        
        # Message input
        input_layout = QHBoxLayout()
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type message... (Shift+Enter to send)")
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #232d45;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.message_input.setMaximumHeight(60)
        input_layout.addWidget(self.message_input)
        
        # Send buttons
        self.broadcast_btn = QPushButton("Send")
        self.broadcast_btn.setStyleSheet("background-color: #51cf66; color: white; padding: 5px; border-radius: 4px;")
        self.broadcast_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.broadcast_btn)
        
        chat_layout.addLayout(input_layout)
        main_layout.addLayout(chat_layout)
        
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
            QPushButton:hover:!pressed {
                opacity: 0.8;
            }
            QPushButton:disabled {
                background-color: #4a5568;
                color: #8b95a5;
            }
            QComboBox {
                background-color: #1e2139;
                color: #e1e8f0;
                border: 1px solid #3d4556;
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox:disabled {
                background-color: #0a0e27;
                color: #8b95a5;
            }
        """)
        
    def enroll(self):
        """Enroll in the election."""
        if not self.enrollment_enabled:
            QMessageBox.warning(self, "Warning", "Enrollment phase has not started yet!")
            return
        
        if self.is_enrolled:
            QMessageBox.warning(self, "Warning", "Already enrolled!")
            return
        
        self.is_enrolled = True
        self.enroll_status.setText("Status: ✓ Enrolled")
        self.enroll_status.setStyleSheet("color: #51cf66;")
        
        # Update status card - keep current phase but update enrollment status
        phase_color = "#ffa500"  # Default orange
        phase_name = "Enrollment"
        if self.current_phase == "voting":
            phase_color = "#4dabf7"
            phase_name = "Voting"
        elif self.current_phase == "ended":
            phase_color = "#ff6b6b"
            phase_name = "Ended"
        
        self.status_card.setText(f"<b>📊 Current Status</b><br><br>Phase: <span style='color: {phase_color};'>{phase_name}</span><br>Enrolled: <span style='color: #51cf66;'>Yes</span><br>Voted: <span style='color: #ff6b6b;'>No</span>")
        
        # Update button text and style to green and disable it
        self.enroll_btn.setText("Enrolled")
        self.enroll_btn.setStyleSheet("""
            QPushButton {
                background-color: #51cf66;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #51cf66;
                color: white;
                opacity: 0.9;
            }
        """)
        self.enroll_btn.setEnabled(False)
        self.phase_label.setText("You have successfully enrolled!")
        self.phase_label.setStyleSheet("color: #51cf66;")
        self.status_text.setText("✓ Successfully enrolled!")
        
        self.logger.info(f"{self.student_id} successfully enrolled")
        self.notify_teacher_enrollment()
        
    def cast_vote(self):
        """Cast a vote."""
        if self.has_voted:
            QMessageBox.warning(self, "Warning", "You have already voted!")
            return
        
        candidate = self.candidate_combo.currentText()
        if not candidate:
            QMessageBox.warning(self, "Warning", "Please select a candidate!")
            return
        
        self.has_voted = True
        self.vote_status.setText(f"Status: ✓ Voted for {candidate}")
        self.vote_status.setStyleSheet("color: #51cf66;")
        
        # Update status card
        self.status_card.setText(f"<b>📊 Current Status</b><br><br>Phase: <span style='color: #51cf66;'>Complete</span><br>Enrolled: <span style='color: #51cf66;'>Yes</span><br>Voted: <span style='color: #51cf66;'>Yes ({candidate})</span>")
        
        self.vote_btn.setEnabled(False)
        self.candidate_combo.setEnabled(False)
        self.status_text.setText(f"✓ Vote cast for {candidate}")
        
        self.logger.info(f"{self.student_id} voted for {candidate}")
        self.notify_teacher_vote(candidate)
        
    def check_phase_update(self):
        """Check if teacher has broadcast a phase update via file."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            phase_file = os.path.join(temp_dir, f"election_phase_{self.teacher_port}.txt")
            
            if os.path.exists(phase_file):
                try:
                    with open(phase_file, 'r') as f:
                        new_phase = f.read().strip()
                    
                    # Only update if phase is different
                    if new_phase and new_phase != self.current_phase:
                        self.current_phase = new_phase
                        self.logger.info(f"✓ Received phase update: {new_phase}")
                        self.update_election_state(new_phase)
                except Exception as e:
                    self.logger.debug(f"Error reading phase file: {e}")
            else:
                # Log only once - check if we're missing the phase file
                if self.current_phase == "idle":
                    self.logger.debug(f"Waiting for phase file: {phase_file}")
        except Exception as e:
            self.logger.debug(f"Error checking phase update: {e}")
            
    def check_cr_selection(self):
        """Check if a Class Representative has been selected and show popup."""
        try:
            # Only check for CR selection after voting phase (when results are announced)
            if self.current_phase not in ["results", "ended"]:
                return
            
            import tempfile
            temp_dir = tempfile.gettempdir()
            cr_file = os.path.join(temp_dir, f"selected_cr_{self.teacher_port}.txt")
            
            if os.path.exists(cr_file):
                try:
                    with open(cr_file, 'r') as f:
                        selected_cr = f.read().strip()
                    
                    # Only show popup if CR was just announced and we haven't shown this one yet
                    if selected_cr and selected_cr != getattr(self, '_last_cr_shown', None):
                        self._last_cr_shown = selected_cr
                        self.show_cr_notification(selected_cr)
                except Exception as e:
                    self.logger.debug(f"Error reading CR file: {e}")
        except Exception as e:
            self.logger.debug(f"Error checking CR selection: {e}")
    
    def show_cr_notification(self, cr_name: str):
        """Display CR selection notification with themed popup."""
        try:
            # Create custom dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("🎉 CLASS REPRESENTATIVE ELECTED 🎉")
            dialog.setGeometry(100, 100, 500, 300)
            dialog.setModal(True)
            
            # Create layout
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)
            layout.setContentsMargins(30, 30, 30, 30)
            
            # Title label
            title_label = QLabel("🎉 CLASS REPRESENTATIVE ELECTED 🎉")
            title_font = QFont("Segoe UI", 14)
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_label.setStyleSheet("color: #00d9ff;")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title_label)
            
            # Selected student name (large, green)
            student_label = QLabel(f"👑 {cr_name}")
            student_font = QFont("Segoe UI", 24)
            student_font.setBold(True)
            student_label.setFont(student_font)
            student_label.setStyleSheet("color: #51cf66;")
            student_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(student_label)
            
            # Congratulations message
            congrats_label = QLabel("has been elected as")
            congrats_font = QFont("Segoe UI", 12)
            congrats_label.setFont(congrats_font)
            congrats_label.setStyleSheet("color: #d4d4d4;")
            congrats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(congrats_label)
            
            # Role text
            role_label = QLabel("Class Representative!")
            role_font = QFont("Segoe UI", 14)
            role_font.setBold(True)
            role_label.setFont(role_font)
            role_label.setStyleSheet("color: #ffa94d;")
            role_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(role_label)
            
            # Motivational message
            motivational_label = QLabel("🎊 Congratulations! Lead with honor and integrity 🎊")
            motivational_font = QFont("Segoe UI", 10)
            motivational_label.setFont(motivational_font)
            motivational_label.setStyleSheet("color: #8b95a5;")
            motivational_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(motivational_label)
            
            layout.addStretch()
            
            # Close button
            close_btn = QPushButton("✓ OK")
            close_btn.setFont(QFont("Segoe UI", 11))
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0e639c;
                    color: white;
                    border: 2px solid #00d9ff;
                    padding: 10px 30px;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                    border: 2px solid #00d9ff;
                }
                QPushButton:pressed {
                    background-color: #094771;
                }
            """)
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            # Apply dark theme to dialog
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #0a0e27;
                    border: 2px solid #00d9ff;
                    border-radius: 8px;
                }
            """)
            
            dialog.exec()
            self.logger.info(f"✓ Displayed CR notification: {cr_name}")
        except Exception as e:
            self.logger.error(f"Error showing CR notification: {e}")
            # Fallback to basic message box
            try:
                QMessageBox.information(self, "🎉 CLASS REPRESENTATIVE ELECTED 🎉", 
                                      f"👑 {cr_name} has been elected as Class Representative!")
            except:
                pass
            
            
    def update_election_state(self, state: str):
        """Update election state display."""
        if state == "enrollment":
            self.enrollment_enabled = True
            self.phase_label.setText("(Optional) Click 'Enroll Now' to be a candidate")
            self.phase_label.setStyleSheet("color: #51cf66; font-size: 11px;")
            
            # Update status card
            self.status_card.setText("<b>📊 Current Status</b><br><br>Phase: <span style='color: #51cf66;'>Enrollment</span><br>Enrolled: <span style='color: #ff6b6b;'>No</span><br>Voted: <span style='color: #ff6b6b;'>No</span>")
            
            # Enable button if not already enrolled
            if not self.is_enrolled:
                self.enroll_btn.setEnabled(True)
                self.logger.info("Enrollment phase started - Enroll button enabled")
            else:
                # Already enrolled - keep button disabled with green style
                self.enroll_btn.setEnabled(False)
                self.logger.info("Already enrolled - keeping button disabled with green style")
        elif state == "voting":
            self.enrollment_enabled = False
            self.enroll_btn.setEnabled(False)
            
            # Load enrolled students as candidates for voting
            self.load_enrolled_candidates()
            
            # Update status card
            enrolled_text = "Yes" if self.is_enrolled else "No"
            enrolled_color = "#51cf66" if self.is_enrolled else "#ff6b6b"
            self.status_card.setText(f"<b>📊 Current Status</b><br><br>Phase: <span style='color: #4dabf7;'>Voting</span><br>Enrolled: <span style='color: {enrolled_color};'>{enrolled_text}</span><br>Voted: <span style='color: #ff6b6b;'>No</span>")
            
            self.vote_btn.setEnabled(not self.has_voted)
            self.candidate_combo.setEnabled(not self.has_voted)
            self.vote_status.setText("Status: Voting open")
            self.vote_status.setStyleSheet("color: #4dabf7;")
            self.logger.info(f"✓ Voting phase started - candidates loaded, vote_btn enabled: {self.vote_btn.isEnabled()}")
        elif state == "ended":
            self.enrollment_enabled = False
            self.enroll_btn.setEnabled(False)
            self.vote_btn.setEnabled(False)
            self.candidate_combo.setEnabled(False)
            
            # Update status card
            voted_text = "Yes" if self.has_voted else "No"
            voted_color = "#51cf66" if self.has_voted else "#ff6b6b"
            self.status_card.setText(f"<b>📊 Current Status</b><br><br>Phase: <span style='color: #ff6b6b;'>Ended</span><br>Enrolled: <span style='color: #51cf66;'>{voted_text}</span><br>Voted: <span style='color: {voted_color};'>{voted_text}</span>")
            
            # Lock voting button with red styling to indicate election ended
            self.vote_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff6b6b;
                    color: white;
                    padding: 8px;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:disabled {
                    background-color: #ff6b6b;
                    color: white;
                    opacity: 0.7;
                }
            """)
            self.vote_btn.setText("Voting Closed")
            
            self.status_text.setText("Election has ended")
            self.status_text.setStyleSheet("color: #ff6b6b;")
            self.logger.info("Election ended - voting buttons locked")
    
    def load_enrolled_candidates(self):
        """Load list of enrolled students as candidates for voting."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            enrollment_file = os.path.join(temp_dir, f"enrollments_{self.teacher_port}.txt")
            
            if os.path.exists(enrollment_file):
                try:
                    with open(enrollment_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            enrolled_students = content.split('\n')
                            enrolled_students = [s for s in enrolled_students if s]
                            self.candidates = enrolled_students
                            
                            # Clear and update combo box
                            self.candidate_combo.clear()
                            self.candidate_combo.addItems(self.candidates)
                            
                            self.logger.info(f"Loaded {len(self.candidates)} enrolled candidates: {self.candidates}")
                        else:
                            self.logger.warning("No enrolled students found in enrollment file")
                            self.candidates = []
                            self.candidate_combo.clear()
                except Exception as e:
                    self.logger.error(f"Error reading enrollment file: {e}")
            else:
                self.logger.warning(f"Enrollment file not found: {enrollment_file}")
        except Exception as e:
            self.logger.error(f"Error loading enrolled candidates: {e}", exc_info=True)
            
    def preload_candidates(self):
        """Preemptively load candidates even if voting phase hasn't started yet.
        This helps students spawned during voting phase to be ready to vote."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            enrollment_file = os.path.join(temp_dir, f"enrollments_{self.teacher_port}.txt")
            
            # Only preload if we haven't loaded candidates yet and enrollment file exists
            if not self.candidates and os.path.exists(enrollment_file):
                try:
                    with open(enrollment_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            enrolled_students = content.split('\n')
                            enrolled_students = [s for s in enrolled_students if s]
                            self.candidates = enrolled_students
                            
                            # Update combo box
                            self.candidate_combo.clear()
                            self.candidate_combo.addItems(self.candidates)
                            
                            self.logger.info(f"✓ Preloaded {len(self.candidates)} candidates (before voting phase): {self.candidates}")
                except Exception as e:
                    pass  # Silent fail - will retry later
        except Exception as e:
            pass  # Silent fail
            
    def notify_teacher_enrollment(self):
        """Notify teacher that this student has enrolled."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            enrollment_file = os.path.join(temp_dir, f"enrollments_{self.teacher_port}.txt")
            
            self.logger.info(f"Writing to enrollment file: {enrollment_file}")
            
            # Read current enrollments
            enrolled_students = []
            if os.path.exists(enrollment_file):
                try:
                    with open(enrollment_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            enrolled_students = content.split('\n')
                            enrolled_students = [s for s in enrolled_students if s]
                except Exception as e:
                    self.logger.warning(f"Could not read enrollment file: {e}")
            
            # Add this student if not already enrolled
            if self.student_id not in enrolled_students:
                enrolled_students.append(self.student_id)
                self.logger.info(f"Added {self.student_id} to enrollments")
            else:
                self.logger.info(f"{self.student_id} already in enrollments")
            
            # Write back to file
            try:
                with open(enrollment_file, 'w') as f:
                    f.write('\n'.join(enrolled_students))
                self.logger.info(f"Successfully wrote enrollment file. Total enrolled: {len(enrolled_students)}")
            except Exception as e:
                self.logger.error(f"Error writing enrollment file: {e}")
        except Exception as e:
            self.logger.error(f"Error notifying teacher: {e}", exc_info=True)
    
    def notify_teacher_vote(self, candidate: str):
        """Notify teacher that this student has voted."""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            votes_file = os.path.join(temp_dir, f"votes_{self.teacher_port}.txt")
            
            self.logger.info(f"Writing to votes file: {votes_file}")
            
            # Read current votes
            votes = []
            if os.path.exists(votes_file):
                try:
                    with open(votes_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            votes = content.split('\n')
                            votes = [v for v in votes if v]
                except Exception as e:
                    self.logger.warning(f"Could not read votes file: {e}")
            
            # Add this student's vote (format: student_id,candidate)
            vote_entry = f"{self.student_id},{candidate}"
            if vote_entry not in votes:
                votes.append(vote_entry)
                self.logger.info(f"Added vote: {vote_entry}")
            else:
                self.logger.info(f"Vote already recorded: {vote_entry}")
            
            # Write back to file
            try:
                with open(votes_file, 'w') as f:
                    f.write('\n'.join(votes))
                self.logger.info(f"Successfully wrote votes file. Total votes: {len(votes)}")
            except Exception as e:
                self.logger.error(f"Error writing votes file: {e}")
        except Exception as e:
            self.logger.error(f"Error notifying teacher of vote: {e}", exc_info=True)
    
    def send_broadcast_message(self):
        """Send a broadcast message to all users."""
        message = self.message_input.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "Warning", "Message cannot be empty!")
            return
        
        msg_id = self.chat_manager.send_broadcast(message)
        if msg_id:
            self.logger.info(f"Broadcast message sent (msg_id: {msg_id})")
            self.message_input.clear()
            self.update_chat_display()
        else:
            QMessageBox.critical(self, "Error", "Failed to send broadcast message")
    
    def on_message_mode_changed(self):
        """Handle message mode change (broadcast vs private)."""
        mode = self.message_mode.currentData()
        if mode == "private":
            self.update_recipient_list()
            self.recipient_selector.show()
        else:
            self.recipient_selector.hide()
    
    def update_recipient_list(self):
        """Update recipient list to include all active students plus teacher."""
        try:
            mode = self.message_mode.currentData()
            if mode != "private":
                return
            
            # Get current selection
            current_recipient = self.recipient_selector.currentData()
            
            # Build list of recipients: teacher + all registered students
            recipients = ["teacher"]
            
            # Get registered students (students that have spawned)
            registered_students = self.chat_manager.get_registered_students()
            other_students = [s for s in registered_students if s != self.student_id]
            recipients.extend(other_students)
            
            # Also discover students who have sent messages (for backward compatibility)
            discovered_students = self.chat_manager.get_all_active_students()
            for student in discovered_students:
                if student != self.student_id and student not in recipients:
                    recipients.append(student)
            
            # Remove duplicates and sort (except teacher stays first)
            other_recipients = sorted(set(recipients[1:]))
            recipients = ["teacher"] + other_recipients
            
            # Get current items in dropdown (as data values)
            current_items = [self.recipient_selector.itemData(i) for i in range(self.recipient_selector.count())]
            
            # Only update if the list changed
            if set(recipients) != set(current_items) or len(recipients) != len(current_items):
                self.logger.debug(f"Recipient list updated: {recipients}")
                
                # Store current selection to restore it
                self.recipient_selector.blockSignals(True)
                self.recipient_selector.clear()
                
                for recipient in recipients:
                    display_name = recipient.replace("_", " ").title() if recipient != "teacher" else "👨‍🏫 Teacher"
                    self.recipient_selector.addItem(display_name, recipient)
                
                # Try to restore previous selection
                if current_recipient and current_recipient in recipients:
                    index = self.recipient_selector.findData(current_recipient)
                    if index >= 0:
                        self.recipient_selector.setCurrentIndex(index)
                
                self.recipient_selector.blockSignals(False)
        except Exception as e:
            self.logger.debug(f"Error updating recipient list: {e}")
    
    def send_message(self):
        """Send message (broadcast or private based on mode)."""
        mode = self.message_mode.currentData()
        message = self.message_input.toPlainText().strip()
        
        if not message:
            QMessageBox.warning(self, "Warning", "Message cannot be empty!")
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
            QMessageBox.critical(self, "Error", f"Failed to send broadcast: {e}")
            self.logger.error(f"Error sending broadcast: {e}")
    
    def send_private_message(self, message: str):
        """Send a private message to selected recipient."""
        recipient = self.recipient_selector.currentData()
        
        if not recipient:
            QMessageBox.warning(self, "Warning", "Please select a recipient!")
            return
        
        try:
            msg_id = self.chat_manager.send_private(recipient, message)
            self.logger.info(f"Private message sent to {recipient} (msg_id: {msg_id})")
            self.message_input.clear()
            self.update_chat_display()
            QMessageBox.information(self, "Success", f"Private message sent to {recipient}!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send private message: {e}")
            self.logger.error(f"Error sending private message: {e}")
    
    def update_chat_display(self):
        """Update chat display with all messages (broadcast + private unified)."""
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
        """Send heartbeat to indicate student is alive."""
        try:
            self.chat_manager.send_heartbeat()
            self.logger.debug("Heartbeat sent")
        except Exception as e:
            self.logger.error(f"Error sending heartbeat: {e}")
    
    def broadcast_routes(self):
        """Broadcast RIP routing table to all peers."""
        try:
            self.chat_manager.broadcast_rip_update()
            routes_count = len(self.chat_manager.routing_table)
            self.logger.debug(f"RIP: Broadcast routing table ({routes_count} known routes)")
        except Exception as e:
            self.logger.error(f"Error broadcasting RIP updates: {e}")
    
    def process_routing_updates(self):
        """Process received RIP updates and update local routing table."""
        try:
            updated = self.chat_manager.process_rip_updates()
            if updated:
                routes_count = len(self.chat_manager.routing_table)
                self.logger.debug(f"RIP: Routing table updated ({routes_count} routes now known)")
        except Exception as e:
            self.logger.error(f"Error processing RIP updates: {e}")

