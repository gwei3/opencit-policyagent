; Script generated by the HM NIS Edit Script Wizard.

; HM NIS Edit Wizard helper defines
!define PRODUCT_NAME "Policy Agent"
!define PRODUCT_VERSION "1.0"
!define PRODUCT_PUBLISHER "Intel Corporation"
!define PRODUCT_WEB_SITE "http://www.intel.com"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; MUI 1.67 compatible ------
!include "MUI.nsh"
!include "x64.nsh"
!include "nsDialogs.nsh"
;Changes to read ini file
!include "FileFunc.nsh"
!include "WinMessages.nsh"
!include "TextFunc.nsh"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Welcome page
!insertmacro MUI_PAGE_WELCOME
; License page
;!insertmacro MUI_PAGE_LICENSE "license.txt"
; Directory page
!define MUI_PAGE_CUSTOMFUNCTION_SHOW DirectoryPageShow
!insertmacro MUI_PAGE_DIRECTORY
LangString TITLE ${LANG_ENGLISH} "Installing"
LangString SUBTITLE ${LANG_ENGLISH} "Please wait while Policy Agent is being installed"
Page Custom getVolumeStart getVolumeEnd
Page Custom getSizeStart getSizeEnd
Page Custom getDriveLetterStart getDriveLetterEnd
;Page Custom bitlockerstart bitlockerend
; Instfiles page
!insertmacro MUI_PAGE_INSTFILES
; Finish page
!define MUI_FINISHPAGE_NOAUTOCLOSE
;!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
;!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

; Language files
!insertmacro MUI_LANGUAGE "English"
!insertmacro ConfigWrite

; MUI end ------

Name "${PRODUCT_NAME}"
OutFile "policyagent-setup.exe"
InstallDir "$PROGRAMFILES\Intel\Policy Agent"
ShowInstDetails show
ShowUnInstDetails show

Var /Global drive
VAR /Global size
VAR /Global diskNumber
Var /Global radiobutton1_state
Var /Global radiobutton2_state
Var /Global property
Var /Global property_file
Var /Global INIFILE
Var /Global uniqueDrive
Var /Global KMSPROXY_SERVER
Var /Global KMSPROXY_SERVER_PORT

Function getVolumeStart
!insertmacro MUI_HEADER_TEXT $(TITLE) $(SUBTITLE)
ReadINIStr $drive "$INIFILE" "POLICY_AGENT" "DriveUsedForPartition"

${If} $drive != ""
      StrCpy $radiobutton1_state ${BST_CHECKED}
${EndIf}

${If} $drive == ""
      StrCpy $radiobutton2_state ${BST_CHECKED}
${EndIf}

nsDialogs::Create /NOUNLOAD 1018
Pop $0
${If} $radiobutton2_state == ${BST_CHECKED}
	StrCpy $drive $uniqueDrive
${EndIf}
${NSD_CreateLabel} 0 0 100% 20% "'$drive' drive is to be used for encryption"

${If} $radiobutton1_state == ${BST_CHECKED}
    ${NSD_CreateLabel} 0 10% 50% 10% "Using drive to create new partition."
${EndIf}

${If} $radiobutton2_state == ${BST_CHECKED}
	${NSD_CreateLabel} 0 10% 50% 10% "Using drive as new partition"
${EndIf}

nsDialogs::Show
FunctionEnd

Function getVolumeEnd

SetOverwrite try
SetOutPath "$INSTDIR\scripts"
File "scripts\ps_utility.ps1"

nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\ps_utility.ps1" "isDriveExist" $drive  '
pop $R1
pop $R2

;MessageBox mb_ok $R2
${If} $R2 == "False$\r$\n"
      MessageBox mb_ok "Drive $drive does not exist. Please provide another drive letter."
      Abort
${EndIf}

nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\ps_utility.ps1" "getDiskNumber" $drive  '
pop $R1
pop $R2

Strcpy $diskNumber $R2
;MessageBox mb_ok $R2

