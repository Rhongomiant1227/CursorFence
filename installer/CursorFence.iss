#define MyAppName "CursorFence"
#define MyAppPublisher "CursorFence contributors"
#define MyAppURL "https://github.com/Rhongomiant1227/CursorFence"
#define MyAppExeName "CursorFence.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.3.0"
#endif

[Setup]
AppId={{B9E3A8B8-5AF6-4BF4-A9AF-8A1A4B4C4E4A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=CursorFence-Installer
SetupIconFile=..\resources\CursorFence.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=CursorFence Windows cursor boundary utility installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
Uninstallable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\CursorFence\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CursorFence"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall CursorFence"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CursorFence"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CursorFence"; Flags: nowait postinstall skipifsilent
