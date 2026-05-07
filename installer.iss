#define MyAppName "CATX Systems Torch RCON Tool"
#define MyAppVersion "23.4.2.0"
#define MyAppPublisher "CATX Systems LLC"
#define MyAppExeName "CATX-Systems-Torch-RCON-Tool.exe"

[Setup]
AppId={{8E1F4C64-6A4E-4C8B-9A7A-CATXTORCHRCON}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CATX Systems\Torch RCON Tool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=CATX-Systems-Torch-RCON-Tool-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=logo.ico

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Dirs]
Name: "{localappdata}\CATX\TorchRemoteAdmin"
Name: "{localappdata}\CATX\TorchRemoteAdmin\Settings"
Name: "{localappdata}\CATX\TorchRemoteAdmin\Logs"

[Files]
Source: "dist\CATX-Systems-Torch-RCON-Tool.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DeleteSettingsOnUninstall: Boolean;

function InitializeUninstall(): Boolean;
begin
  DeleteSettingsOnUninstall :=
    MsgBox(
      'Do you want to delete saved settings, logs, and cached runtime files from AppData?' #13#10#13#10 +
      'Folder:' #13#10 +
      ExpandConstant('{localappdata}\CATX\TorchRemoteAdmin'),
      mbConfirmation,
      MB_YESNO
    ) = IDYES;

  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DeleteSettingsOnUninstall then
    begin
      DelTree(ExpandConstant('{localappdata}\CATX\TorchRemoteAdmin'), True, True, True);
    end;
  end;
end;
