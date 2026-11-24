@echo off
REM Builds DeskCat.exe - a single file you can send to friends.
REM Double-click this on a Windows PC. It needs Python (run_windows.bat
REM installs it if you have not run the cat on this PC yet) and internet.
REM The result appears in the "dist" folder.
setlocal
cd /d "%~dp0"

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3.9 or newer was not found.
    echo Double-click run_windows.bat once first - it installs Python - then run this again.
    goto :fail
)

echo == Installing the build tools (one-time, needs internet)...
%PY% -m pip install --disable-pip-version-check --upgrade pyinstaller -r requirements.txt
if errorlevel 1 (
    echo Could not install the build tools. Check your internet connection.
    goto :fail
)

echo.
echo == Building DeskCat.exe (takes a minute or two)...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name DeskCat --icon deskcat.ico --add-data "meow.wav;." deskcat.py
if errorlevel 1 (
    echo The build failed. The messages above say why.
    goto :fail
)
if not exist "dist\DeskCat.exe" (
    echo The build finished but dist\DeskCat.exe is missing.
    goto :fail
)

echo.
echo Done! Your file is:  %~dp0dist\DeskCat.exe
echo Send that one file to your friends - they just double-click it.
explorer "%~dp0dist"
pause
exit /b 0

:fail
echo.
pause
exit /b 1
