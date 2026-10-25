@echo off
REM Admin PDF Toolkit - installs Tesseract OCR and the Turkish language data.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-ocr-windows.ps1"
pause
