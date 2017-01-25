@echo off
REM #####################################################################
REM This script build the bitlocker service on windows platform
REM #####################################################################
setlocal enabledelayedexpansion

set me=%~n0
set pwd=%~dp0

set VsDevCmd="C:\Program Files (x86)\Microsoft Visual Studio 12.0\Common7\Tools\VsDevCmd.bat"

REM ~ is to remove "" from argument passed with quotes
IF "%~1"=="" (
  call:print_help
) ELSE IF "%~2"=="" (
  call:print_help
) ELSE (
  call:ps_service_build %2 %1
)
GOTO:EOF

:ps_service_build
  echo. Building biltlocker service....
  cd %pwd%

  call %VsDevCmd%
  IF NOT %ERRORLEVEL% EQU 0 (
    echo. %me%: Visual Studio Dev Env could not be set
    EXIT /b %ERRORLEVEL%
  )

  msbuild BitLocker.sln /property:Configuration=%1;Platform=%2
  IF NOT %ERRORLEVEL% EQU 0 (
    echo. %me%: Build Failed
    EXIT /b %ERRORLEVEL%
  )

  copy "BitLocker\bin\%2\%1\BitLocker.exe" ..\policyagent\src\main\application\bin /y
  IF NOT %ERRORLEVEL% EQU 0 (
    echo. "%me%: BitLocker.exe could not be copied to destination"
    EXIT /b %ERRORLEVEL%
  )
  EXIT /b 0
GOTO:EOF

:print_help
  echo. "Usage: $0 Platform Configuration"
GOTO:EOF

endlocal