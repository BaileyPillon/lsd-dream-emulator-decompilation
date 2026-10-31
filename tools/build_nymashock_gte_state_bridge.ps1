[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EmulatorRoot,
    [Parameter(Mandatory = $true)][string]$Netstandard,
    [Parameter(Mandatory = $true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$privateRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '.decomp-lab'))
$outputPath = if ([IO.Path]::IsPathRooted($Output)) { [IO.Path]::GetFullPath($Output) } else {
    [IO.Path]::GetFullPath((Join-Path $repoRoot $Output))
}
if (-not $outputPath.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetExtension($outputPath) -ne '.exe') {
    throw 'Choose a new .exe path inside private .decomp-lab.'
}
$logPath = [IO.Path]::ChangeExtension($outputPath, '.build.log')
if ((Test-Path -LiteralPath $outputPath) -or (Test-Path -LiteralPath $logPath)) {
    throw 'Preserve existing bridge/build files; choose a fresh output name.'
}
$runtimePath = (Resolve-Path -LiteralPath $EmulatorRoot).Path
$facadePath = (Resolve-Path -LiteralPath $Netstandard).Path
$compilerPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compilerPath -PathType Leaf)) { throw 'The existing x64 .NET Framework compiler is required.' }
$compileArgs = @('/nologo', '/target:exe', '/platform:x64', '/langversion:5', "/out:$outputPath",
    '/r:System.Web.Extensions.dll', "/r:$facadePath")
foreach ($name in @('BizHawk.Common.dll', 'BizHawk.BizInvoke.dll', 'BizHawk.Emulation.Common.dll', 'BizHawk.Emulation.Cores.dll')) {
    $library = Join-Path $runtimePath "dll\$name"
    if (-not (Test-Path -LiteralPath $library -PathType Leaf)) { throw "Missing installed runtime library: $name" }
    $compileArgs += "/r:$library"
}
$compileArgs += (Join-Path $PSScriptRoot 'nymashock_gte_state_bridge.cs')
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
& $compilerPath @compileArgs > $logPath 2>&1
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Bridge compilation failed; inspect $logPath."
}
Write-Output "Compiled private stateful GTE bridge: $outputPath"
Write-Output 'No runtime files were copied; execution checks all pinned native inputs.'
