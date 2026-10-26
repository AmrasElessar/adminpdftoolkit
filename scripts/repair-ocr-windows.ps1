# Admin PDF Toolkit - check and repair the bundled OCR (Windows package).
# 1. Every file in ocr\ is compared with the SHA-256 recorded in
#    ocr\manifest.json when the package was built (works offline).
# 2. Damaged or missing language data is downloaded again over HTTPS and
#    accepted ONLY if its SHA-256 matches the manifest exactly.
# 3. A damaged program file (exe/dll) is not downloaded: extract the package
#    zip again instead.
# Messages are ASCII on purpose: Windows PowerShell 5.1 reads scripts as ANSI.
param([Parameter(Mandatory = $true)][string]$OcrDir)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$manifestPath = Join-Path $OcrDir 'manifest.json'
if (-not (Test-Path $manifestPath)) {
    Write-Host 'OCR klasoru veya manifest.json yok. Paketi yeniden cikarin.'
    Write-Host 'The OCR folder or manifest.json is missing. Extract the package again.'
    exit 1
}
$manifest = Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json
$root = (Resolve-Path $OcrDir).Path

function Test-File([string]$rel, [string]$expected) {
    $path = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
    return ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() -eq $expected.ToLower())
}

$bad = @()
foreach ($entry in $manifest.files.PSObject.Properties) {
    if (-not (Test-File $entry.Name $entry.Value)) { $bad += $entry.Name }
}
if ($bad.Count -eq 0) {
    Write-Host 'OCR dosyalari saglam. / OCR files are intact.'
    exit 0
}

Write-Host 'Bozuk veya eksik dosyalar / Damaged or missing files:'
$bad | ForEach-Object { Write-Host "  $_" }

$unfixable = @()
foreach ($rel in $bad) {
    $key = $rel -replace '\.traineddata$', ''
    $source = $manifest.sources.$key
    if (-not $source -or -not $source.url.StartsWith('https://')) { $unfixable += $rel; continue }
    $expected = $manifest.files.$rel
    $target = Join-Path $root $rel
    $part = "$target.part"
    Write-Host "Indiriliyor / Downloading: $($source.url)"
    try {
        Invoke-WebRequest -Uri $source.url -OutFile $part -UseBasicParsing
    } catch {
        Write-Host "  Indirilemedi (ag engelli olabilir). / Download failed (the network may block it)."
        $unfixable += $rel
        continue
    }
    $got = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $expected.ToLower()) {
        Remove-Item -Force $part
        Write-Host "  REDDEDILDI: dosya beklenen SHA-256 ile eslesmiyor. / REJECTED: SHA-256 does not match."
        $unfixable += $rel
        continue
    }
    Move-Item -Force $part $target
    Write-Host "  Onarildi / Repaired: $rel"
}

if ($unfixable.Count -gt 0) {
    Write-Host ''
    Write-Host 'Onarilamayan dosyalar var. Paket zip dosyasini yeniden cikarin.'
    Write-Host 'Some files could not be repaired. Extract the package zip again.'
    exit 1
}
Write-Host ''
Write-Host 'OCR onarildi. Uygulama aciksa kapatip yeniden baslatin.'
Write-Host 'OCR repaired. Restart Admin PDF Toolkit if it is running.'
