@echo off
REM Admin PDF Toolkit - start from the Python package (needs Python 3.11+).
REM Windows users without Python: use the self-contained AdminPDFToolkit-*-Windows.zip.
setlocal
cd /d "%~dp0\..\server"
if not exist ".venv\Scripts\python.exe" (
  echo Kurulum yapiliyor / Setting up...
  call :make_venv || goto :nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install . || goto :fail
  call "%~dp0offer-ocr.bat"
)
".venv\Scripts\python.exe" -m adminpdf --open %*
goto :eof

:make_venv
REM "python" may be the Microsoft Store stub, so check the version really runs.
where py >nul 2>nul && py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && (py -3 -m venv .venv & goto :eof)
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && (python -m venv .venv & goto :eof)
exit /b 1

:nopython
echo.
echo Bu bilgisayarda Python 3.11+ yok. Kurulum gerektirmeyen Windows paketini indirin:
echo Python 3.11+ is not installed. Download the self-contained Windows package:
echo   https://github.com/AmrasElessar/adminpdftoolkit/releases/latest
echo   (AdminPDFToolkit-...-Windows.zip)
start "" "https://github.com/AmrasElessar/adminpdftoolkit/releases/latest"
pause
goto :eof

:fail
echo Kurulum basarisiz oldu / Setup failed.
pause
goto :eof
