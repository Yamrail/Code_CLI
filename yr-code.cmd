@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" goto venv
where python >nul 2>nul
if errorlevel 1 goto launcher
python -B "%~dp0yr_code.py" %*
exit /b %errorlevel%
:venv
"%~dp0.venv\Scripts\python.exe" -B "%~dp0yr_code.py" %*
exit /b %errorlevel%
:launcher
where py >nul 2>nul
if errorlevel 1 goto missing
py -3 -B "%~dp0yr_code.py" %*
exit /b %errorlevel%
:missing
echo HOLD: Install Python 3.11 or later, then run yr-code doctor.
exit /b 2
