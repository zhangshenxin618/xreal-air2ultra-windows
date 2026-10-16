@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe goto missing
.venv\Scripts\python.exe -X utf8 check_stereo.py
goto done
:missing
echo Run start.cmd once to prepare the environment.
:done
pause
