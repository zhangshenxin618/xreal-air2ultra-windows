@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe goto missing
.venv\Scripts\python.exe -X utf8 tests\run_tests.py
if errorlevel 1 goto failed
echo All tests passed.
goto done
:missing
echo Run start.cmd once or install requirements-lock.txt in .venv first.
goto failed
:failed
echo Tests did not complete successfully.
:done
pause
