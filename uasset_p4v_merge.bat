@echo off
rem P4V merge arguments should be: %b %2 %1
python "%~dp0uasset_p4merge.py" "%~1" "%~2" "%~3"
exit /b %ERRORLEVEL%
