@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Admin PDF Toolkit - Gelistirme Sunucusu (by Engin)

rem =======================================================================
rem  Admin PDF Toolkit by Engin -- Gelistirme sunucusu baslatici
rem
rem  Yeni PC'de ilk kez calistirilirsa:
rem    1. Python yuklu mu kontrol et (yoksa winget ile kurmayi onerir)
rem    2. requirements.txt'teki paketleri pip ile kur
rem    3. PDF editor asset'lerini (pdf.js + Noto/DejaVu fontlar) indir
rem    4. Sunucuyu baslat ve tarayiciyi ac
rem
rem  ONEMLI: Bu .bat dosyasi pure ASCII olmali. Turkce harfler sadece
rem  echo satirlarinda kullanilabilir (chcp 65001 sonrasi UTF-8 aktif).
rem  Title, rem, etiket adlari, komut/argumanlar ASCII kalmali; aksi
rem  halde cmd.exe (CP-857/CP-1254 OEM codepage ile) bayt dizilerini
rem  yanlis cozer ve "X is not recognized as a command" hatalari verir.
rem =======================================================================

rem --- Python var mi? ---
where python >nul 2>&1
if errorlevel 1 goto NO_PYTHON

rem --- Paketler daha once kuruldu mu? ---
if exist ".deps_ok" goto CHECK_ASSETS

echo.
echo ============================================================
echo   Admin PDF Toolkit -- Ilk kurulum
echo ============================================================
echo   Gerekli Python paketleri indirilip kurulacak.
echo   Bu islem yalniz ILK seferde calisir ve birkac dakika surer.
echo   Internet baglantisi gerekli.
echo ============================================================
echo.
python -m pip install --upgrade pip
if errorlevel 1 goto PIP_FAIL
python -m pip install -r requirements.txt
if errorlevel 1 goto PIP_FAIL
echo ok > .deps_ok
echo.
echo Python paketleri tamamlandi.
echo.

:CHECK_ASSETS
rem --- PDF editor asset'leri (pdf.js + fontlar) var mi? ---
if exist "static\pdfjs\pdf.min.mjs" if exist "static\fonts\NotoSans-Regular.ttf" goto CHECK_CLAMAV

echo.
echo ============================================================
echo   PDF Editor asset'leri indiriliyor (~11 MB)
echo ============================================================
echo   pdf.js (sayfa render) + Noto/DejaVu fontlar
echo   Bu islem yalniz ILK seferde calisir.
echo ============================================================
echo.
python "scripts\setup_editor_assets.py"
if errorlevel 1 (
    echo.
    echo UYARI: Asset indirme basarisiz. PDF editor calismayabilir.
    echo Manuel olarak su komutu calistirabilirsiniz:
    echo    python scripts\setup_editor_assets.py
    echo.
    timeout /t 5 >nul
)
echo.

:CHECK_CLAMAV
rem --- ClamAV motoru + imza veritabani hazir mi? ---
rem Hem binary (clamscan.exe) hem en az bir imza dosyasi (main.cvd/main.cld)
rem varsa hazir kabul edilir; degilse setup_clamav.py her iki adimi da yapar.
if exist "clamav\clamscan.exe" (
    if exist "clamav\database\main.cvd" goto RUN_SERVER
    if exist "clamav\database\main.cld" goto RUN_SERVER
)

echo.
echo ============================================================
echo   ClamAV antivirus hazirlaniyor
echo ============================================================
echo   1. Binary indirme  (~40 MB, varsa atlanir)
echo   2. Imza veritabani (~300 MB, ilk kez gerekli)
echo   Toplam: ilk seferde ~1-2 dakika, sonraki acilista atlanir.
echo   Internet'siz ortamda atlanabilir; o zaman yapisal kontrol +
echo   Windows Defender ile devam edilir.
echo ============================================================
echo.
python "scripts\setup_clamav.py"
if errorlevel 1 (
    echo.
    echo UYARI: ClamAV hazirlanamadi. PDF guvenlik taramasi yapisal
    echo kontrol + Windows Defender ile devam eder.
    echo Manuel kurulum icin:  python scripts\setup_clamav.py
    echo.
    timeout /t 5 >nul
)
echo.

:RUN_SERVER
echo ============================================================
echo   Admin PDF Toolkit baslatiliyor...
echo   URL: http://127.0.0.1:8000
echo ============================================================
echo.
rem Tarayici arka planda acilsin, kucuk bir gecikme ile
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"
python app.py
echo.
echo Sunucu durdu. Kapatmak icin bir tusa basin...
pause >nul
goto END

:NO_PYTHON
echo.
echo ============================================================
echo   [HATA] Bu bilgisayarda Python yuklu degil
echo ============================================================
echo.

rem Windows Paket Yoneticisi (winget) varsa otomatik kurulum onerelim
where winget >nul 2>&1
if errorlevel 1 goto MANUAL_PYTHON

echo   Windows'un paket yoneticisi (winget) kullanilabilir.
echo   Python 3.13 otomatik kurmak ister misiniz?
echo.
choice /c EH /n /m "   Kuralim mi? [E=Evet  H=Hayir]: "
if errorlevel 2 goto MANUAL_PYTHON
echo.
echo Kuruluyor, lutfen bekleyin...
winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements --silent
echo.
echo ============================================================
echo   Python kuruldu.
echo   Lutfen bu pencereyi KAPATIP bu .bat dosyasina
echo   tekrar cift tiklayin.
echo ============================================================
pause
goto END

:MANUAL_PYTHON
echo   Elle kurmak icin iki yol:
echo.
echo     1. Microsoft Store'u acin, "Python 3.13" arayip kurun (en kolay)
echo     2. veya https://www.python.org/downloads/ adresinden indirin
echo.
echo   Kurulum sirasinda "Add Python to PATH" secenegini
echo   mutlaka isaretleyin.
echo.
echo   Kurulum bittikten sonra bu .bat'e tekrar cift tiklayin.
echo.
pause
goto END

:PIP_FAIL
echo.
echo ============================================================
echo   [HATA] Paketler indirilemedi
echo ============================================================
echo   Internet baglantinizi kontrol edin ve tekrar deneyin.
echo   Sirket guvenlik duvari pip'i engelliyor olabilir.
echo ============================================================
echo.
pause
goto END

:END
