@echo off
REM Admin PDF Toolkit v2 - first run creates a virtualenv, later runs just start.
setlocal
cd /d "%~dp0\..\server"
if not exist ".venv\Scripts\python.exe" (
  echo Kurulum yapiliyor / Setting up...
  py -3 -m venv .venv || python -m venv .venv || goto :nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install . || goto :fail
  call :offer_ocr
)
".venv\Scripts\python.exe" -m adminpdf --open %*
goto :eof
:nopython
echo Python 3.11+ bulunamadi. https://www.python.org/downloads/ adresinden kurun.
pause
goto :eof
:fail
echo Kurulum basarisiz oldu / Setup failed.
pause
goto :eof
:offer_ocr
REM First run only: offer OCR (Tesseract + Turkish) if it isn't installed yet.
where tesseract >nul 2>nul && goto :eof
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" goto :eof
if exist "%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe" goto :eof
choice /C EH /N /M "Taranmis belgeler icin OCR (Tesseract) kurulsun mu? / Install OCR now? [E=evet / H=hayir] "
if errorlevel 2 goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-ocr-windows.ps1"
goto :eof
