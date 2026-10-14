@echo off
cd /d "%~dp0"
echo Checking dependencies...
py -3 -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo Could not install dependencies. Is Python installed? See README.md.
  pause
  exit /b 1
)
echo.
py -3 admin.py
echo.
echo The admin tool has stopped.
pause
