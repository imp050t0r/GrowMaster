#define MyAppName "GrowMaster"
#define MyAppVersion "1.24.8"
#define MyAppPublisher "GrowMaster"
#define MyAppURL "https://github.com/imp050t0r/GrowMaster"

[Setup]
AppId={{8AEE9542-AD11-4FB4-937C-F690935FE33C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\GrowMaster
DefaultGroupName=GrowMaster
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=GrowMaster-Setup-{#MyAppVersion}
SetupIconFile=assets\GrowMaster.ico
UninstallDisplayIcon={app}\GrowMaster.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible

[Languages]
Name: "slovenian"; MessagesFile: "compiler:Languages\Slovenian.isl"

[Tasks]
Name: "desktopicon"; Description: "Ustvari ikono GrowMaster na namizju"; GroupDescription: "Bližnjice:"; Flags: checkedonce
