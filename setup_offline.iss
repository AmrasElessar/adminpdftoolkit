; ===========================================================================
;  Admin PDF Toolkit - Inno Setup wizard (OFFLINE EDITION)
; ===========================================================================
;  Her sey installer .exe icinde gomulu: Python embeddable, tum pip paketleri
;  (PyTorch + EasyOCR + FastAPI vs.), ClamAV binary, ClamAV virus imza DB,
;  EasyOCR yapay zeka modelleri. Kurulum sirasinda INTERNET GEREKMEZ.
;
;  Hedef: kurumsal firewall arkasinda olan is bilgisayarlari.
;
;  Boyut: ~1-1.4 GB .exe (LZMA2 ile sikistirilmis). Online versiyonla ayni
;  wizard akisi; sadece indirme adimi yerine yerel dosyalardan ekleme yapilir.
;
;  UTF-8 BOM ile kaydedilir.
; ===========================================================================

#define MyAppName       "Admin PDF Toolkit"
#define MyAppVersion    "1.0.0"
#define MyAppPublisher  "Engin"
#define MyAppExeName    "Admin PDF Toolkit.exe"
#define MyAppId         "F4C7E2A1-7E2D-4B6A-91AC-PDFTOOLKIT01"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} (Offline)
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
OutputBaseFilename=AdminPDFToolkit_Setup_Offline
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=2
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
DiskSpanning=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Native tray launcher
Source: "build\_pyinstaller_dist\Admin PDF Toolkit.exe"; DestDir: "{app}"; Flags: ignoreversion

; --- App code (root files) -------------------------------------------------
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

; --- App code (directories) -----------------------------------------------
Source: "dist\Admin_PDF_Toolkit_Portable\core\*";      DestDir: "{app}\core";      Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\routers\*";   DestDir: "{app}\routers";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\pipelines\*"; DestDir: "{app}\pipelines"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\parsers\*";   DestDir: "{app}\parsers";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\static\*";    DestDir: "{app}\static";    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Admin_PDF_Toolkit_Portable\scripts\*";   DestDir: "{app}\scripts";   Flags: ignoreversion recursesubdirs createallsubdirs

; --- Python embeddable + all pip packages (the big one, ~1.3 GB) ---------
Source: "dist\Admin_PDF_Toolkit_Portable\python\*";    DestDir: "{app}\python";    Flags: ignoreversion recursesubdirs createallsubdirs

; --- ClamAV antivirus binary + signature DB (optional, ~700 MB) -----------
Source: "dist\Admin_PDF_Toolkit_Portable\clamav\*";    DestDir: "{app}\clamav";    Flags: ignoreversion recursesubdirs createallsubdirs; Components: clamav

; --- EasyOCR AI models (optional, ~95 MB) ---------------------------------
Source: "dist\Admin_PDF_Toolkit_Portable\_EasyOCR_models\*"; DestDir: "{app}\_EasyOCR_models"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: easyocr

[Types]
Name: "full";    Description: "{cm:TypeFull}"
Name: "minimal"; Description: "{cm:TypeMinimal}"
Name: "custom";  Description: "{cm:TypeCustom}"; Flags: iscustom

[Components]
Name: "app";     Description: "{cm:CompApp}";     Types: full minimal custom; Flags: fixed
Name: "clamav";  Description: "{cm:CompClamAV}";  Types: full
Name: "easyocr"; Description: "{cm:CompEasyOCR}"; Types: full

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
Type: filesandordirs; Name: "{app}\logs"

[CustomMessages]
turkish.TypeFull=Tam kurulum (önerilen, ~2 GB — yapay zeka + antivirüs dahil)
turkish.TypeMinimal=Asgari kurulum (~1.3 GB — yapay zeka ve antivirüs HARİÇ)
turkish.TypeCustom=Özel kurulum (bileşenleri kendiniz seçin)
english.TypeFull=Full install (recommended, ~2 GB — AI + antivirus included)
english.TypeMinimal=Minimal install (~1.3 GB — without AI and antivirus)
english.TypeCustom=Custom install (pick components yourself)

