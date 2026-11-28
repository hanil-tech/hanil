; 한일 판금 전개 설치 프로그램 (Inno Setup 6)
;   iscc /DMyVersion=1.0.0 packaging\setup.iss          전체판
;   iscc /DMyVersion=1.0.0 /DLite packaging\setup.iss    전개 전용판 (따로 설치 — 둘 다 깔 수 있음)
#ifndef MyVersion
  #define MyVersion "1.0.0"
#endif
#ifdef Lite
  #define AppTitle "한일 판금 전개 (전개 전용)"
  #define AppExe "HanilUnfoldLite"
  #define AppGuid "{{3A9E6D52-8B17-4F0C-A2C4-5E7B91D0F3A8}"
#else
  #define AppTitle "한일 판금 전개"
  #define AppExe "HanilUnfold"
  #define AppGuid "{{6C0B7B0E-2F5B-4C1E-9F64-6A1C1E5A7D21}"
#endif

[Setup]
AppId={#AppGuid}
AppName={#AppTitle}
AppVersion={#MyVersion}
AppVerName={#AppTitle} {#MyVersion}
VersionInfoVersion={#MyVersion}
VersionInfoProductName={#AppTitle}
AppPublisher=한일특장(주)
AppPublisherURL=https://www.hanil-steel.com
AppSupportURL=https://www.hanil-steel.com
AppCopyright=Copyright (C) 2025-2026 한일특장(주)
VersionInfoCompany=한일특장(주)
VersionInfoCopyright=Copyright (C) 2025-2026 한일특장(주)
DefaultDirName={autopf}\{#AppExe}
DefaultGroupName={#AppTitle}
UninstallDisplayIcon={app}\{#AppExe}.exe
OutputDir=..\dist
OutputBaseFilename={#AppExe}-Setup-{#MyVersion}
SetupIconFile=..\hanil_unfold\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 관리자 권한 없이도 설치할 수 있게 (내 계정에만 설치)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; Flags: checkedonce
Name: "assoc"; Description: "STEP 파일(.stp, .step)을 마우스 오른쪽 [연결 프로그램] 에 추가"; Flags: checkedonce

[Files]
Source: "..\dist\{#AppExe}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppTitle}"; Filename: "{app}\{#AppExe}.exe"
Name: "{group}\제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppTitle}"; Filename: "{app}\{#AppExe}.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}.exe\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}.exe"" ""%1"""; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.stp\OpenWithList\{#AppExe}.exe"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.step\OpenWithList\{#AppExe}.exe"; Flags: uninsdeletekey; Tasks: assoc

[Run]
Filename: "{app}\{#AppExe}.exe"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent
