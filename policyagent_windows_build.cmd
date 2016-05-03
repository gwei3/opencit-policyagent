@echo off
setlocal enabledelayedexpansion

set me=%~n0
set pwd=%~dp0
set "pa_home=%pwd%"

IF "%NSIS_HOME%"=="" (
  set "makensis=C:\Program Files (x86)\NSIS\makensis.exe"
) ELSE (
  set "makensis=%NSIS_HOME%\makensis.exe"
)

IF %1=="" (
  call:print_help
) ELSE IF %2=="" (
  call:print_help
) ELSE (
  call:pa_installer %1 %2
)
GOTO:EOF

:pa_installer
  echo. Creating policyagent installer....
  cd %pa_home%
  cd
  call "%pa_home%\bitlocker_service\BitLocker_build.cmd" %1 %2
  IF NOT %ERRORLEVEL% EQU 0 (
    echo. %me%: bitlocker service build failed
    call:ExitBatch
    REM EXIT /b %ERRORLEVEL%
  )

  REM call %makensis% .\policyagent\src\main\application\policyagentinstallscript.nsi
  cd %pa_home%
  cd
  IF EXIST "%makensis%" (
    echo. "%makensis% exists"
    call "%makensis%" .\policyagent\src\main\application\policyagentinstallscript.nsi
  ) ELSE (
    echo. "Neither makensis.exe found at default location nor environment variable pointing to NSIS_HOME exist."
    echo. "If NSIS not installed please install it and add NSIS_HOME environment variable in system variables"
    call:ExitBatch
    REM EXIT /b 1
  )
  IF NOT %ERRORLEVEL% EQU 0 (
    echo. %me%: policyagent install failed
    call:ExitBatch
    REM EXIT /b %ERRORLEVEL%
  )
GOTO:EOF

:print_help
  echo. "Usage: $0 Platform Configuration"
GOTO:EOF

:ExitBatch - Cleanly exit batch processing, regardless how many CALLs
if not exist "%temp%\ExitBatchYes.txt" call :buildYes
call :CtrlC <"%temp%\ExitBatchYes.txt" 1>nul 2>&1
:CtrlC
cmd /c exit -1073741510

:buildYes - Establish a Yes file for the language used by the OS
pushd "%temp%"
set "yes="
copy nul ExitBatchYes.txt >nul
for /f "delims=(/ tokens=2" %%Y in (
  '"copy /-y nul ExitBatchYes.txt <nul"'
) do if not defined yes set "yes=%%Y"
echo %yes%>ExitBatchYes.txt
popd
exit /b

endlocal