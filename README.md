# PyQt6 P2P Election System

This repository contains a PyQt6-based peer-to-peer classroom election system (Teacher + Student GUIs) with file-based IPC, RIP routing monitor, and a unified logger.

## Quick overview
- `main_pyqt6.py` — Teacher GUI launcher (opens Teacher Dashboard and Unified Logger; spawns `rip_monitor.py`).
- `main_pyqt6_student.py` — Student GUI entrypoint (spawned by the Teacher when clicking "Spawn").
- `teacher/` — Teacher GUI implementation (`pyqt6_main.py`).
- `students/` — Student GUI implementation (`pyqt6_main.py`).
- `network/` — Networking utilities and chat manager (ACKs, RIP, heartbeat).
- `rip_monitor.py` — RIP routing monitor (launched in a separate terminal by the teacher launcher).

## Prerequisites
Install the following before running the application.

- Python 3.10 or newer (3.11 recommended)
  - Make sure `python` (and optionally `pythonw`) is on your PATH.
- Pip (comes with Python).
- PyQt6 GUI toolkit

Optional / recommended:
- Use a virtual environment (`venv`) to keep dependencies isolated.
- Windows: `pythonw.exe` is used when running the GUI silently (no console window).

## Required Python packages
At minimum, install:

- `PyQt6` (for GUI)

You can install the required package with pip or use the provided `requirements.txt`:

PowerShell (recommended, from project root):

```powershell
# create and activate venv (optional, recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# install requirements
pip install -r requirements.txt
```

Or install PyQt6 directly:

```powershell
pip install PyQt6
```

## Running the application
From the project root (`e:\3 Semester\5.CN Theory\Cn Final project\PyQt6_Project`):

- Double-click `run.bat` (if provided) — will launch Teacher GUI (may use `pythonw.exe` to hide console).
- Or run from PowerShell/Command Prompt (for debugging to see console logs):

```powershell
# Run with console (shows logs)
python main_pyqt6.py

# Run silently (no terminal) on Windows if pythonw is available
pythonw main_pyqt6.py
```

What opens when you run the teacher launcher:
- Teacher Dashboard (PyQt6 window)
- Unified Logger window (PyQt6 window)
- RIP Monitor (separate terminal, launched by the teacher launcher) — can be disabled/hidden if desired

Spawning students:
- In the Teacher GUI click `Spawn` to start student processes. The teacher uses `main_pyqt6_student.py` to spawn student apps.

## Files & behavior to be aware of
- Temporary files are used for file-based IPC (broadcast messages, private messages, enrollments, votes, ACK files). These are typically placed in the system temporary directory (e.g., `%TEMP%` on Windows).
- ACK files follow the naming pattern `ack_{port}_{msg_id}.txt`.
- If you see many stale files while developing, clear the system temp folder entries related to this project (be careful not to remove unrelated temp files).

## Troubleshooting
- If GUI does not start, run `python main_pyqt6.py` from a console to see error messages.
- If `python` is not found, install Python and ensure it is added to PATH.
- If you prefer no extra RIP Monitor terminal, edit `main_pyqt6.py` and remove or modify the subprocess spawn that launches `rip_monitor.py`.
- If student spawn fails, check that `main_pyqt6_student.py` exists and is executable by the same Python interpreter.

## Notes for Windows users
- The provided `run.bat` can be used to start the application. If you want no console window, use `pythonw.exe` or the `run.bat` variant that starts via `start "" pythonw.exe main_pyqt6.py`.
- Running the teacher launcher from the command prompt will keep a console open showing logs. Double-clicking `run.bat` may use `pythonw.exe` depending on the batch content.

## Security & Production
- This project uses file-based IPC and polling — not suitable for production without locking, atomic writes, and stronger security.
- Consider replacing with sockets, message queues, or a proper server for production deployments.

## Contact
If you need changes to the start logic (e.g., hide RIP monitor, change ports, or add packaging), open an issue or contact the maintainer.

---
Generated README for quick local setup and usage.