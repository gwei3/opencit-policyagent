@echo off
REM #####################################################################
REM This script build the bitlocker service on windows platform
REM #####################################################################
setlocal enabledelayedexpansion

set me=%~n0
set pwd=%~dp0

set VsDevCmd="C:\Program Files (x86)\Microsoft Visual Studio 12.0\Common7\Tools\VsDevCmd.bat"

echo. Building biltlocker service....
cd
call %VsDevCmd%
IF NOT %ERRORLEVEL% EQU 0 (
  echo. %me%: Visual Studio Dev Env could not be set
  EXIT /b %ERRORLEVEL%
)

msbuild BitLocker.sln /property:Configuration=Release
IF NOT %ERRORLEVEL% EQU 0 (
  echo. %me%: Build Failed
  EXIT /b %ERRORLEVEL%
)

cp BitLocker\bin\Release\BitLocker.exe ../policyagent/src/main/application/bin/

endlocal