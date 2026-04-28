@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Admin PDF Toolkit - Portable Paket (by Engin)

REM =======================================================================
REM  Admin PDF Toolkit by Engin - Portable paket olusturma + sikistirma
REM =======================================================================

set "DIST=dist\Admin_PDF_Toolkit_Portable"

:MENU
cls
echo.
echo ============================================================
echo   Admin PDF Toolkit - Portable Paket (by Engin)
echo ============================================================
echo   Hedef klasor: %DIST%
echo ============================================================
echo.
echo   [1] Sifirdan portable paket olustur (~10-15 dk, ~1.2 GB)
echo   [2] Mevcut dist klasorunu hizli guncelle
echo       (Python paketlerine dokunmaz, sadece kaynak kod)
echo   [3] dist'i .7z paketine sikistir (en kucuk boyut)
echo   [4] dist'i Self-Extracting .exe yap (kurulum gerektirmez)
echo   [Q] Cikis
echo.
choice /c 1234Q /n /m "  Seciminiz: "
if errorlevel 5 goto END
if errorlevel 4 goto SFX
if errorlevel 3 goto SEVENZIP
if errorlevel 2 goto UPDATE
if errorlevel 1 goto BUILD
goto MENU

REM ----------------------------------------------------------------------
:BUILD
echo.
echo === Sifirdan portable paket olustur ===
echo.
echo Bu islem 10-15 dakika surecek ve ~1-2 GB indirme yapacak.
echo Bittiginde '%DIST%\' klasoru hazir olacak.
echo.
choice /c YN /n /m "Devam edilsin mi? [Y=Evet, N=Hayir]: "
if errorlevel 2 goto MENU

python build_portable.py
if errorlevel 1 (
    echo.
    echo [HATA] Build basarisiz. Yukaridaki mesajlari kontrol edin.
    pause
    goto MENU
)

echo.
echo ============================================================
echo   Paket hazir: %DIST%\
echo.
echo   Sirada yapabilecekleriniz:
echo     - Menu [3] ile .7z paketi olustur (en kucuk^)
echo     - Menu [4] ile Self-Extracting .exe yap (en kolay tasima^)
echo     - veya %DIST%\ klasorune sag tik ^> "Sikistirilmis klasore gonder"
echo ============================================================
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:UPDATE
echo.
echo === Mevcut dist klasorunu hizli guncelle ===

if not exist "%DIST%" (
    echo.
    echo [HATA] %DIST% klasoru yok.
    echo Once menu [1] ile portable paket olusturun.
    echo.
    pause
    goto MENU
)

echo Kaynak dosyalar dist klasorune kopyalaniyor...
echo (Python ve paketlere dokunulmaz - sadece kaynak guncellenir)
echo.

REM --- Tek dosyalar ---
copy /y "app.py"             "%DIST%\app.py"             >nul && echo   ok  app.py
copy /y "app_http.py"        "%DIST%\app_http.py"        >nul && echo   ok  app_http.py
copy /y "state.py"           "%DIST%\state.py"           >nul && echo   ok  state.py
copy /y "settings.py"        "%DIST%\settings.py"        >nul && echo   ok  settings.py
copy /y "pdf_converter.py"   "%DIST%\pdf_converter.py"   >nul && echo   ok  pdf_converter.py
copy /y "pdf_safety.py"      "%DIST%\pdf_safety.py"      >nul && echo   ok  pdf_safety.py
copy /y "requirements.txt"   "%DIST%\requirements.txt"   >nul && echo   ok  requirements.txt
if exist "LICENSE" (
    copy /y "LICENSE"        "%DIST%\LICENSE"            >nul && echo   ok  LICENSE
)
if exist "NOTICE.txt" (
    copy /y "NOTICE.txt"     "%DIST%\NOTICE.txt"         >nul && echo   ok  NOTICE.txt
)

REM --- Klasorler ---
if exist "%DIST%\core"      rmdir /s /q "%DIST%\core"      2>nul
xcopy /e /i /q /y "core"      "%DIST%\core\"       >nul && echo   ok  core/

if exist "%DIST%\routers"   rmdir /s /q "%DIST%\routers"   2>nul
xcopy /e /i /q /y "routers"   "%DIST%\routers\"    >nul && echo   ok  routers/

if exist "%DIST%\pipelines" rmdir /s /q "%DIST%\pipelines" 2>nul
xcopy /e /i /q /y "pipelines" "%DIST%\pipelines\"  >nul && echo   ok  pipelines/

