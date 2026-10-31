@echo off
rem @@ACTION_TITLE@@ @@NAME@@ for Toy Story 3. This file only starts @@SCRIPT@@ next to it, which does the work:
rem open that in Notepad to read every step. "-ExecutionPolicy Bypass" lets Windows run that one script this once;
rem it doesn't change any setting.
if not exist "%~dp0@@SCRIPT@@" (
    echo Please extract the whole zip first, then run this file from the extracted folder.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0@@SCRIPT@@" @@ACTION@@
echo.
pause
