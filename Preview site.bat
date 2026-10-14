@echo off
cd /d "%~dp0"
start "nettisivut preview server — close this window to stop" py -3 -m http.server 8000 --directory docs
timeout /t 1 /nobreak >nul
start "" http://localhost:8000/index.html
echo.
echo Preview server is running in the other window.
echo Close that window (or press Ctrl+C in it) to stop the server.
pause
