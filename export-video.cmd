@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe goto missing
.venv\Scripts\python.exe export_recording.py %*
goto done
:missing
echo Run start.cmd once to prepare the environment.
:done
pause
