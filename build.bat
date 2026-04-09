@echo off
echo Installing dependencies...
pip install flask waitress pystray pillow pyinstaller

echo Building executable...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --name "DepthController" ^
  --add-data "server.py;." ^
  server_tray.py

echo Done. Executable is in dist\DepthController.exe
pause
