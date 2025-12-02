"""
PyQt6 Entry Point - Teacher GUI Launcher
Simply run this file to start the Teacher GUI with PyQt6
"""
import sys
import os
import logging
import subprocess
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from network.logging_util import setup_logging


def main():
    """Launch PyQt6 Teacher GUI."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger('Main_PyQt6')
    
    try:
        logger.info('Starting Teacher GUI with PyQt6...')
        
        # Launch RIP Monitor in a separate terminal
        logger.info('Starting RIP Routing Monitor...')
        rip_monitor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rip_monitor.py')
        
        if sys.platform == 'win32':
            # Windows: Open in new command window
            subprocess.Popen(
                [sys.executable, rip_monitor_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Linux/Mac: Open in new terminal
            subprocess.Popen(
                ['gnome-terminal', '--', sys.executable, rip_monitor_path]
            )
        
        time.sleep(1)  # Give RIP monitor time to start
        logger.info('RIP Monitor launched in separate terminal')
        
        # Launch PyQt6 application with Teacher GUI and Unified Logger
        from PyQt6.QtWidgets import QApplication
        from teacher.pyqt6_main import TeacherGUIQt
        from unified_logger_gui import UnifiedLoggerGUI
        
        app = QApplication(sys.argv)
        
        # Start unified logger window
        logger_window = UnifiedLoggerGUI()
        logger.info('Unified Logger window opened')
        
        # Start teacher GUI window
        window = TeacherGUIQt(num_students=0)
        logger.info('Teacher GUI window opened')
        
        sys.exit(app.exec())

    except Exception as e:
        logger.error(f'Fatal error: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
