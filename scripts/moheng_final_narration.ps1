$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$folder = Join-Path $root 'artifacts/moheng-final-20261021'
Add-Type -AssemblyName System.Speech
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speech.SelectVoice('Microsoft Huihui Desktop')
$speech.Rate = 1
$scenes = Get-Content -LiteralPath (Join-Path $folder 'narration.json') -Raw -Encoding UTF8 | ConvertFrom-Json
try {
    foreach ($scene in $scenes) {
        $speech.SetOutputToWaveFile((Join-Path $folder ("voice-{0}.wav" -f $scene.id)))
        $speech.Speak($scene.text)
        $speech.SetOutputToNull()
        Write-Output ("Narrated scene {0}" -f $scene.id)
    }
} finally { $speech.Dispose() }
