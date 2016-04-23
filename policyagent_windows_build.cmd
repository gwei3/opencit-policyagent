@echo off
setlocal enabledelayedexpansion

set me=%~n0
set pwd=%~dp0

set /p makensis=Enter the NSIS binary path : 
echo. Creating policyagent installer....

call .\bitlocker-service\bitlocker_build.cmd
IF NOT %ERRORLEVEL% EQU 0 (
  echo. %me%: bitlocker service build failed
  EXIT /b %ERRORLEVEL%
)

call %makensis% .\policyagent\src\main\application\policyagentinstallscript.nsi
IF NOT %ERRORLEVEL% EQU 0 (
  echo. %me%: policyagent install failed
  EXIT /b %ERRORLEVEL%
)

endlocal