${If} $radiobutton1_state == ${BST_CHECKED}
      SetOutPath "$INSTDIR\logs"
      FileOpen $9 diskpartscript.txt w ;Opens an Empty File and fills it
      FileWrite $9 "select disk $diskNumber$\r$\n"
      FileWrite $9 "list partition"
      FileClose $9 ;Closes the filled file

      nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\ps_utility.ps1" "getPartitionCount"  '
      pop $R1
      pop $R2
      ;MessageBox mb_ok $R2
      ${If} $R2 == "4$\r$\n"
            MessageBox mb_ok "New primary partition could not be created. Please proceed with other option."
            Abort
      ${EndIf}
${EndIf}

Strcpy $property "MOUNT_LOCATION"
Strcpy $property_file "$INSTDIR\configuration\policyagent_nt.properties"
SetOutPath "$INSTDIR\scripts"
File "scripts\update_property.ps1"
File "scripts\bitlocker_drive_setup.ps1"
SetOutPath "$INSTDIR\configuration"
File "configuration\policyagent_nt.properties"

ReadINIStr $KMSPROXY_SERVER "$INIFILE" "POLICY_AGENT" "KMSPROXY_SERVER"
ReadINIStr $KMSPROXY_SERVER_PORT "$INIFILE" "POLICY_AGENT" "KMSPROXY_SERVER_PORT"
${If} $KMSPROXY_SERVER != ""
      ${ConfigWrite} "$INSTDIR\configuration\policyagent_nt.properties" "KMSPROXY_SERVER=" "$KMSPROXY_SERVER" $0
${EndIf}

${If} $KMSPROXY_SERVER_PORT != ""
     ${ConfigWrite} "$INSTDIR\configuration\policyagent_nt.properties" "KMSPROXY_SERVER_PORT=" "$KMSPROXY_SERVER_PORT" $0
${EndIf}

${If} $radiobutton2_state == ${BST_CHECKED}
      StrCpy $0 $SYSDIR 1
      ${If} $drive == $0
            MessageBox MB_OK "Specified drive is OS drive. Please provide another drive letter."
            Abort
${EndIf}

      ${If} ${RunningX64}
            ${DisableX64FSRedirection}

			#Update MOUNT_LOCATION property
			nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\update_property.ps1" "$property_file" "$property" "$drive"  '
			nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\bitlocker_drive_setup.ps1" $drive  '

            ${EnableX64FSRedirection}
      ${EndIf}
      MessageBox mb_ok "Bitlocker drive setup complete. Please check log file '$INSTDIR\logs\bitlockersetup.log' for more details."
${EndIf}
FunctionEnd

Function getSizeStart
!insertmacro MUI_HEADER_TEXT $(TITLE) $(SUBTITLE)
ReadINIStr $size "$INIFILE" "POLICY_AGENT" "SizeOfNewPartition"
${If} $size == ""
        MessageBox MB_OK "Size can't be left blank. Please configure SizeOfNewPartition attribute under POLICY_AGENT section of system.ini"
        Abort
${EndIf}
${If} $radiobutton2_state == ${BST_CHECKED}
      Abort
${EndIf}

SetOutPath "$INSTDIR\logs"
FileOpen $9 diskpartscript.txt w ;Opens an Empty File and fills it
FileWrite $9 "select volume $drive$\r$\n"
FileWrite $9 "shrink querymax"
FileClose $9 ;Closes the filled file

nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\ps_utility.ps1" "getFreeSpace"  '
pop $R1
pop $R2

IntCmp $R2 $size equal lessthan morethan
equal:
  Goto done
morethan:
  Goto done
lessthan:
  MessageBox MB_OK "Maximum amount of reclaimable size is $R2, SizeOfNewPartition value under POLICY_AGENT section of system.ini should be less than $R2"
  Abort
done:

