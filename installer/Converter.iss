#define MyAppName "Converter"
#define MyAppExeName "Converter.exe"
#define MyAppPublisher "Enryuuh"
#define MyAppURL "https://github.com/Enryuuh/Converter"
#define MyAppVersion GetEnv("APP_VERSION")
#if MyAppVersion == ""
#define MyAppVersion "1.3.10"
#endif

[Setup]
AppId={{8F933911-9731-4F44-90D2-51A863F0E56C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases/latest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ConverterSetup
SetupIconFile=..\assets\converter-logo.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "contextmenu"; Description: "Agregar clic derecho > Convertir con Converter"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "portableflag"; Description: "Activar modo portable en esta instalacion"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "profileassoc"; Description: "Asociar archivos .converterprofile"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Abrir carpeta de imagenes"; Filename: "{userdocs}\Pictures"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\*\shell\Converter"; ValueType: string; ValueName: ""; ValueData: "Convertir con {#MyAppName}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Converter"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\Converter\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Converter"; ValueType: string; ValueName: ""; ValueData: "Convertir con {#MyAppName}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Converter"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Converter\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\.converterprofile"; ValueType: string; ValueName: ""; ValueData: "Converter.Profile"; Flags: uninsdeletekey; Tasks: profileassoc
Root: HKCU; Subkey: "Software\Classes\Converter.Profile"; ValueType: string; ValueName: ""; ValueData: "Perfil de Converter"; Flags: uninsdeletekey; Tasks: profileassoc
Root: HKCU; Subkey: "Software\Classes\Converter.Profile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey; Tasks: profileassoc
Root: HKCU; Subkey: "Software\Classes\Converter.Profile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: profileassoc

[Run]
Filename: "{cmd}"; Parameters: "/C type nul > ""{app}\portable.flag"""; Flags: runhidden; Tasks: portableflag
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
