; ===========================================================================
;  Admin PDF Toolkit — Inno Setup wizard (profesyonel)
; ===========================================================================
;  Akış:
;    Dil seçimi (TR/EN)
;    -> Kullanıcı seçimi (Sadece ben / Tüm kullanıcılar)
;    -> [Mevcut kurulum varsa] Onar / Değiştir / Kaldır
;    -> Hoş Geldiniz
;    -> Lisans (AGPL-3.0, TR özet + EN resmi metin tek dosyada)
;    -> Kurulum Tipi (Tam / Asgari / Özel)
;    -> Bileşenler (ClamAV, EasyOCR opsiyonel)
;    -> Konum
;    -> İndirilecek Dosyalar (önizleme)
;    -> Hazır
;    -> İndirme (canlı bar, dosya başına)
;    -> Kurulum (7 adımlı progress)
;    -> Tamamlandı
;
;  UTF-8 BOM ile kaydedilmiştir (Türkçe karakterler).
; ===========================================================================

#define MyAppName       "Admin PDF Toolkit"
#define MyAppVersion    "1.13.1"
#define MyAppPublisher  "D Brand"
#define MyAppExeName    "Admin PDF Toolkit.exe"
#define MyAppId         "F4C7E2A1-7E2D-4B6A-91AC-PDFTOOLKIT01"

#define PythonVersion   "3.13.0"
#define PythonEmbedURL  "https://www.python.org/ftp/python/" + PythonVersion + "/python-" + PythonVersion + "-embed-amd64.zip"
#define GetPipURL       "https://bootstrap.pypa.io/get-pip.py"
#define ClamAVVersion   "1.4.2"
#define ClamAVZipURL    "https://github.com/Cisco-Talos/clamav/releases/download/clamav-" + ClamAVVersion + "/clamav-" + ClamAVVersion + ".win.x64.zip"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/AmrasElessar
AppSupportURL=https://github.com/AmrasElessar
AppUpdatesURL=https://github.com/AmrasElessar
DefaultDirName={localappdata}\AdminPDFToolkit
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
LicenseFile=LICENSE.installer.txt
OutputDir=dist
OutputBaseFilename=AdminPDFToolkit_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
ShowLanguageDialog=yes
UsePreviousAppDir=yes
UsePreviousSetupType=yes
UsePreviousTasks=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full";    Description: "{cm:TypeFull}"
Name: "minimal"; Description: "{cm:TypeMinimal}"
Name: "custom";  Description: "{cm:TypeCustom}"; Flags: iscustom

[Components]
Name: "app";     Description: "{cm:CompApp}";     Types: full minimal custom; Flags: fixed
Name: "clamav";  Description: "{cm:CompClamAV}";  Types: full
Name: "easyocr"; Description: "{cm:CompEasyOCR}"; Types: full

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "build\_pyinstaller_dist\Admin PDF Toolkit.exe"; DestDir: "{app}"; Flags: ignoreversion

Source: "dist\Admin_PDF_Toolkit_Portable\app.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\app_http.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\state.py";                DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\settings.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\pdf_converter.py";        DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\pdf_safety.py";           DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\requirements.txt";        DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\LICENSE";                 DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.tr.txt";                                          DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Admin_PDF_Toolkit_Portable\NOTICE.txt";              DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "dist\Admin_PDF_Toolkit_Portable\THIRD_PARTY_LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "dist\Admin_PDF_Toolkit_Portable\README.md";               DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

Source: "dist\Admin_PDF_Toolkit_Portable\core\*";      DestDir: "{app}\core";      Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\routers\*";   DestDir: "{app}\routers";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\pipelines\*"; DestDir: "{app}\pipelines"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\parsers\*";   DestDir: "{app}\parsers";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\static\*";    DestDir: "{app}\static";    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\scripts\*";   DestDir: "{app}\scripts";   Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\clamav"
Type: filesandordirs; Name: "{app}\_EasyOCR_models"

; ===========================================================================
; ÖZEL MESAJLAR — Türkçe & İngilizce
; ===========================================================================
[CustomMessages]
; -- Setup Types ----------------------------------------------------------
turkish.TypeFull=Tam kurulum (önerilen, ~1.2 GB — yapay zeka + antivirüs dahil)
turkish.TypeMinimal=Asgari kurulum (~700 MB — yapay zeka ve antivirüs HARİÇ)
turkish.TypeCustom=Özel kurulum (bileşenleri kendiniz seçin)
english.TypeFull=Full install (recommended, ~1.2 GB — AI + antivirus included)
english.TypeMinimal=Minimal install (~700 MB — without AI and antivirus)
english.TypeCustom=Custom install (pick components yourself)

; -- Components -----------------------------------------------------------
turkish.CompApp=Çekirdek uygulama (zorunlu)
turkish.CompClamAV=ClamAV antivirüs taraması (~350 MB) — Yüklenen PDF'leri ve içeriklerini virüse karşı tarar
turkish.CompEasyOCR=EasyOCR yapay zeka OCR (~150 MB) — Taranmış PDF'lerden metin çıkarır (Türkçe + İngilizce)
english.CompApp=Core application (required)
english.CompClamAV=ClamAV antivirus scanning (~350 MB) — Scans uploaded PDFs for viruses
english.CompEasyOCR=EasyOCR AI OCR (~150 MB) — Extracts text from scanned PDFs (Turkish + English)

; -- Transparency / download details page --------------------------------
turkish.DownloadListPageCaption=Tam Şeffaflık — İndirilecek Dosyalar
turkish.DownloadListPageDescription=Hangi bağlantıdan ne indirileceği tam olarak listelenmiştir
english.DownloadListPageCaption=Full Transparency — Files To Be Downloaded
english.DownloadListPageDescription=Exactly what is downloaded, from where, with full URLs

; -- Existing install action page -----------------------------------------
turkish.ActionPageCaption=Kurulum Algılandı
turkish.ActionPageDescription={#MyAppName} bu bilgisayarda zaten kurulu. Ne yapmak istersiniz?
turkish.ActionRepair=Onar — mevcut kurulumun üstüne yeniden kur
turkish.ActionRepairHint=Bozulan dosyaları onarmak, indirmeleri tamamlamak için
turkish.ActionModify=Değiştir — kurulum konumu veya bileşenleri güncelle
turkish.ActionModifyHint=Farklı klasöre taşımak, ClamAV/EasyOCR ekleme/çıkarma için
turkish.ActionUninstall=Kaldır — uygulamayı bilgisayardan tamamen sil
turkish.ActionUninstallHint=Uninstall sihirbazını çalıştırır, kullanıcı verilerini de silebilirsiniz
turkish.ExistingLocation=Mevcut konum: %1
english.ActionPageCaption=Existing Installation Detected
english.ActionPageDescription={#MyAppName} is already installed on this computer. What would you like to do?
english.ActionRepair=Repair — reinstall over the existing install
english.ActionRepairHint=Fix corrupted files, finish interrupted downloads
english.ActionModify=Modify — change install location or components
english.ActionModifyHint=Move to a different folder, add/remove ClamAV/EasyOCR
english.ActionUninstall=Uninstall — remove the application from this computer
english.ActionUninstallHint=Runs the uninstaller; you may also delete user data
english.ExistingLocation=Current location: %1

; -- Welcome / install step labels ----------------------------------------
turkish.PreparingDownload=Dosyalar indiriliyor...
turkish.ExtractingPython=Python ortamı kuruluyor...
turkish.InstallingPip=pip kuruluyor...
turkish.InstallingPackages=Python paketleri kuruluyor (PyTorch, EasyOCR, FastAPI — 5-10 dakika)...
turkish.ExtractingClamAV=ClamAV açılıyor...
turkish.UpdatingClamAV=ClamAV virüs imza veritabanı indiriliyor (~300 MB)...
turkish.PreparingOCR=EasyOCR yapay zeka modelleri indiriliyor (~150 MB)...
turkish.WritingShortcuts=Kısayollar yazılıyor...
turkish.SkippedClamAV=ClamAV atlandı (kullanıcı seçimi)
turkish.SkippedEasyOCR=EasyOCR atlandı (kullanıcı seçimi)
english.PreparingDownload=Downloading files...
english.ExtractingPython=Setting up Python runtime...
english.InstallingPip=Installing pip...
english.InstallingPackages=Installing Python packages (PyTorch, EasyOCR, FastAPI — 5-10 min)...
english.ExtractingClamAV=Extracting ClamAV...
english.UpdatingClamAV=Updating ClamAV virus signature database (~300 MB)...
english.PreparingOCR=Downloading EasyOCR AI models (~150 MB)...
english.WritingShortcuts=Writing shortcuts...
english.SkippedClamAV=ClamAV skipped (user choice)
english.SkippedEasyOCR=EasyOCR skipped (user choice)

; -- Uninstall ------------------------------------------------------------
turkish.UninstallCleanCaption=Kullanıcı Verilerini Sil
turkish.UninstallCleanPrompt=Kurulum klasörü içindeki indirilmiş Python, ClamAV ve EasyOCR dosyaları silinsin mi?%n%nEvet -> uygulama klasörü ve içindeki TÜM dosyalar silinir (~1.2 GB temizlenir)%nHayır -> sadece kayıt defteri ve kısayollar silinir, dosyalar kalır
english.UninstallCleanCaption=Delete User Data
english.UninstallCleanPrompt=Should the downloaded Python, ClamAV and EasyOCR files inside the install folder also be deleted?%n%nYes -> the app folder and ALL its contents are removed (~1.2 GB freed)%nNo -> only registry entries and shortcuts are removed; files stay

; ===========================================================================
; PASCAL SCRIPT
; ===========================================================================
[Code]
const
  EM_GETFIRSTVISIBLELINE = $00CE;
  EM_LINESCROLL          = $00B6;

var
  ActionPage: TInputOptionWizardPage;
  DownloadListPage: TWizardPage;
  DownloadPage: TDownloadWizardPage;
  ProgressPage: TOutputProgressWizardPage;
  ExistingInstallLocation: String;
  UserChoseUninstall: Boolean;
  LicenseScrolledToEnd: Boolean;
  ScrollToEndButton: TNewButton;
  LicenseHintLabel: TNewStaticText;
  LogMemo: TNewMemo;
  ProgressCancelButton: TNewButton;
  LastDLFile: String;
  LastDLLoggedComplete: Boolean;
  InstallCancelRequested: Boolean;

function GetExistingInstall(): String;
var
  KeyName, Location: String;
begin
  Result := '';
  KeyName := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1';
  if RegQueryStringValue(HKCU, KeyName, 'InstallLocation', Location) then
    Result := Location
  else if RegQueryStringValue(HKLM, KeyName, 'InstallLocation', Location) then
    Result := Location;
end;

function GetUninstallerPath(): String;
var
  KeyName, ExePath: String;
begin
  Result := '';
  KeyName := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1';
  if RegQueryStringValue(HKCU, KeyName, 'UninstallString', ExePath) then
    Result := ExePath
  else if RegQueryStringValue(HKLM, KeyName, 'UninstallString', ExePath) then
    Result := ExePath;
  Result := RemoveQuotes(Result);
end;

procedure CreateActionPage();
begin
  ActionPage := CreateInputOptionPage(
    wpWelcome,
    ExpandConstant('{cm:ActionPageCaption}'),
    ExpandConstant('{cm:ActionPageDescription}') + #13#10 +
      Format(ExpandConstant('{cm:ExistingLocation}'), [ExistingInstallLocation]),
    '',
    True,  // exclusive radio buttons
    False  // not list-style
  );
  ActionPage.Add(ExpandConstant('{cm:ActionRepair}'));
  ActionPage.Add(ExpandConstant('{cm:ActionModify}'));
  ActionPage.Add(ExpandConstant('{cm:ActionUninstall}'));
  ActionPage.Values[0] := True;
end;

function BuildTransparencyText(): String;
var
  S: String;
  NL: String;
begin
  NL := #13#10;
  S := 'Bu uygulama AÇIK KAYNAK ve ŞEFFAFTIR. Aşağıda kurulum sırasında' + NL;
  S := S + 'internetten indirilecek HER dosyanın tam adresi listelenmiştir.' + NL;
  S := S + 'Hiçbir gizli telemetri, analitik veya kullanıcı bilgisi yollanmaz.' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  1. Python 3.13 runtime' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  URL    : {#PythonEmbedURL}' + NL;
  S := S + '  Boyut  : ~25 MB' + NL;
  S := S + '  Kaynak : python.org (Python Software Foundation)' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  2. pip paket yöneticisi kurucusu' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  URL    : {#GetPipURL}' + NL;
  S := S + '  Boyut  : ~2 MB' + NL;
  S := S + '  Kaynak : PyPA (Python Packaging Authority)' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  3. ClamAV antivirüs binary  (opsiyonel)' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  URL    : {#ClamAVZipURL}' + NL;
  S := S + '  Boyut  : ~50 MB' + NL;
  S := S + '  Kaynak : Cisco Talos resmi GitHub release' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  4. ClamAV virüs imza veritabanı  (opsiyonel)' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  Sunucu   : database.clamav.net  (freshclam.exe ile)' + NL;
  S := S + '  Dosyalar : main.cvd, daily.cvd, bytecode.cvd' + NL;
  S := S + '  Boyut    : ~300 MB' + NL;
  S := S + '  Kaynak   : ClamAV resmi imza mirror sistemi' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  5. Python paketleri  (pip install -r requirements.txt)' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  Sunucu   : https://pypi.org  (Python Package Index)' + NL;
  S := S + '  Paketler :' + NL;
  S := S + '     • pymupdf            (PDF görüntüleme + düzenleme)' + NL;
  S := S + '     • pdfplumber         (PDF metin çıkarma)' + NL;
  S := S + '     • pdf2docx           (PDF -> Word dönüşümü)' + NL;
  S := S + '     • openpyxl           (Excel desteği)' + NL;
  S := S + '     • python-docx        (Word desteği)' + NL;
  S := S + '     • xhtml2pdf          (HTML -> PDF)' + NL;
  S := S + '     • Pillow             (görüntü işleme)' + NL;
  S := S + '     • fastapi            (web framework)' + NL;
  S := S + '     • uvicorn[standard]  (ASGI sunucu)' + NL;
  S := S + '     • python-multipart   (dosya yükleme)' + NL;
  S := S + '     • jinja2             (HTML template engine)' + NL;
  S := S + '     • easyocr            (OCR motoru)' + NL;
  S := S + '     • torch + torchvision (PyTorch — EasyOCR''ün AI altyapısı)' + NL;
  S := S + '     • cryptography       (HTTPS sertifikası üretmek için)' + NL;
  S := S + '     • pydantic + pydantic-settings' + NL;
  S := S + '  Boyut    : ~700 MB (PyTorch dahil)' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  6. EasyOCR yapay zeka modelleri  (opsiyonel)' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  URL''ler:' + NL;
  S := S + '    - https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/craft_mlt_25k.zip' + NL;
  S := S + '    - https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/latin_g2.zip' + NL;
  S := S + '  Boyut    : ~150 MB' + NL;
  S := S + '  Kaynak   : JaidedAI resmi GitHub' + NL;
  S := S + '  Kullanım : Yalnızca makinenizde, hiçbir veri dışarı yollanmaz.' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  TOPLAM' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  İndirilen toplam : ~1.2 GB' + NL;
  S := S + '  Tahmini süre     : 5-15 dakika (bağlantınıza bağlı)' + NL;
  S := S + '  Kurulum sonrası  : İnternet bağlantısı GEREKLİ DEĞİLDİR' + NL + NL;

  S := S + 'Bu liste açık kaynak ilkemizin bir parçasıdır.' + NL;
  S := S + 'Kaynak kod: https://github.com/AmrasElessar' + NL;
  S := S + 'Lisans   : GNU AGPL-3.0' + NL;

  Result := S;
end;

procedure CreateDownloadListPage();
var
  Memo: TNewMemo;
begin
  DownloadListPage := CreateCustomPage(
    wpSelectDir,
    ExpandConstant('{cm:DownloadListPageCaption}'),
    ExpandConstant('{cm:DownloadListPageDescription}')
  );

  Memo := TNewMemo.Create(DownloadListPage);
  Memo.Parent := DownloadListPage.Surface;
  Memo.Left := 0;
  Memo.Top := 0;
  Memo.Width := DownloadListPage.SurfaceWidth;
  Memo.Height := DownloadListPage.SurfaceHeight;
  Memo.ScrollBars := ssVertical;
  Memo.ReadOnly := True;
  Memo.WordWrap := False;
  Memo.Font.Name := 'Consolas';
  Memo.Font.Size := 8;
  Memo.Text := BuildTransparencyText();
end;

function LicenseIsScrolledToEnd(): Boolean;
var
  hLicense: HWND;
  TotalLines, FirstVisible, VisibleLines, ApproxLineHeight: Integer;
begin
  Result := True;
  hLicense := WizardForm.LicenseMemo.Handle;
  TotalLines := WizardForm.LicenseMemo.Lines.Count;
  if TotalLines <= 1 then exit;
  FirstVisible := SendMessage(hLicense, EM_GETFIRSTVISIBLELINE, 0, 0);
  ApproxLineHeight := WizardForm.LicenseMemo.Font.Size + 4;
  if ApproxLineHeight < 12 then ApproxLineHeight := 14;
  VisibleLines := WizardForm.LicenseMemo.ClientHeight div ApproxLineHeight;
  Result := (FirstVisible + VisibleLines) >= (TotalLines - 2);
end;

procedure EnableLicenseRadios();
begin
  if LicenseScrolledToEnd then exit;
  LicenseScrolledToEnd := True;
  WizardForm.LicenseAcceptedRadio.Enabled := True;
  WizardForm.LicenseNotAcceptedRadio.Enabled := True;
  if ScrollToEndButton <> nil then
    ScrollToEndButton.Visible := False;
  if LicenseHintLabel <> nil then
    LicenseHintLabel.Visible := False;
end;

procedure UpdateLicenseRadiosFromScroll();
begin
  if LicenseScrolledToEnd then exit;
  if LicenseIsScrolledToEnd() then
    EnableLicenseRadios();
end;

procedure OnScrollToEndButtonClick(Sender: TObject);
begin
  SendMessage(WizardForm.LicenseMemo.Handle, EM_LINESCROLL, 0, 30000);
  EnableLicenseRadios();
end;

procedure LicenseScrollNotify(Sender: TObject);
begin
  UpdateLicenseRadiosFromScroll();
end;

procedure LicenseKeyNotify(Sender: TObject; var Key: Word; Shift: TShiftState);
begin
  UpdateLicenseRadiosFromScroll();
end;

// ---------------------------------------------------------------------------
//  Install-phase log + cancel button (canli kayit, kullanici durdurma)
// ---------------------------------------------------------------------------

procedure LogLine(const S: String);
var
  Stamp: String;
begin
  if LogMemo = nil then exit;
  Stamp := GetDateTimeString('hh:nn:ss', '/', ':');
  LogMemo.Lines.Add('[' + Stamp + '] ' + S);
  // Scroll-to-bottom
  SendMessage(LogMemo.Handle, $0115 {WM_VSCROLL}, 7 {SB_BOTTOM}, 0);
end;

procedure LogStep(StepNum, TotalSteps: Integer; const Title: String);
begin
  LogLine('[' + IntToStr(StepNum) + '/' + IntToStr(TotalSteps) + '] ' + Title);
end;

procedure LogOK(const Title: String);
begin
  LogLine('   ✓ ' + Title);
end;

function OnDLProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  // Inno calls this repeatedly during download. We only log meaningful
  // transitions: start of a new file, and completion.
  Result := not InstallCancelRequested;
  if (FileName <> '') and (FileName <> LastDLFile) then begin
    LogLine('Indiriliyor: ' + ExtractFileName(FileName));
    LastDLFile := FileName;
    LastDLLoggedComplete := False;
  end;
  if (ProgressMax > 0) and (Progress >= ProgressMax) and (not LastDLLoggedComplete) then begin
    LogOK(ExtractFileName(LastDLFile) + ' tamamlandi (~' + IntToStr(ProgressMax div 1048576) + ' MB)');
    LastDLLoggedComplete := True;
  end;
end;

procedure OnInstallCancelClick(Sender: TObject);
begin
  if InstallCancelRequested then exit;
  if MsgBox(
       'Kurulumu durdurmak istediginizden emin misiniz?' + #13#10 + #13#10 +
       'Mevcut adim (paket indirme/kurma) tamamlandiktan sonra durdurulacak,' + #13#10 +
       'kalan adimlar atlanacak. Yarim kurulum gerirebilirsiniz.',
       mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then begin
    InstallCancelRequested := True;
    ProgressCancelButton.Enabled := False;
    ProgressCancelButton.Caption := 'Durduruluyor...';
    LogLine('!! Iptal istendi - mevcut adim bittikten sonra durdurulacak');
  end;
end;

procedure CreateInstallLogAndCancel();
var
  MemoTop, MemoHeight, BtnHeight: Integer;
begin
  // ProgressPage.Surface ust yarisinda Inno'nun MsgLabel + ProgressBar
  // var; alt yarisina log memo + iptal butonu koyalim.
  BtnHeight := ScaleY(26);
  MemoTop := ScaleY(80);
  MemoHeight := ProgressPage.SurfaceHeight - MemoTop - BtnHeight - ScaleY(8);
  if MemoHeight < ScaleY(120) then MemoHeight := ScaleY(120);

  LogMemo := TNewMemo.Create(WizardForm);
  LogMemo.Parent := ProgressPage.Surface;
  LogMemo.Left := 0;
  LogMemo.Top := MemoTop;
  LogMemo.Width := ProgressPage.SurfaceWidth;
  LogMemo.Height := MemoHeight;
  LogMemo.ScrollBars := ssVertical;
  LogMemo.ReadOnly := True;
  LogMemo.WordWrap := False;
  LogMemo.Font.Name := 'Consolas';
  LogMemo.Font.Size := 8;

  ProgressCancelButton := TNewButton.Create(WizardForm);
  ProgressCancelButton.Parent := ProgressPage.Surface;
  ProgressCancelButton.Caption := 'Kurulumu Durdur';
  ProgressCancelButton.OnClick := @OnInstallCancelClick;
  ProgressCancelButton.Width := ScaleX(160);
  ProgressCancelButton.Height := BtnHeight;
  ProgressCancelButton.Left := ProgressPage.SurfaceWidth - ProgressCancelButton.Width;
  ProgressCancelButton.Top := LogMemo.Top + LogMemo.Height + ScaleY(6);
end;


procedure InitializeWizard();
begin
  ExistingInstallLocation := GetExistingInstall();
  if ExistingInstallLocation <> '' then
    CreateActionPage();
  CreateDownloadListPage();
  DownloadPage := CreateDownloadPage(
    SetupMessage(msgWizardPreparing),
    ExpandConstant('{cm:PreparingDownload}'),
    @OnDLProgress
  );
  ProgressPage := CreateOutputProgressPage(
    SetupMessage(msgWizardPreparing),
    ''
  );
  CreateInstallLogAndCancel();

  // License scroll-to-accept gating (acik kaynak seffaflik prensibi):
  // Accept ve Decline radyolari pasif baslar. Lisans memosunda scroll
  // sona ininca her iki radyo aktif olur, Inno'nun standart akisi calisir.
  LicenseScrolledToEnd := False;
  WizardForm.LicenseAcceptedRadio.Enabled := False;
  WizardForm.LicenseNotAcceptedRadio.Enabled := False;

  // Scroll algilamak icin: memo'daki desteklenen tum etkilesim eventlerini
  // dinle (Inno Pascal Script TMemo/TNewMemo'da OnMouseXxx exposed degil).
  WizardForm.LicenseMemo.OnClick   := @LicenseScrollNotify;
  WizardForm.LicenseMemo.OnChange  := @LicenseScrollNotify;
  WizardForm.LicenseMemo.OnKeyDown := @LicenseKeyNotify;
  WizardForm.LicenseMemo.OnKeyUp   := @LicenseKeyNotify;
  WizardForm.LicenseMemo.OnEnter   := @LicenseScrollNotify;
  WizardForm.LicenseMemo.OnExit    := @LicenseScrollNotify;
end;

procedure SetupLicenseScrollHelpers();
var
  PageWidth, BtnWidth, BtnHeight, HintTop: Integer;
begin
  if ScrollToEndButton <> nil then exit;

  // Memo'yu biraz kisalt, altina hint + buton yerlestir
  WizardForm.LicenseMemo.Height := WizardForm.LicenseMemo.Height - ScaleY(48);

  PageWidth := WizardForm.LicenseMemo.Width;
  HintTop := WizardForm.LicenseMemo.Top + WizardForm.LicenseMemo.Height + ScaleY(4);
  BtnWidth := ScaleX(260);
  BtnHeight := ScaleY(22);

  LicenseHintLabel := TNewStaticText.Create(WizardForm);
  LicenseHintLabel.Parent := WizardForm.LicenseMemo.Parent;
  LicenseHintLabel.Caption := 'Acik kaynak / seffaflik: Kabul butonu lisansi sonuna kadar okudugunuzda aktif olur.';
  LicenseHintLabel.AutoSize := False;
  LicenseHintLabel.WordWrap := True;
  LicenseHintLabel.Left := WizardForm.LicenseMemo.Left;
  LicenseHintLabel.Top := HintTop;
  LicenseHintLabel.Width := PageWidth - BtnWidth - ScaleX(8);
  LicenseHintLabel.Height := BtnHeight;
  LicenseHintLabel.Font.Style := [fsItalic];

  ScrollToEndButton := TNewButton.Create(WizardForm);
  ScrollToEndButton.Parent := WizardForm.LicenseMemo.Parent;
  ScrollToEndButton.Caption := 'Lisansi sonuna kaydir';
  ScrollToEndButton.OnClick := @OnScrollToEndButtonClick;
  ScrollToEndButton.Left := WizardForm.LicenseMemo.Left + PageWidth - BtnWidth;
  ScrollToEndButton.Top := HintTop;
  ScrollToEndButton.Width := BtnWidth;
  ScrollToEndButton.Height := BtnHeight;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpLicense then begin
    SetupLicenseScrollHelpers();
    if not LicenseScrolledToEnd then begin
      SendMessage(WizardForm.LicenseMemo.Handle, EM_LINESCROLL, 0, -10000);
      // Cok kisa bir lisans memo'ya sigarsa scroll yapilamayacagi icin
      // hemen kontrol et — kucuk lisanslarda kullaniciyi kilitlemeyelim.
      UpdateLicenseRadiosFromScroll();
    end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  // If user chose Uninstall, skip everything between ActionPage and the end
  if (ActionPage <> nil) and (ActionPage.Values[2]) then begin
    if (PageID <> wpWelcome) and (PageID <> ActionPage.ID) and (PageID <> wpFinished) then
      Result := True;
  end;
end;

procedure RunUninstaller();
var
  UninstExe: String;
  ResultCode: Integer;
begin
  UninstExe := GetUninstallerPath();
  if FileExists(UninstExe) then
    Exec(UninstExe, '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  // ActionPage handling
  if (ActionPage <> nil) and (CurPageID = ActionPage.ID) then begin
    if ActionPage.Values[2] then begin
      // Uninstall — run uninstaller and exit installer
      UserChoseUninstall := True;
      RunUninstaller();
      WizardForm.Close;
      Result := False;
      exit;
    end;
    // Repair / Modify — set install dir to existing, then continue normally
    if (ActionPage.Values[0] or ActionPage.Values[1]) and (ExistingInstallLocation <> '') then
      WizardForm.DirEdit.Text := ExistingInstallLocation;
  end;

  // Downloads happen when leaving wpReady
  if CurPageID = wpReady then begin
    DownloadPage.Clear;
    DownloadPage.Add('{#PythonEmbedURL}', 'python_embed.zip', '');
    DownloadPage.Add('{#GetPipURL}',      'get-pip.py',       '');
    if IsComponentSelected('clamav') then
      DownloadPage.Add('{#ClamAVZipURL}', 'clamav.zip',       '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        SuppressibleMsgBox(AddPeriod(GetExceptionMessage), mbCriticalError, MB_OK, IDOK);
        Result := False;
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure ExtractZipPS(const ZipPath, DestDir: String);
var
  ResultCode: Integer;
  PS: String;
begin
  ForceDirectories(DestDir);
  PS := 'Expand-Archive -Force -Path "' + ZipPath + '" -DestinationPath "' + DestDir + '"';
  Exec('powershell.exe',
       '-NoProfile -ExecutionPolicy Bypass -Command "' + PS + '"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure WritePthFile(const PyDir: String);
var
  PthPath, Content: String;
begin
  PthPath := PyDir + '\python313._pth';
  Content := 'python313.zip' + #13#10 +
             '.' + #13#10 +
             'Lib\site-packages' + #13#10 + #13#10 +
             'import site' + #13#10;
  SaveStringToFile(PthPath, Content, False);
end;

procedure WriteStarterBat(const AppDir: String);
var
  Bat: String;
begin
  Bat :=
    '@echo off' + #13#10 +
    'chcp 65001 >nul' + #13#10 +
    'cd /d "%~dp0"' + #13#10 +
    'title Admin PDF Toolkit - Sunucu' + #13#10 +
    'set "PYTHONHOME="' + #13#10 +
    'set "PYTHONPATH=%~dp0;%~dp0python\Lib\site-packages"' + #13#10 +
    'set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"' + #13#10 +
    'start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"' + #13#10 +
    '"%~dp0python\python.exe" "%~dp0app.py"' + #13#10 +
    'pause >nul' + #13#10;
  SaveStringToFile(AppDir + '\Admin PDF Toolkit Baslat.bat', Bat, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, PyDir, TmpDir, ClamAVDir: String;
  ResultCode, TotalSteps, StepNum: Integer;
begin
  if CurStep = ssPostInstall then begin
    AppDir := ExpandConstant('{app}');
    PyDir := AppDir + '\python';
    ClamAVDir := AppDir + '\clamav';
    TmpDir := ExpandConstant('{tmp}');

    TotalSteps := 4; // Python extract, pip, packages, shortcuts
    if IsComponentSelected('clamav')  then TotalSteps := TotalSteps + 2;
    if IsComponentSelected('easyocr') then TotalSteps := TotalSteps + 1;
    StepNum := 0;
    InstallCancelRequested := False;

    ProgressPage.Show;
    LogLine('Kurulum baslatildi (hedef: ' + AppDir + ')');
    LogLine('Toplam adim sayisi: ' + IntToStr(TotalSteps));
    LogLine('');

    try
      // 1) Python embeddable
      if not InstallCancelRequested then begin
        Inc(StepNum);
        ProgressPage.SetText(ExpandConstant('{cm:ExtractingPython}'), '');
        ProgressPage.SetProgress(StepNum, TotalSteps);
        LogStep(StepNum, TotalSteps, 'Python ortami kuruluyor...');
        ForceDirectories(PyDir);
        ExtractZipPS(TmpDir + '\python_embed.zip', PyDir);
        WritePthFile(PyDir);
        LogOK('Python 3.13 embeddable kuruldu');
      end;

      // 2) pip
      if not InstallCancelRequested then begin
        Inc(StepNum);
        ProgressPage.SetText(ExpandConstant('{cm:InstallingPip}'), '');
        ProgressPage.SetProgress(StepNum, TotalSteps);
        LogStep(StepNum, TotalSteps, 'pip paket yoneticisi kuruluyor...');
        Exec(PyDir + '\python.exe',
             '"' + TmpDir + '\get-pip.py" --no-warn-script-location',
             PyDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
        if ResultCode = 0 then LogOK('pip kuruldu')
        else LogLine('   !! pip exit ' + IntToStr(ResultCode));
      end;

      // 3) Python packages
      if not InstallCancelRequested then begin
        Inc(StepNum);
        ProgressPage.SetText(ExpandConstant('{cm:InstallingPackages}'), '');
        ProgressPage.SetProgress(StepNum, TotalSteps);
        LogStep(StepNum, TotalSteps, 'Python paketleri kuruluyor (PyTorch + EasyOCR + FastAPI...)');
        LogLine('   Bu adim 5-10 dakika surebilir, lutfen bekleyin');
        Exec(PyDir + '\python.exe',
             '-m pip install --isolated --no-user --ignore-installed --no-warn-script-location --disable-pip-version-check -r "' + AppDir + '\requirements.txt"',
             AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
        if ResultCode = 0 then LogOK('Tum Python paketleri kuruldu')
        else LogLine('   !! pip install exit ' + IntToStr(ResultCode));
      end;

      // 4) ClamAV (optional)
      if IsComponentSelected('clamav') and not InstallCancelRequested then begin
        Inc(StepNum);
        ProgressPage.SetText(ExpandConstant('{cm:ExtractingClamAV}'), '');
        ProgressPage.SetProgress(StepNum, TotalSteps);
        LogStep(StepNum, TotalSteps, 'ClamAV antivirus binary aciliyor...');
        ForceDirectories(ClamAVDir);
        ExtractZipPS(TmpDir + '\clamav.zip', ClamAVDir);
        LogOK('ClamAV binary acildi');

        if not InstallCancelRequested then begin
          Inc(StepNum);
          ProgressPage.SetText(ExpandConstant('{cm:UpdatingClamAV}'), '');
          ProgressPage.SetProgress(StepNum, TotalSteps);
          LogStep(StepNum, TotalSteps, 'ClamAV virus imza veritabani indiriliyor (~300 MB)...');
          Exec(PyDir + '\python.exe',
               '"' + AppDir + '\scripts\setup_clamav.py"',
               AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
          if ResultCode = 0 then LogOK('ClamAV imza DB hazir')
          else LogLine('   !! setup_clamav.py exit ' + IntToStr(ResultCode));
        end;
      end else if IsComponentSelected('clamav') then begin
        LogLine('ClamAV adimi atlandi (iptal)');
      end;

      // 5) EasyOCR (optional)
      if IsComponentSelected('easyocr') and not InstallCancelRequested then begin
        Inc(StepNum);
        ProgressPage.SetText(ExpandConstant('{cm:PreparingOCR}'), '');
        ProgressPage.SetProgress(StepNum, TotalSteps);
        LogStep(StepNum, TotalSteps, 'EasyOCR yapay zeka modelleri indiriliyor (~150 MB)...');
        Exec(PyDir + '\python.exe',
             '-c "import easyocr; easyocr.Reader([''tr'',''en''], gpu=False, verbose=False, model_storage_directory=r''' + AppDir + '\_EasyOCR_models'', download_enabled=True)"',
             AppDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
        if ResultCode = 0 then LogOK('EasyOCR modelleri yuklendi')
        else LogLine('   !! EasyOCR exit ' + IntToStr(ResultCode));
      end else if IsComponentSelected('easyocr') then begin
        LogLine('EasyOCR adimi atlandi (iptal)');
      end;

      // 6) Baslat.bat fallback (always, even after partial cancel)
      Inc(StepNum);
      ProgressPage.SetText(ExpandConstant('{cm:WritingShortcuts}'), '');
      ProgressPage.SetProgress(StepNum, TotalSteps);
      LogStep(StepNum, TotalSteps, 'Kisayollar yaziliyor...');
      WriteStarterBat(AppDir);
      LogOK('Baslat.bat hazir');

      LogLine('');
      if InstallCancelRequested then
        LogLine('!! Kurulum kullanici tarafindan durduruldu (kismi).')
      else
        LogLine('Kurulum basariyla tamamlandi.');
    finally
      ProgressPage.Hide;
    end;
  end;
end;

// ===========================================================================
// UNINSTALL: ask whether to delete the install folder's downloaded files
// ===========================================================================
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
  Reply: Integer;
begin
  if CurUninstallStep = usUninstall then begin
    AppDir := ExpandConstant('{app}');
    Reply := SuppressibleMsgBox(
      ExpandConstant('{cm:UninstallCleanPrompt}'),
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2,
      IDNO
    );
    if Reply = IDYES then begin
      DelTree(AppDir + '\python',          True, True, True);
      DelTree(AppDir + '\clamav',          True, True, True);
      DelTree(AppDir + '\_EasyOCR_models', True, True, True);
    end;
  end;
end;
