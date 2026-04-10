@echo off
setlocal

set APP_NAME=DepthController
set ENTRY=server_tray.py

echo [build] Cleaning previous output...
if exist dist\%APP_NAME%.exe del /f /q dist\%APP_NAME%.exe
if exist build rmdir /s /q build

echo [build] Running PyInstaller...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --icon "anchor.png" ^
  --name %APP_NAME% ^
  --add-data "templates;templates" ^
  --add-data "server.py;." ^
  --add-data "static;static" ^
  --add-data "maps;maps" ^
  --add-data "anchor.png;." ^
  %ENTRY%

if errorlevel 1 (
  echo [build] ERROR: PyInstaller failed.
  pause
  exit /b 1
)

echo.
echo [build] Done!  dist\%APP_NAME%.exe is ready.
echo.
pause
