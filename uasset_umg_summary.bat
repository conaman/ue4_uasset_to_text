@echo off
set "UASSET_PATH=%~1"
set "UASSET_PATH=%UASSET_PATH:"=%"
python "%~dp0uasset_umg_summary.py" "%UASSET_PATH%"
exit /b %ERRORLEVEL%
