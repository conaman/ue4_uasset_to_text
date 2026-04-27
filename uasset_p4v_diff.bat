@echo off
python "%~dp0uasset_p4merge.py" "%~1" "%~2"
exit /b %ERRORLEVEL%