if exist "%DIST%\parsers"   rmdir /s /q "%DIST%\parsers"   2>nul
xcopy /e /i /q /y "parsers"   "%DIST%\parsers\"    >nul && echo   ok  parsers/

if exist "%DIST%\templates" rmdir /s /q "%DIST%\templates" 2>nul
xcopy /e /i /q /y "templates" "%DIST%\templates\"  >nul && echo   ok  templates/

if exist "%DIST%\static"    rmdir /s /q "%DIST%\static"    2>nul
xcopy /e /i /q /y "static"    "%DIST%\static\"     >nul && echo   ok  static/

if exist "%DIST%\tests"     rmdir /s /q "%DIST%\tests"     2>nul
xcopy /e /i /q /y "tests"     "%DIST%\tests\"      >nul && echo   ok  tests/

if exist "%DIST%\scripts"   rmdir /s /q "%DIST%\scripts"   2>nul
xcopy /e /i /q /y "scripts"   "%DIST%\scripts\"    >nul && echo   ok  scripts/

REM --- ClamAV (opsiyonel — scripts/setup_clamav.py'i once calistirin) ---
REM database/ ve _download.zip kopyalama sonrasi temizlenir; freshclam ilk
REM acilista yeniden indirir.
if exist "clamav\clamscan.exe" (
    if exist "%DIST%\clamav"    rmdir /s /q "%DIST%\clamav"    2>nul
    xcopy /e /i /q /y "clamav"    "%DIST%\clamav\"     >nul && echo   ok  clamav/ ^(binaries^)
    if exist "%DIST%\clamav\database" rmdir /s /q "%DIST%\clamav\database" 2>nul
    if exist "%DIST%\clamav\_download.zip" del /q "%DIST%\clamav\_download.zip" 2>nul
) else (
    echo   .. clamav/ atlandi ^(scripts\setup_clamav.py calistirin^)
)

REM --- Baslat.bat'i guncelle ---
> "%DIST%\Admin PDF Toolkit Baslat.bat" (
    echo @echo off
    echo chcp 65001 ^>nul
    echo cd /d "%%~dp0"
    echo title Admin PDF Toolkit - Sunucu
    echo.
    echo set "PYTHONHOME="
    echo REM PYTHONPATH: kaynak kod dizini (app.py icin^) + site-packages
    echo set "PYTHONPATH=%%~dp0;%%~dp0python\Lib\site-packages"
    echo set "PATH=%%~dp0python;%%~dp0python\Scripts;%%PATH%%"
    echo.
    echo echo.
    echo echo ============================================================
    echo echo   Admin PDF Toolkit by Engin
    echo echo   Portable Surum - Kurulum gerekmez
    echo echo ============================================================
    echo echo.
    echo.
    echo REM --- ClamAV hazir mi? Yoksa indir + imza pull ---
    echo if exist "clamav\clamscan.exe" ^(
    echo     if exist "clamav\database\main.cvd" goto :BASLAT_RUN
    echo     if exist "clamav\database\main.cld" goto :BASLAT_RUN
    echo ^)
    echo echo.
    echo echo ClamAV antivirus hazirlaniyor ^(ilk seferde ^~1-2 dakika^)...
    echo echo Internet baglantisi gerekli; yoksa atlayacak.
    echo echo.
    echo "%%~dp0python\python.exe" "%%~dp0scripts\setup_clamav.py"
    echo if errorlevel 1 ^(
    echo     echo.
    echo     echo UYARI: ClamAV hazirlanamadi - yapisal tarama + Defender ile devam edilecek.
    echo     timeout /t 4 ^>nul
    echo ^)
    echo.
    echo :BASLAT_RUN
    echo start "" /min cmd /c "timeout /t 2 /nobreak ^>nul ^&^& start http://127.0.0.1:8000"
    echo.
    echo "%%~dp0python\python.exe" "%%~dp0app.py"
    echo.
    echo echo.
    echo echo Sunucu durdu. Kapatmak icin bir tusa basin...
    echo pause ^>nul
)
echo   ok  Admin PDF Toolkit Baslat.bat

REM Eski gecmis veritabani temizle
if exist "%DIST%\history.db" del "%DIST%\history.db"

REM __pycache__ temizle
for /d /r "%DIST%" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul

echo.
echo ============================================================
echo   Guncelleme tamamlandi.
echo.
echo   Test:  %DIST%\Admin PDF Toolkit Baslat.bat (cift tikla^)
echo.
echo   NOT: ZIP/7z'i yeniden yaparsan hash degisir.
echo        Modal'daki VirusTotal/MetaDefender hash'leri eski paket icin.
echo ============================================================
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:SEVENZIP
echo.
echo === .7z paketi olustur ===

if not exist "%DIST%" (
    echo.
    echo [HATA] %DIST% klasoru yok. Once menu [1] ile olusturun.
    echo.
    pause
    goto MENU
)

call :FIND_7Z
if "%SZ%"=="" goto MENU

set "OUT=dist\Admin_PDF_Toolkit_Portable.7z"
if exist "%OUT%" (
    echo Eski %OUT% var, siliniyor...
    del "%OUT%"
)

echo.
echo ============================================================
echo   7z sikistirma basliyor (LZMA2, Ultra, solid mode^)
echo   Bu birkac dakika surebilir.
echo ============================================================
echo.

"%SZ%" a -t7z -mx=9 -m0=lzma2 -md=128m -ms=on -mmt=on -mfb=273 "%OUT%" "%DIST%"
if errorlevel 1 (
    echo.
    echo [HATA] Sikistirma basarisiz.
    pause
    goto MENU
)

echo.
echo ============================================================
echo   Hazir: %OUT%
for %%I in ("%OUT%") do echo   Boyut: %%~zI byte
echo.
echo   Hedef PC'de acmak icin 7-Zip gerekir.
echo   7-Zip yoksa: menu [4] ile Self-Extracting .exe tercih edin.
echo ============================================================
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:SFX
echo.
echo === Self-Extracting .exe olustur ===

if not exist "%DIST%" (
    echo.
    echo [HATA] %DIST% klasoru yok. Once menu [1] ile olusturun.
    echo.
    pause
    goto MENU
)

call :FIND_7Z
if "%SZ%"=="" goto MENU

set "OUT=dist\Admin_PDF_Toolkit_Portable.exe"
if exist "%OUT%" del "%OUT%"

echo.
echo ============================================================
echo   Self-Extracting EXE olusturuluyor (LZMA2 Ultra^)
echo   Hedef PC'de 7-Zip kurulumuna gerek YOK.
echo ============================================================
echo.

"%SZ%" a -t7z -mx=9 -m0=lzma2 -md=128m -ms=on -mmt=on -sfx7z.sfx "%OUT%" "%DIST%"
if errorlevel 1 (
    echo.
    echo [HATA] Olusturma basarisiz.
    pause
    goto MENU
)

echo.
echo ============================================================
echo   Hazir: %OUT%
for %%I in ("%OUT%") do echo   Boyut: %%~zI byte
echo.
echo   Bu .exe'yi hedef PC'ye kopyala, cift tikla — klasor acilir.
echo.
echo   ANTIVIRUS UYARISI: Yeni .exe icin "bilinmeyen yayinci" mesaji
echo   cikabilir. "Yine de calistir" / "Daha fazla bilgi" denirse acilir.
echo ============================================================
echo.
pause
goto MENU

REM ----------------------------------------------------------------------
:FIND_7Z
set "SZ="
if exist "C:\Program Files\7-Zip\7z.exe"        set "SZ=C:\Program Files\7-Zip\7z.exe"
if exist "C:\Program Files (x86)\7-Zip\7z.exe"  set "SZ=C:\Program Files (x86)\7-Zip\7z.exe"
if "%SZ%"=="" (
    where 7z >nul 2>&1
    if not errorlevel 1 set "SZ=7z"
)

if "%SZ%"=="" (
    echo.
    echo 7-Zip bulunamadi. Otomatik kurmak ister misiniz? (winget ile, ucretsiz)
    echo.
    choice /c YN /n /m "  Y=Evet  N=Hayir: "
    if errorlevel 2 (
        echo.
        echo Iptal edildi. 7-Zip elle kurup tekrar deneyebilirsiniz: https://7-zip.org/
        pause
        exit /b 0
    )
    where winget >nul 2>&1
    if errorlevel 1 (
        echo winget yok. https://7-zip.org adresinden manuel kurun.
        pause
        exit /b 0
    )
    winget install -e --id 7zip.7zip --accept-package-agreements --accept-source-agreements
    if exist "C:\Program Files\7-Zip\7z.exe" set "SZ=C:\Program Files\7-Zip\7z.exe"
    if "%SZ%"=="" (
        echo Kurulum tamam ama 7z.exe bulunamadi. Pencereyi kapatip tekrar deneyin.
        pause
        exit /b 0
    )
)
exit /b 0

REM ----------------------------------------------------------------------
:END
exit /b 0
