@echo off
echo Installing dependencies...
pip install flask waitress pystray pillow pyinstaller
echo Building executable...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --name "DepthController" ^
  --icon "anchor.png" ^
  --add-data "server.py;." ^
  --add-data "anchor.png;." ^
  server_tray.py
echo Done. Executable is in dist\DepthController.exe
pause