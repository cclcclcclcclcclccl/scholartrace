@echo off
cd /d "%~dp0"
node scripts\start.mjs --open
if errorlevel 1 pause
