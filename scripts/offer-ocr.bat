@echo off
REM Offers OCR (Tesseract + Turkish) once, if it isn't installed yet.
where tesseract >nul 2>nul && goto :eof
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" goto :eof
if exist "%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe" goto :eof
choice /C EH /N /M "Taranmis belgeler icin OCR (Tesseract) kurulsun mu? / Install OCR now? [E=evet / H=hayir] "
if errorlevel 2 goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-ocr-windows.ps1"