turkish.CompApp=Çekirdek uygulama + Python runtime (zorunlu)
turkish.CompClamAV=ClamAV antivirüs + virüs imza veritabanı (~700 MB)
turkish.CompEasyOCR=EasyOCR yapay zeka modelleri (~95 MB)
english.CompApp=Core application + Python runtime (required)
english.CompClamAV=ClamAV antivirus + virus signature database (~700 MB)
english.CompEasyOCR=EasyOCR AI models (~95 MB)

turkish.OfflinePageCaption=Tam Şeffaflık — Paketin İçeriği
turkish.OfflinePageDescription=Bu OFFLINE installer'da her şey içeride, internet gerekmez
turkish.WritingShortcuts=Kısayollar yazılıyor...
english.OfflinePageCaption=Full Transparency — Bundled Contents
english.OfflinePageDescription=This OFFLINE installer contains everything; no internet required
english.WritingShortcuts=Writing shortcuts...

turkish.UninstallCleanCaption=Kullanıcı Verilerini Sil
turkish.UninstallCleanPrompt=Kurulum klasörü içindeki Python, ClamAV ve EasyOCR dosyaları silinsin mi?%n%nEvet -> uygulama klasörü ve içindeki TÜM dosyalar silinir (~2 GB temizlenir)%nHayır -> sadece kayıt defteri ve kısayollar silinir, dosyalar kalır
english.UninstallCleanPrompt=Should the Python, ClamAV and EasyOCR files inside the install folder also be deleted?%n%nYes -> the app folder and ALL its contents are removed (~2 GB freed)%nNo -> only registry entries and shortcuts are removed; files stay
english.UninstallCleanCaption=Delete User Data

[Code]
const
  EM_GETFIRSTVISIBLELINE = $00CE;
  EM_LINESCROLL          = $00B6;

var
  ActionPage: TInputOptionWizardPage;
  OfflineInfoPage: TWizardPage;
  ExistingInstallLocation: String;
  LicenseScrolledToEnd: Boolean;
  ScrollToEndButton: TNewButton;
  LicenseHintLabel: TNewStaticText;

// -- Existing install detection (Repair/Modify/Uninstall) -----------------

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
    'Kurulum Algılandı',
    '{#MyAppName} bu bilgisayarda zaten kurulu. Ne yapmak istersiniz?' + #13#10 +
      'Mevcut konum: ' + ExistingInstallLocation,
    '',
    True,
    False
  );
  ActionPage.Add('Onar — mevcut kurulumun üstüne yeniden kur');
  ActionPage.Add('Değiştir — kurulum konumu veya bileşenleri güncelle');
  ActionPage.Add('Kaldır — uygulamayı bilgisayardan tamamen sil');
  ActionPage.Values[0] := True;
end;

// -- Offline transparency page --------------------------------------------

procedure CreateOfflineInfoPage();
var
  Memo: TNewMemo;
  S, NL: String;
