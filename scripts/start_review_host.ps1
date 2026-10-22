param([switch]$UpdateEntry)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 can otherwise negotiate obsolete TLS and fail HTTPS.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function Wait-ReviewHealth([string]$BaseUrl, [int]$Attempts = 12) {
    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        try {
            $result = Invoke-RestMethod "$BaseUrl/api/health" -TimeoutSec 10
            if ($result.service -eq 'scholartrace') { return $result }
        } catch { }
        if ($attempt -lt $Attempts - 1) { Start-Sleep -Seconds 2 }
    }
    throw "Review service not ready after retries: $BaseUrl"
}
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$reviewRoot = Join-Path $projectRoot 'artifacts/public-review-20261021'
if (-not (Test-Path -LiteralPath (Join-Path $reviewRoot 'review-access.json'))) {
    throw 'Review instance is not prepared. Follow docs/免费评审部署说明_2026-10-21.md.'
}
& node scripts/start.mjs
if ($LASTEXITCODE -ne 0) { throw 'Local model startup failed' }
$serviceReady = $false
try { $serviceReady = (Invoke-RestMethod 'http://localhost:8768/api/health' -TimeoutSec 5).service -eq 'scholartrace' } catch { }
if (-not $serviceReady) {
    $env:SCHOLARTRACE_PUBLIC = '1'
    $env:SCHOLARTRACE_REGISTRATION = '0'
    try {
        $server = Start-Process -FilePath (Join-Path $projectRoot '.venv/Scripts/python.exe') -ArgumentList @('-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8768') -WorkingDirectory $reviewRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reviewRoot 'server-restart.out.log') -RedirectStandardError (Join-Path $reviewRoot 'server-restart.err.log')
    } finally {
        Remove-Item Env:SCHOLARTRACE_PUBLIC -ErrorAction SilentlyContinue
        Remove-Item Env:SCHOLARTRACE_REGISTRATION -ErrorAction SilentlyContinue
    }
}
# Wait for the origin before creating or publishing a tunnel.
$null = Wait-ReviewHealth 'http://127.0.0.1:8768'
$url = ''
$urlFile = Join-Path $reviewRoot 'url.txt'
if (Test-Path -LiteralPath $urlFile) {
    $candidate = (Get-Content -LiteralPath $urlFile -Raw).Trim()
    if ($candidate -match '^https://[a-z0-9-]+\.trycloudflare\.com$') {
        try { if ((Invoke-RestMethod "$candidate/api/health" -TimeoutSec 10).service -eq 'scholartrace') { $url = $candidate } } catch { }
    }
}
if (-not $url) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $errorLog = Join-Path $reviewRoot "tunnel-$stamp.err.log"
    $tunnel = Start-Process -FilePath (Join-Path $projectRoot 'tools/cloudflared.exe') -ArgumentList @('tunnel','--url','http://127.0.0.1:8768','--protocol','http2','--edge-ip-version','4','--no-autoupdate') -WorkingDirectory $reviewRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reviewRoot "tunnel-$stamp.out.log") -RedirectStandardError $errorLog
    for ($i=0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path -LiteralPath $errorLog) {
            $match = [regex]::Match((Get-Content -LiteralPath $errorLog -Raw), 'https://[a-z0-9-]+\.trycloudflare\.com')
            if ($match.Success) { $url = $match.Value; break }
        }
    }
    if (-not $url) { throw 'Free tunnel did not return a URL; inspect its error log' }
    Set-Content -LiteralPath $urlFile -Value $url -Encoding UTF8
}
# Only anonymous health is requested here; no reviewer credentials leave localhost.
$health = Wait-ReviewHealth $url
if ($health.service -ne 'scholartrace') { throw 'Unexpected service at tunnel URL' }
if ($UpdateEntry) {
    & (Join-Path $projectRoot '.venv/Scripts/python.exe') -X utf8 (Join-Path $PSScriptRoot 'refresh_review_entry.py')
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Direct review endpoint is available: $url"
        throw 'The app is running, but the fixed entrance could not be updated. Share the direct endpoint temporarily.'
    }
}
Write-Host "Review endpoint: $url"
Write-Host 'Keep this computer awake and online. No authenticated public test was performed.'

& (Join-Path $projectRoot '.venv/Scripts/python.exe') -X utf8 (Join-Path $PSScriptRoot 'review_watchdog.py') start