;${If} ${$R2} < ${$size}
;      MessageBox MB_OK "Maximum amount of reclaimable size is $R2, SizeOfNewPartition value under POLICY_AGENT section of system.ini should be less than $R2"
;      Abort
;${EndIf}
;${If} ${$R2} > ${$size}
;	MessageBox MB_OK "Space is available"
;${EndIf}

nsDialogs::Create /NOUNLOAD 1018
Pop $0
${NSD_CreateLabel} 0 0 100% 20% "Maximum amount of reclaimable size : $R2"
${NSD_CreateLabel} 0 10% 50% 10% "Size to shrink(MB) : $size"
nsDialogs::Show
FunctionEnd

Function getSizeEnd
${If} $size == ""
        MessageBox MB_OK "Size can't be left blank. Please provide size to continue."
        Abort
${EndIf}
FunctionEnd

Function getDriveLetterStart
!insertmacro MUI_HEADER_TEXT $(TITLE) $(SUBTITLE)
ReadINIStr $uniqueDrive "$INIFILE" "POLICY_AGENT" "DriveUsedForEncryption"
${If} $uniqueDrive == ""
        StrCpy $uniqueDrive "Z"
${EndIf}

${If} $radiobutton2_state == ${BST_CHECKED}
      Abort
${EndIf}

nsDialogs::Create /NOUNLOAD 1018
Pop $0
${NSD_CreateLabel} 0 0 100% 20% "Using '$uniqueDrive' letter to be assigned to new volume"
nsDialogs::Show
FunctionEnd

Function getDriveLetterEnd
${If} $uniqueDrive == ""
        MessageBox MB_OK "Drive Letter can't be left blank"
        Abort
${EndIf}

nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\ps_utility.ps1" "isDriveExist" $uniqueDrive  '
pop $R1
pop $R2
${If} $R2 == "True$\r$\n"
        MessageBox MB_OK "Drive $uniqueDrive already exist. Please provide another drive letter."
        Abort
${EndIf}
;MessageBox mb_ok $R2

SetOutPath "$INSTDIR\logs"
FileOpen $9 diskpartscript.txt w ;Opens an Empty File and fills it
FileWrite $9 "select volume $drive$\r$\n"
FileWrite $9 "shrink desired=$size$\r$\n"
FileWrite $9 "select disk $diskNumber"
FileWrite $9 "create partition primary size=$size$\r$\n"
FileWrite $9 "format quick fs=ntfs$\r$\n"
FileWrite $9 "assign letter=$uniqueDrive$\r$\n"
FileClose $9 ;Closes the filled file

nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\ps_utility.ps1" "createFinalPartition"  '
pop $R1
pop $R2

${If} ${RunningX64}
      ${DisableX64FSRedirection}

      #Update MOUNT_LOCATION property
      nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\update_property.ps1" "$property_file" "$property" "$uniqueDrive"  '
      nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\bitlocker_drive_setup.ps1" $uniqueDrive  '

      ${EnableX64FSRedirection}
${EndIf}
MessageBox mb_ok "Bitlocker drive setup complete. Please check log file '$INSTDIR\logs\bitlockersetup.log' for more details."
FunctionEnd

