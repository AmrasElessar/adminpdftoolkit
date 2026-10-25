# Admin PDF Toolkit - OCR setup for Windows.
# 1. Installs Tesseract (UB-Mannheim build) with winget if it isn't installed.
# 2. Adds the Turkish language data. If the Tesseract folder lacks tur.traineddata,
#    the installed languages plus tur are put in a per-user folder that the app
#    picks up automatically (%LOCALAPPDATA%\AdminPDFToolkit\tessdata), so no
#    administrator rights are needed for this step.
# Messages are ASCII on purpose: Windows PowerShell 5.1 reads scripts as ANSI.

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$WikiUrl = 'https://github.com/UB-Mannheim/tesseract/wiki'
$DataUrl = 'https://github.com/tesseract-ocr/tessdata_fast/raw/main'
$UserData = Join-Path $env:LOCALAPPDATA 'AdminPDFToolkit\tessdata'
$Languages = @('tur', 'eng', 'osd')

function Find-Tesseract {
    $cmd = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, (Join-Path $env:LOCALAPPDATA 'Programs')) | Where-Object { $_ }
    foreach ($root in $roots) {
        $exe = Join-Path $root 'Tesseract-OCR\tesseract.exe'
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

$exe = Find-Tesseract
if (-not $exe) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host 'Tesseract OCR indiriliyor ve kuruluyor (winget)... / Installing Tesseract OCR...'
        Write-Host 'Windows yonetici izni isteyebilir. / Windows may ask for administrator approval.'
        winget install --exact --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
        $exe = Find-Tesseract
    }
    if (-not $exe) {
        Write-Host ''
        Write-Host 'Tesseract otomatik kurulamadi. Acilan sayfadan Windows kurulum dosyasini indirin;'
        Write-Host 'kurulumda "Additional language data" altindan Turkish secin.'
        Write-Host 'Tesseract could not be installed automatically. Download the installer from the page'
        Write-Host 'that opens and tick Turkish under "Additional language data".'
        Start-Process $WikiUrl
        exit 1
    }
}
Write-Host "Tesseract: $exe"

$system = Join-Path (Split-Path $exe) 'tessdata'
if (Test-Path (Join-Path $system 'tur.traineddata')) {
    Write-Host 'Turkce dil paketi zaten kurulu. / Turkish language data is already installed.'
    exit 0
}

New-Item -ItemType Directory -Force -Path $UserData | Out-Null
if (Test-Path $system) {
    Get-ChildItem -Path $system -Filter '*.traineddata' | ForEach-Object {
        $target = Join-Path $UserData $_.Name
        if (-not (Test-Path $target)) { Copy-Item $_.FullName $target }
    }
}
foreach ($lang in $Languages) {
    $target = Join-Path $UserData "$lang.traineddata"
    if (Test-Path $target) { continue }
    Write-Host "Dil paketi indiriliyor / Downloading language data: $lang"
    $part = "$target.part"
    Invoke-WebRequest -Uri "$DataUrl/$lang.traineddata" -OutFile $part -UseBasicParsing
    Move-Item -Force $part $target
}

$env:TESSDATA_PREFIX = $UserData
& $exe --list-langs
Write-Host ''
Write-Host 'OCR hazir. Admin PDF Toolkit acikse kapatip yeniden baslatin.'
Write-Host 'OCR is ready. Restart Admin PDF Toolkit if it is running.'
