; 한일 판금 전개 설치 프로그램 (Inno Setup 6)
;   iscc /DMyVersion=1.0.0 packaging\setup.iss     (unfold 폴더에서, PyInstaller 다음에)
#ifndef MyVersion
  #define MyVersion "1.0.0"
#endif

[Setup]
AppId={{6C0B7B0E-2F5B-4C1E-9F64-6A1C1E5A7D21}
AppName=한일 판금 전개
AppVersion={#MyVersion}
AppPublisher=Hanil
DefaultDirName={autopf}\HanilUnfold
DefaultGroupName=한일 판금 전개
UninstallDisplayIcon={app}\HanilUnfold.exe
OutputDir=..\dist
OutputBaseFilename=HanilUnfold-Setup
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
Source: "..\dist\HanilUnfold\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\한일 판금 전개"; Filename: "{app}\HanilUnfold.exe"
Name: "{group}\제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\한일 판금 전개"; Filename: "{app}\HanilUnfold.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\HanilUnfold.exe\shell\open\command"; ValueType: string; ValueData: """{app}\HanilUnfold.exe"" ""%1"""; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.stp\OpenWithList\HanilUnfold.exe"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.step\OpenWithList\HanilUnfold.exe"; Flags: uninsdeletekey; Tasks: assoc

[Run]
Filename: "{app}\HanilUnfold.exe"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent
