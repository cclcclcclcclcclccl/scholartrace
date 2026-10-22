$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& (Join-Path $root '.venv/Scripts/python.exe') -X utf8 (Join-Path $PSScriptRoot 'review_watchdog.py') start
