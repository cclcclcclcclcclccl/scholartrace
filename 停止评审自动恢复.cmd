@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install_review_startup.ps1" -Remove
pause
