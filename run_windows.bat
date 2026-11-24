@echo off
REM DeskCat - double-click this file.
REM It installs Python and PyQt6 automatically if they are missing,
REM then starts the cat. First run needs internet and takes a few minutes.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0DeskCatSetup.ps1"
if errorlevel 1 (
    echo.
    echo DeskCat could not start. See the message above for what went wrong.
    pause
)
