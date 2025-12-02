@echo off
REM PyQt6 Election System - Teacher Dashboard Launcher
REM This batch file starts the teacher GUI application

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0

REM Change to the project directory
cd /d "%SCRIPT_DIR%"

REM Display banner
cls
echo.
echo ================================================================================
echo     PyQt6 Election System - Teacher Dashboard
echo ================================================================================
echo.
echo Starting the application...
echo.

REM Run the Python application
python main_pyqt6.py

REM If the application exits, show status
if %errorlevel% equ 0 (
    echo.
    echo ✓ Application closed successfully
) else (
    echo.
    echo ✗ Application exited with error code: %errorlevel%
    echo Press any key to exit...
    pause
)

endlocal
