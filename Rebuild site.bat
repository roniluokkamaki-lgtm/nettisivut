@echo off
cd /d "%~dp0"
echo Installing/checking dependencies...
py -3 -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo Could not install dependencies. Is Python installed? See README.md.
  pause
  exit /b 1
)
echo.
echo Building the site...
py -3 build.py --check
if errorlevel 1 (
  echo.
  echo BUILD FAILED - see the messages above, fix paintings.csv or the images, and try again.
) else (
  echo.
  echo Done. Run preview.bat to look at it, then commit and push to publish.
)
pause