Section "policyagent" SEC01
  # Set output path to the installation directory (also sets the working directory for shortcuts)
  SetOutPath "$INSTDIR"

  # Copy files to installation directory
  SetOverwrite try
  # bin directory
  SetOutPath "$INSTDIR\bin\commons"
  File "bin\commons\parse.py"
  File "bin\commons\process_trust_policy.py"
  File "bin\commons\utils.py"
  File "bin\commons\__init__.py"

  SetOutPath "$INSTDIR\bin\encryption"
  File "bin\encryption\crypt.py"
  File "bin\encryption\win_crypt.py"
  File "bin\encryption\__init__.py"

  SetOutPath "$INSTDIR\bin\invocation"
  File "bin\invocation\measure_vm.py"
  File "bin\invocation\stream.py"
  File "bin\invocation\vrtm_invoke.py"
  File "bin\invocation\__init__.py"

  SetOutPath "$INSTDIR\bin\trustpolicy"
  File "bin\trustpolicy\trust_policy_retrieval.py"
  File "bin\trustpolicy\trust_store_glance_image_tar.py"
  File "bin\trustpolicy\trust_store_swift.py"
  File "bin\trustpolicy\__init__.py"
  
  SetOutPath "$INSTDIR\bin"
  File "bin\policyagent-init"
  File "bin\policyagent.py"
  File "bin\__init__.py"
  File "bin\BitLocker.exe"
  
  # configuration directory
  SetOutPath "$INSTDIR\configuration"
  File "configuration\logging_properties_nt.cfg"
  
  # scripts directory
  SetOutPath "$INSTDIR\scripts"
  File "scripts\unlock_bitlocker_drive.ps1"
  File "scripts\free_bitlocker_drive.ps1"

  # Create System Environment Variable - POLICYAGENT_HOME
  !define env_hklm 'HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"'
  !define env_hkcu 'HKCU "Environment"'
  WriteRegExpandStr ${env_hklm} POLICYAGENT_HOME $INSTDIR
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
SectionEnd

Section -AdditionalIcons
  CreateDirectory "$SMPROGRAMS\Intel"
  CreateDirectory "$SMPROGRAMS\Intel\PolicyAgent"
  CreateShortCut "$SMPROGRAMS\Intel\PolicyAgent\Uninstall.lnk" "$INSTDIR\uninst.exe"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

Function .onInit
  ; Start Code to specify ini file path
  StrCpy "$INIFILE" "$EXEDIR\system.ini"
  IfFileExists "$INIFILE" 0 file_not_found
        goto check_unique_drive_letter
  file_not_found:
        MessageBox MB_OK "System Configuration file doesn't exists in installer folder"
        Abort
  check_unique_drive_letter:
  ReadINIStr $uniqueDrive "$INIFILE" "POLICY_AGENT" "DriveUsedForEncryption"
        ${If} $uniqueDrive == ""
              MessageBox MB_OK "Please configure UniqueDrive name in system.ini"
              Abort
        ${EndIf}

  ReadRegStr $R0 ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString"
  StrCmp $R0 "" done
  MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL|MB_DEFBUTTON2 "$(^Name) is already installed. Click `OK` to remove the previous version or `Cancel` to cancel this upgrade." IDOK +2
  Abort
  Exec $INSTDIR\uninst.exe
  done:
FunctionEnd

Function un.onUninstSuccess
;  HideWindow
;  MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully removed from your computer."
FunctionEnd

Function un.onInit
;  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely remove $(^Name) and all of its components?" IDYES +2
;  Abort
FunctionEnd

Function DirectoryPageShow
	FindWindow $R0 "#32770" "" $HWNDPARENT
	GetDlgItem $R1 $R0 1019
	EnableWindow $R1 0
	GetDlgItem $R1 $R0 1001
	EnableWindow $R1 0
FunctionEnd

