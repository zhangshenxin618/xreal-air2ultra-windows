@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if not exist .venv\Scripts\python.exe goto failed
.venv\Scripts\python.exe -c "import cv2, numpy, imageio_ffmpeg, sounddevice" >nul 2>&1
if not errorlevel 1 goto run
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if errorlevel 1 goto failed
:run
.venv\Scripts\python.exe xreal_windows.py %*
:failed
pause
