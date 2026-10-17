@echo off
REM Builds dist\VoidLock.exe (single file, no console window, with icon)
python -m pip install -r requirements.txt
python -m PyInstaller --noconsole --onefile --name VoidLock --icon assets\icon.ico --add-data "assets;assets" main.py
echo.
echo Done: dist\VoidLock.exe
