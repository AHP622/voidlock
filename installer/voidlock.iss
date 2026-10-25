; VOIDLOCK installer (Inno Setup 6). Built by the release workflow:  ISCC /DAppVersion=1.5.0 installer\voidlock.iss
; Installs for the current user only (no administrator rights needed), so the in-app updater can replace VoidLock.exe.
; Your data lives in %APPDATA%\VoidLock and is never touched by installing or updating.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8F3C2D17-6B4A-4E59-9D21-5A7E0C3B9F64}
AppName=VOIDLOCK
AppVersion={#AppVersion}
AppPublisher=AHP622
AppPublisherURL=https://github.com/AHP622/voidlock
DefaultDirName={autopf}\VoidLock
DefaultGroupName=VOIDLOCK
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64
OutputDir=..\dist
OutputBaseFilename=VoidLock-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\VoidLock.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableDirPage=auto
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\VoidLock.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\VOIDLOCK"; Filename: "{app}\VoidLock.exe"
Name: "{autodesktop}\VOIDLOCK"; Filename: "{app}\VoidLock.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VoidLock.exe"; Description: "Launch VOIDLOCK"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; remove everything the program registered with Windows (it does not start again after uninstalling)
Filename: "{app}\VoidLock.exe"; Parameters: "--clean-hosts"; Flags: runhidden; RunOnceId: "CleanHosts"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN VoidLockWatchdog /F"; Flags: runhidden; RunOnceId: "DelWatchdog"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN VoidLockGuardAdmin /F"; Flags: runhidden; RunOnceId: "DelAdminTask"
Filename: "{sys}\reg.exe"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v VoidLockGuard /f"; Flags: runhidden; RunOnceId: "DelRunGuard"
Filename: "{sys}\reg.exe"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v VoidLockTray /f"; Flags: runhidden; RunOnceId: "DelRunTray"

[Code]
procedure StopVoidLock();
var
  rc: Integer;
begin
  { the program and its guard keep VoidLock.exe open; they start again after the install (the watchdog / sign-in task) }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM VoidLock.exe', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Sleep(700);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopVoidLock();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopVoidLock();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    if MsgBox('Also delete your VOIDLOCK data (study hours, tests, settings, backups)?' + #13#10 +
              'Choose No to keep it for a future install.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\VoidLock'), True, True, True);
  end;
end;
