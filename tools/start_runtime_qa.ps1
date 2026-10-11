param(
    [Parameter(Mandatory)][string]$EmulatorRoot,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$Cue,
    [Parameter(Mandatory)][string]$BiosRoot,
    [ValidateSet('boot','play')][string]$Scenario = 'boot',
    [ValidateRange(1,30000)][int]$Frames = 1800,
    [string]$LoadState,
    [string]$Python = 'python',
    [string]$Script,
    [switch]$CaptureAudio
)
$ErrorActionPreference = 'Stop'
$executable = Join-Path $EmulatorRoot 'EmuHawk.exe'
if (-not $Script) { $Script = Join-Path $PSScriptRoot 'runtime_smoke.lua' }
foreach ($item in @($executable, $Script, $Cue, (Join-Path $BiosRoot 'scph5500.bin'))) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) { throw "Missing QA input: $item" }
}
if (Test-Path -LiteralPath $Output) { throw 'Choose a new output directory for this run.' }
if ($LoadState -and -not (Test-Path -LiteralPath $LoadState -PathType Leaf)) { throw 'Missing QA start state.' }
New-Item -ItemType Directory -Path $Output | Out-Null
# Freeze these two inputs so a later source edit cannot change the running QA.
$runScript = Join-Path $Output 'runtime_smoke.lua'
Copy-Item -LiteralPath $Script -Destination $runScript
if ($LoadState) {
    $runState = Join-Path $Output 'start.State'
    Copy-Item -LiteralPath $LoadState -Destination $runState
}
$config = [ordered]@{
    LastWrittenFrom = '2.11.1'
    FirstBoot = $false
    SkipSuperuserPrivsCheck = $true
    UpdateAutoCheckEnabled = $false
    SoundEnabled = $false
    SoundEnabledNormal = $false
    SoundEnabledRWFF = $false
    FirmwareUserSpecifications = [ordered]@{
        'PSX+J' = (Join-Path $BiosRoot 'scph5500.bin')
        'PSX+U' = (Join-Path $BiosRoot 'scph5501.BIN')
        'PSX+E' = (Join-Path $BiosRoot 'scph5502.BIN')
    }
}
$configPath = Join-Path $Output 'config.json'
$config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding utf8
$configInput = Join-Path $Output 'config-input.json'
Copy-Item -LiteralPath $configPath -Destination $configInput
$pinArguments = @((Join-Path $PSScriptRoot 'runtime_inputs.py'), '--cue', $Cue,
    '--bios-root', $BiosRoot, '--emulator-root', $EmulatorRoot,
    '--configuration', $configInput, '--script', $runScript,
    '--output', (Join-Path $Output 'inputs.json'), '--scenario', $Scenario, '--frames', "$Frames")
if ($LoadState) { $pinArguments += @('--load-state', $runState) }
if ($CaptureAudio) { $pinArguments += '--capture-audio' }
& $Python @pinArguments
if ($LASTEXITCODE -ne 0) { throw 'QA input identity pinning failed; emulator was not started.' }
$arguments = @('--config', ('"' + $configPath + '"'), '--lua', ('"' + $runScript + '"'),
               '--chromeless', '--gdi')
if ($LoadState) {
    $arguments += @('--load-state', ('"' + $runState + '"'))
}
if ($CaptureAudio) {
    # BizHawk's WAV writer requests core audio even while desktop sound is off.
    $arguments += @('--dump-type', 'wave', '--dump-name', ('"' + (Join-Path $Output 'audio.wav') + '"'),
                    '--audiosync', 'true', '--dump-length', "$Frames")
}
$arguments += ('"' + $Cue + '"')
$previousQA = @{}
foreach ($name in @('LSD_QA_OUTPUT','LSD_QA_SCENARIO','LSD_QA_FRAMES')) {
    $previousQA[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:LSD_QA_OUTPUT = $Output
    $env:LSD_QA_SCENARIO = $Scenario
    $env:LSD_QA_FRAMES = "$Frames"
    $process = Start-Process -FilePath $executable -ArgumentList $arguments `
        -WorkingDirectory $EmulatorRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Output 'emulator.out.log') `
        -RedirectStandardError (Join-Path $Output 'emulator.err.log') -PassThru
} finally {
    foreach ($name in $previousQA.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousQA[$name], 'Process')
    }
}
$process.PriorityClass = 'BelowNormal'
$process.Id | Set-Content -LiteralPath (Join-Path $Output 'emulator.pid')
Write-Output "Started emulator QA PID $($process.Id), output $Output"
