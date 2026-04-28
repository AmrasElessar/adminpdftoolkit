@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Admin PDF Toolkit - Servis Yoneticisi (by Engin)

REM =======================================================================
REM  Admin PDF Toolkit by Engin - Tum servis islemleri tek menude
REM  Tum islemler Yonetici izni gerektirir.
REM =======================================================================

REM SVCNAME deliberately preserved as HTAdminPDF for backwards compat
REM (existing service registrations on user machines still work).
set "SVCNAME=HTAdminPDF"
set "NSSM=%~dp0nssm.exe"
if not exist "%NSSM%" set "NSSM=nssm"

REM --- Yonetici kontrolu ---
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   [HATA] Yonetici izni gerekli
    echo ============================================================
    echo   Bu dosyaya sag tiklayip "Yonetici olarak calistir" secin.
    echo.
    pause
    exit /b 1
)

:MENU
cls
echo.
echo ============================================================
echo   Admin PDF Toolkit - Servis Yoneticisi (by Engin)
echo ============================================================
echo   Servis adi: %SVCNAME%
echo   URL       : http://127.0.0.1:8000
echo ============================================================
echo.
echo   [1] Servis olarak kur ve baslat
echo   [2] Servisi baslat
echo   [3] Servisi durdur
echo   [4] Servis durumunu goster
echo   [5] Servisi tamamen kaldir
echo   [Q] Cikis
echo.
choice /c 12345Q /n /m "  Seciminiz: "
if errorlevel 6 goto END
if errorlevel 5 goto REMOVE
if errorlevel 4 goto STATUS
if errorlevel 3 goto STOP
if errorlevel 2 goto START
if errorlevel 1 goto INSTALL
goto MENU

REM ----------------------------------------------------------------------
:INSTALL
echo.
echo === Servis kurulumu basliyor ===

REM --- NSSM kurulu mu? ---
where %NSSM% >nul 2>&1
if errorlevel 1 (
    echo.
    echo NSSM (servis yoneticisi) kurulu degil.
    echo Otomatik kurmak istiyor musunuz? (winget kullanir)
    echo.
    choice /c YN /n /m "  Y = Evet, N = Hayir: "
    if errorlevel 2 (
        echo.
        echo NSSM'yi elle indirip ya bu klasore "nssm.exe" olarak koyun
        echo ya da PATH'e ekleyin: https://nssm.cc/download
        echo.
        pause
        goto MENU
    )
    winget install -e --id NSSM.NSSM --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo NSSM kurulamadi. Lutfen elle kurun.
        pause
        goto MENU
    )
    echo.
    echo NSSM kuruldu. Lutfen bu menuyu kapatip tekrar Yonetici olarak acin.
    pause
    goto END
)

REM --- Python yolu ---
set "PYEXE="
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%i"
if "%PYEXE%"=="" (
    echo.
    echo [HATA] Python bulunamadi. Once "Sunucuyu Baslat.bat" ile kurulum yapin.
    pause
    goto MENU
)

set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"

REM --- Eski servis varsa kaldir ---
%NSSM% status %SVCNAME% >nul 2>&1
if not errorlevel 1 (
    echo Eski servis bulundu, durdurulup kaldiriliyor...
    %NSSM% stop %SVCNAME% >nul 2>&1
    %NSSM% remove %SVCNAME% confirm >nul 2>&1
)

echo.
echo Servis kuruluyor...
%NSSM% install %SVCNAME% "%PYEXE%" "%APPDIR%\app.py"
%NSSM% set %SVCNAME% AppDirectory "%APPDIR%"
%NSSM% set %SVCNAME% DisplayName "Admin PDF Toolkit"
%NSSM% set %SVCNAME% Description "Admin PDF Toolkit by Engin -- convert / edit / annotate / replace (LAN)"
%NSSM% set %SVCNAME% Start SERVICE_AUTO_START
%NSSM% set %SVCNAME% AppStdout "%APPDIR%\_work\service.log"
%NSSM% set %SVCNAME% AppStderr "%APPDIR%\_work\service.err.log"
%NSSM% set %SVCNAME% AppRotateFiles 1
%NSSM% set %SVCNAME% AppRotateBytes 5242880

echo.
echo Servis baslatiliyor...
%NSSM% start %SVCNAME%
if errorlevel 1 (
    echo Servis baslatma basarisiz. Loglar: %APPDIR%\_work\service.err.log
    pause
    goto MENU
)

echo.
echo ============================================================
echo   Servis kuruldu ve calisiyor: %SVCNAME%
echo   Sunucu: http://127.0.0.1:8000
echo   Bilgisayar her acildiginda otomatik baslayacak.
echo ============================================================
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:START
echo.
echo === Servis baslatiliyor ===
%NSSM% start %SVCNAME%
echo.
echo Tamamlandi. URL: http://127.0.0.1:8000
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:STOP
echo.
echo === Servis durduruluyor ===
%NSSM% stop %SVCNAME%
echo.
echo Durduruldu.
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:STATUS
echo.
echo === Servis durumu ===
%NSSM% status %SVCNAME%
if errorlevel 1 echo Servis kurulu degil.
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:REMOVE
echo.
echo === Servisi tamamen kaldir ===
echo Servis sistemden silinecek. Veriler (history, _work) korunur.
echo.
choice /c YN /n /m "Devam edilsin mi? [Y=Evet, N=Hayir]: "
if errorlevel 2 goto MENU

%NSSM% stop %SVCNAME% >nul 2>&1
%NSSM% remove %SVCNAME% confirm
echo.
echo Servis kaldirildi.
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:END
exit /b 0
