#define MyAppName "GrowMaster"
#define MyAppVersion "1.24.0"
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

[Files]
Source: "..\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".git\*,.env,frontend\node_modules\*,frontend\dist\*,tmp\*,*.db,backups\*,installer\output\*,installer\GrowMaster.iss,installer\Start-GrowMaster.ps1,installer\Stop-GrowMaster.ps1,installer\Move-GrowMasterData.ps1,installer\assets\*"
Source: "Start-GrowMaster.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop-GrowMaster.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Move-GrowMasterData.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\GrowMaster.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GrowMaster"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Start-GrowMaster.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\GrowMaster.ico"
Name: "{group}\GrowMaster - prestavi podatke"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Move-GrowMasterData.ps1"" ""%1"""; WorkingDir: "{app}"; IconFilename: "{app}\GrowMaster.ico"
Name: "{autodesktop}\GrowMaster"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Start-GrowMaster.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\GrowMaster.ico"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\growmaster-storage"; ValueType: string; ValueName: ""; ValueData: "URL:GrowMaster data storage"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\growmaster-storage"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\growmaster-storage\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\GrowMaster.ico,0"
Root: HKA; Subkey: "Software\Classes\growmaster-storage\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """powershell.exe"" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Move-GrowMasterData.ps1"" ""%1"""

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Start-GrowMaster.ps1"" -Build -DataDirectory ""{code:GetDataDirectory}"""; Description: "Zaženi GrowMaster"; Flags: postinstall skipifsilent nowait

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Stop-GrowMaster.ps1"""; Flags: runhidden; RunOnceId: "StopGrowMaster"

[Code]
var
  DataDirectoryPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  DataDirectoryPage := CreateInputDirPage(
    wpSelectDir,
    'Mapa za podatke',
    'Izberi, kam naj GrowMaster shrani podatke.',
    'V izbrani mapi bosta podmapi za PostgreSQL bazo in varnostne kopije. Priporočen je lokalni disk, ki je vedno priključen.',
    False,
    ''
  );
  DataDirectoryPage.Add('');
  DataDirectoryPage.Values[0] := ExpandConstant('{localappdata}\GrowMasterData');
end;

function ExistingEnvironmentFile: Boolean;
begin
  Result := FileExists(ExpandConstant('{userappdata}\GrowMaster\.env'));
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = DataDirectoryPage.ID) and ExistingEnvironmentFile;
end;

function GetDataDirectory(Param: String): String;
begin
  Result := DataDirectoryPage.Values[0];
end;
