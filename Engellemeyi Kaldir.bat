@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Admin PDF Toolkit - Engellemeyi Kaldir (by Engin)

rem =======================================================================
rem  Windows MotW (Mark of the Web) temizleyici
rem
rem  GitHub'dan indirilen ZIP'in icindeki tum dosyalara Windows otomatik
rem  olarak "internet'ten geldi" isareti basar (NTFS Zone.Identifier).
rem  Bu yuzden .bat dosyalari ilk acilista "yayimci dogrulanamadi"
rem  uyarisi verir.
rem
rem  Bu script repodaki TUM dosyalardan bu isareti kaldirir. Bir kez
rem  calistirip kapatabilirsiniz; artik baska uyari almayacaksiniz.
rem =======================================================================

echo.
echo ============================================================
echo   Engellemeyi Kaldir
echo ============================================================
echo   Bu klasordeki tum dosyalardan "internet'ten indirildi"
echo   isareti kaldirilacak. Bu islem GUVENLI:
echo      * Hicbir dosya degistirilmez
echo      * Sadece NTFS Zone.Identifier akisi silinir
echo      * Tum bat/ps/exe'ler imza uyarisi vermeden calisir
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$root = '%~dp0'; $files = Get-ChildItem -Path $root -Recurse -File -Force; $n = $files.Count; Write-Host ('  Toplam dosya: ' + $n); $files | Unblock-File; Write-Host '  Engelleme kaldirildi.' -ForegroundColor Green"

if errorlevel 1 (
    echo.
    echo [HATA] PowerShell calismadi veya yeterli izin yok.
    echo Manuel cozum: bat dosyasina sag tikla, Ozellikler, en altta
    echo "Engellemeyi Kaldir / Unblock" kutusunu isaretleyin, Tamam.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Tamamlandi.
echo ============================================================
echo   Artik "Sunucuyu Baslat.bat" cift tikladiginizda uyari almayacaksiniz.
echo ============================================================
echo.
pause
