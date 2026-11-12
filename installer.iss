#define MyVer "1.0.2"
#define MyApp "REX 7 ENGINE REAL EX"
[Setup]
AppId={{5B7E2C41-7A0D-4F3E-9C2B-9D4A6B2E81F3}
AppName={#MyApp}
AppVersion={#MyVer}
AppVerName={#MyApp} {#MyVer}
AppPublisher=EX Inc./HYPERION DIGITAL
AppPublisherURL=https://github.com/Teobokki/rex7-engine
AppCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoVersion={#MyVer}.0
VersionInfoCompany=EX Inc.
VersionInfoCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoProductName={#MyApp}
VersionInfoDescription={#MyApp} Setup
DefaultDirName={localappdata}\Programs\{#MyApp}
DefaultGroupName={#MyApp}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=REX-7-ENGINE-REAL-EX-Setup-{#MyVer}
SetupIconFile=assets\logo.ico
WizardImageFile=assets\wizard_large.bmp,assets\wizard_large2x.bmp
WizardSmallImageFile=assets\wizard_small.bmp,assets\wizard_small2x.bmp
UninstallDisplayIcon={app}\{#MyApp}.exe
UninstallDisplayName={#MyApp}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyApp}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "wv2lib\webruntime_setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebRuntime

[Icons]
Name: "{group}\{#MyApp}"; Filename: "{app}\{#MyApp}.exe"; IconFilename: "{app}\{#MyApp}.exe"
Name: "{group}\Uninstall {#MyApp}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyApp}"; Filename: "{app}\{#MyApp}.exe"; IconFilename: "{app}\{#MyApp}.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\webruntime_setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing the web runtime (needs internet)..."; Flags: waituntilterminated; Check: NeedsWebRuntime
Filename: "{app}\{#MyApp}.exe"; Description: "Launch {#MyApp}"; Flags: nowait postinstall skipifsilent

[Code]
const WRT = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasPv(Root: Integer; Key: String): Boolean;
var V: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

function NeedsWebRuntime(): Boolean;
begin
  Result := not (HasPv(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WRT) or
                 HasPv(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WRT) or
                 HasPv(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WRT));
end;