begin
  OfflineInfoPage := CreateCustomPage(
    wpSelectDir,
    ExpandConstant('{cm:OfflinePageCaption}'),
    ExpandConstant('{cm:OfflinePageDescription}')
  );

  NL := #13#10;
  S := 'Bu OFFLINE installer''da kurulum sirasinda internetten' + NL;
  S := S + 'HIC BIR SEY indirilmez. Asagidaki bilesenler installer.exe' + NL;
  S := S + '''nin icinde gomulu olarak gelir:' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  Pakette Olanlar' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL + NL;

  S := S + '  ✓ Python 3.13 runtime + standart kutuphane' + NL;
  S := S + '    Boyut: ~25 MB (sikistirilmamis)' + NL + NL;

  S := S + '  ✓ Python paketleri (zaten yuklenmis):' + NL;
  S := S + '       pymupdf, pdfplumber, pdf2docx, openpyxl,' + NL;
  S := S + '       python-docx, xhtml2pdf, Pillow,' + NL;
  S := S + '       fastapi, uvicorn, python-multipart, jinja2,' + NL;
  S := S + '       easyocr + torch + torchvision (PyTorch),' + NL;
  S := S + '       cryptography, pydantic + pydantic-settings' + NL;
  S := S + '    Boyut: ~1.3 GB' + NL + NL;

  S := S + '  ✓ ClamAV antivirus binary + 2026 imza veritabani' + NL;
  S := S + '    Boyut: ~700 MB' + NL + NL;

  S := S + '  ✓ EasyOCR yapay zeka modelleri (Turkce + Ingilizce)' + NL;
  S := S + '    Boyut: ~95 MB' + NL + NL;

  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL;
  S := S + '  Internet Gereksinimi: HIC YOK' + NL;
  S := S + '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' + NL + NL;
  S := S + '  Kurulum tamamen offline calisir. Kurumsal firewall' + NL;
  S := S + '  arkasinda bile sorunsuz kurulur. Hicbir dis sunucuya' + NL;
  S := S + '  baglanilmaz.' + NL + NL;

  S := S + '  Kaynak kod: https://github.com/AmrasElessar' + NL;
  S := S + '  Lisans   : GNU AGPL-3.0' + NL;

  Memo := TNewMemo.Create(OfflineInfoPage);
  Memo.Parent := OfflineInfoPage.Surface;
  Memo.Left := 0;
  Memo.Top := 0;
  Memo.Width := OfflineInfoPage.SurfaceWidth;
  Memo.Height := OfflineInfoPage.SurfaceHeight;
  Memo.ScrollBars := ssVertical;
  Memo.ReadOnly := True;
  Memo.WordWrap := False;
  Memo.Font.Name := 'Consolas';
  Memo.Font.Size := 8;
  Memo.Text := S;
end;

// -- License scroll-to-accept gating --------------------------------------

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
  if ScrollToEndButton <> nil then ScrollToEndButton.Visible := False;
  if LicenseHintLabel <> nil then LicenseHintLabel.Visible := False;
end;

procedure UpdateLicenseRadiosFromScroll();
begin
  if LicenseScrolledToEnd then exit;
  if LicenseIsScrolledToEnd() then EnableLicenseRadios();
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

procedure SetupLicenseScrollHelpers();
var
  PageWidth, BtnWidth, BtnHeight, HintTop: Integer;
begin
  if ScrollToEndButton <> nil then exit;
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

// -- Wizard setup ----------------------------------------------------------

procedure InitializeWizard();
begin
  ExistingInstallLocation := GetExistingInstall();
  if ExistingInstallLocation <> '' then
    CreateActionPage();
  CreateOfflineInfoPage();

  LicenseScrolledToEnd := False;
  WizardForm.LicenseAcceptedRadio.Enabled := False;
  WizardForm.LicenseNotAcceptedRadio.Enabled := False;
  WizardForm.LicenseMemo.OnClick   := @LicenseScrollNotify;
  WizardForm.LicenseMemo.OnChange  := @LicenseScrollNotify;
  WizardForm.LicenseMemo.OnKeyDown := @LicenseKeyNotify;
  WizardForm.LicenseMemo.OnKeyUp   := @LicenseKeyNotify;
  WizardForm.LicenseMemo.OnEnter   := @LicenseScrollNotify;
  WizardForm.LicenseMemo.OnExit    := @LicenseScrollNotify;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpLicense then begin
    SetupLicenseScrollHelpers();
    if not LicenseScrolledToEnd then begin
      SendMessage(WizardForm.LicenseMemo.Handle, EM_LINESCROLL, 0, -10000);
      UpdateLicenseRadiosFromScroll();
    end;
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
  if (ActionPage <> nil) and (CurPageID = ActionPage.ID) then begin
    if ActionPage.Values[2] then begin
      RunUninstaller();
      WizardForm.Close;
      Result := False;
      exit;
    end;
    if (ActionPage.Values[0] or ActionPage.Values[1]) and (ExistingInstallLocation <> '') then
      WizardForm.DirEdit.Text := ExistingInstallLocation;
  end;
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
begin
  if CurStep = ssPostInstall then begin
    WriteStarterBat(ExpandConstant('{app}'));
  end;
end;

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
      DelTree(AppDir + '\logs',            True, True, True);
    end;
  end;
end;
