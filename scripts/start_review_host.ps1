param([switch]$UpdateEntry)
$ErrorActionPreference = 'Stop'
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
$health = Invoke-RestMethod "$url/api/health" -TimeoutSec 30
if ($health.service -ne 'scholartrace') { throw 'Unexpected service at tunnel URL' }
if ($UpdateEntry) {
    $repo = 'cclcclcclcclcclccl/scholartrace'
    $state = & gh api "repos/$repo/contents/runtime.json?ref=gh-pages" | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Pages configuration' }
    $content = @{url=$url; checked_at=(Get-Date -Format 'yyyy-MM-dd'); status='免费隧道健康接口已检查；需保持电脑开机联网，未证明长期可用性。'} | ConvertTo-Json
    $body = @{message='Refresh free review endpoint'; branch='gh-pages'; sha=$state.sha; content=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($content))} | ConvertTo-Json
    $requestFile = Join-Path $reviewRoot 'pages-update.json'
    [IO.File]::WriteAllText($requestFile,$body,[Text.UTF8Encoding]::new($false))
    & gh api "repos/$repo/contents/runtime.json" --method PUT --input $requestFile --silent
    if ($LASTEXITCODE -ne 0) { throw 'Unable to update fixed entrance' }
}
Write-Host "Review endpoint: $url"
Write-Host 'Keep this computer awake and online. No authenticated public test was performed.'
