@echo off
rem Launcher for the keyboard/mouse macro tool (键鼠模拟器)
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python main.py
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py main.py
  ) else (
    echo Python not found. Please install Python 3 from https://www.python.org/
    echo (Remember to check "Add python.exe to PATH" during installation.)
  )
)
if errorlevel 1 pause
