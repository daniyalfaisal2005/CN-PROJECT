"""
Entry point for PyQt6 Student GUI.
Spawned by the teacher application.
"""
import sys
import os
import argparse
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from network.logging_util import setup_logging, get_logger
from students.pyqt6_main import StudentGUIQt
from PyQt6.QtWidgets import QApplication


def main():
    """Main entry point for student GUI."""
    parser = argparse.ArgumentParser(description='PyQt6 Student Portal')
    parser.add_argument('--student_id', required=True, help='Student ID')
    parser.add_argument('--teacher_port', type=int, required=True, help='Teacher port')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    logger = get_logger('StudentEntry')
    
    try:
        # Create QApplication first
        app = QApplication(sys.argv)
        
        # Create and show student GUI
        student_gui = StudentGUIQt(args.student_id, args.teacher_port)
        student_gui.show()
        
        logger.info(f'✓ Started PyQt6 student GUI for {args.student_id}')
        
        # Run the application event loop
        exit_code = app.exec()
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f'Error starting student GUI: {e}', exc_info=True)
        print(f'\n❌ ERROR: Failed to start student GUI')
        print(f'   Student ID: {args.student_id}')
        print(f'   Error: {e}')
        print('\nKeeping window open for 10 seconds...')
        import time
        time.sleep(10)
        sys.exit(1)


if __name__ == '__main__':
    main()