Section Uninstall
  ${If} ${RunningX64}
    ${DisableX64FSRedirection}

	Strcpy $property "MOUNT_LOCATION"
	Strcpy $property_file "$INSTDIR\configuration\policyagent_nt.properties"
	#Update MOUNT_LOCATION property
	nsExec::ExecToStack 'powershell -inputformat none -ExecutionPolicy RemoteSigned -File "$INSTDIR\scripts\free_bitlocker_drive.ps1" "$property_file" $property'

    ${EnableX64FSRedirection}
  ${EndIf}

  nsExec::Exec 'sc stop UnlockDrive'
  nsExec::Exec 'sc delete UnlockDrive'

  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\configuration\bitlocker.key"
  Delete "$INSTDIR\configuration\policyagent_nt.properties"
  Delete "$INSTDIR\configuration\logging_properties_nt.cfg"
  Delete "$INSTDIR\bin\__init__.py"
  Delete "$INSTDIR\bin\__init__.pyc"
  Delete "$INSTDIR\bin\trustpolicy\__init__.pyc"
  Delete "$INSTDIR\bin\trustpolicy\__init__.py"
  Delete "$INSTDIR\bin\trustpolicy\trust_store_swift.py"
  Delete "$INSTDIR\bin\trustpolicy\trust_store_swift.pyc"
  Delete "$INSTDIR\bin\trustpolicy\trust_store_glance_image_tar.pyc"
  Delete "$INSTDIR\bin\trustpolicy\trust_store_glance_image_tar.py"
  Delete "$INSTDIR\bin\trustpolicy\trust_policy_retrieval.pyc"
  Delete "$INSTDIR\bin\trustpolicy\trust_policy_retrieval.py"
  Delete "$INSTDIR\bin\policyagent.py"
  Delete "$INSTDIR\bin\policyagent.pyc"
  Delete "$INSTDIR\bin\policyagent-init"
  Delete "$INSTDIR\bin\BitLocker.exe"
  Delete "$INSTDIR\bin\invocation\vrtm_invoke.py"
  Delete "$INSTDIR\bin\invocation\vrtm_invoke.pyc"
  Delete "$INSTDIR\bin\invocation\stream.py"
  Delete "$INSTDIR\bin\invocation\stream.pyc"
  Delete "$INSTDIR\bin\invocation\measure_vm.py"
  Delete "$INSTDIR\bin\invocation\measure_vm.pyc"
  Delete "$INSTDIR\bin\invocation\__init__.py"
  Delete "$INSTDIR\bin\invocation\__init__.pyc"
  Delete "$INSTDIR\bin\encryption\__init__.py"
  Delete "$INSTDIR\bin\encryption\__init__.pyc"
  Delete "$INSTDIR\bin\encryption\crypt.pyc"
  Delete "$INSTDIR\bin\encryption\crypt.py"
  Delete "$INSTDIR\bin\encryption\win_crypt.pyc"
  Delete "$INSTDIR\bin\encryption\win_crypt.py"
  Delete "$INSTDIR\bin\commons\__init__.pyc"
  Delete "$INSTDIR\bin\commons\__init__.py"
  Delete "$INSTDIR\bin\commons\utils.pyc"
  Delete "$INSTDIR\bin\commons\utils.py"
  Delete "$INSTDIR\bin\commons\process_trust_policy.pyc"
  Delete "$INSTDIR\bin\commons\process_trust_policy.py"
  Delete "$INSTDIR\bin\commons\parse.pyc"
  Delete "$INSTDIR\bin\commons\parse.py"
  Delete "$INSTDIR\logs\bitlockersetup.log"
  Delete "$INSTDIR\logs\diskpartscript.txt"
  Delete "$INSTDIR\scripts\bitlocker_drive_setup.ps1"
  Delete "$INSTDIR\scripts\unlock_bitlocker_drive.ps1"
  Delete "$INSTDIR\scripts\update_property.ps1"
  Delete "$INSTDIR\scripts\free_bitlocker_drive.ps1"
  Delete "$INSTDIR\scripts\ps_utility.ps1"
  Delete "$SMPROGRAMS\Intel\PolicyAgent\Uninstall.lnk"

  RMDir "$SMPROGRAMS\Intel\PolicyAgent"
  RMDir "$SMPROGRAMS\Intel"
  RMDir "$INSTDIR\configuration"
  RMDir "$INSTDIR\bin\trustpolicy"
  RMDir "$INSTDIR\bin\invocation"
  RMDir "$INSTDIR\bin\encryption"
  RMDir "$INSTDIR\bin\commons"
  RMDir "$INSTDIR\bin"
  RMDir "$INSTDIR\logs"
  RMDir "$INSTDIR\scripts"
  RMDir "$INSTDIR"

  # Remove system environment variable POLICYAGENT_HOME
  DeleteRegValue ${env_hklm} POLICYAGENT_HOME
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  SetAutoClose true
SectionEnd
