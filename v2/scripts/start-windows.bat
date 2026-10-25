@echo off
REM Admin PDF Toolkit v2 — first run creates a virtualenv, later runs just start.
setlocal
cd /d "%~dp0\..\server"
if not exist ".venv\Scripts\python.exe" (
  echo Kurulum yapiliyor / Setting up...
  py -3 -m venv .venv || python -m venv .venv || goto :nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install . || goto :fail
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
