param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$path = Join-Path ([Environment]::GetFolderPath('Startup')) 'Moheng Review.lnk'
$shell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $path) {
    $existing = $shell.CreateShortcut($path)
    if ($existing.Arguments -notlike ('*' + (Join-Path $PSScriptRoot 'start_review_guard.ps1') + '*')) { throw 'An unrelated startup shortcut has this name; it was not changed.' }
}
if ($Remove) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    & (Join-Path $root '.venv/Scripts/python.exe') -X utf8 (Join-Path $PSScriptRoot 'review_watchdog.py') stop
    Write-Host 'Removed Moheng login startup and requested watchdog stop.'
} else {
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'start_review_guard.ps1') + '"'
    $shortcut.WorkingDirectory = $root
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Restore Moheng free review services after user login. No power-policy changes.'
    $shortcut.Save()
    & (Join-Path $PSScriptRoot 'start_review_guard.ps1')
    Write-Host 'Enabled current-user login startup; keep the computer awake and online.'
}
