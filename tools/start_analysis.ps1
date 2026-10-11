param(
    [Parameter(Mandatory)][string]$AnalysisRoot,
    [Parameter(Mandatory)][string]$GhidraRoot,
    [Parameter(Mandatory)][string]$JavaRoot,
    [Parameter(Mandatory)][string]$ServerJar,
    [ValidateRange(1024,65535)][int]$Port = 8101
)
$ErrorActionPreference = 'Stop'
$project = Join-Path $AnalysisRoot 'projects'
if (-not (Test-Path -LiteralPath (Join-Path $project 'lsd-original.gpr'))) {
    throw 'Import the verified LSD analysis ELF into the lsd-original project first.'
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already occupied. Existing servers are preserved."
}
foreach ($path in @($ServerJar, (Join-Path $JavaRoot 'bin\java.exe'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing analysis prerequisite: $path" }
}
New-Item -ItemType Directory -Force -Path "$AnalysisRoot\home", "$AnalysisRoot\tmp", "$AnalysisRoot\logs" | Out-Null
$env:GHIDRA_MCP_BIND_ADDRESS = '127.0.0.1'
$env:GHIDRA_MCP_FILE_ROOT = $AnalysisRoot
$env:USERPROFILE = "$AnalysisRoot\home"
$env:APPDATA = "$AnalysisRoot\home\AppData\Roaming"
$env:LOCALAPPDATA = "$AnalysisRoot\home\AppData\Local"
$env:TEMP = "$AnalysisRoot\tmp"
$env:TMP = "$AnalysisRoot\tmp"
$env:JAVA_HOME = $JavaRoot
$classpath = [System.Collections.Generic.List[string]]::new()
$classpath.Add(($ServerJar -replace '\\','/'))
foreach ($group in @('Framework','Features','Debug','Processors')) {
    foreach ($module in Get-ChildItem -LiteralPath "$GhidraRoot\Ghidra\$group" -Directory) {
        $lib = Join-Path $module.FullName 'lib'
        if (Test-Path -LiteralPath $lib) { $classpath.Add(($lib -replace '\\','/') + '/*') }
    }
}
$argumentFile = Join-Path $AnalysisRoot 'server.args'
@(
    '-Xmx2G','-XX:+UseG1GC','-XX:ParallelGCThreads=2','-XX:CICompilerCount=2',
    '-Djava.awt.headless=true','-Dfile.encoding=UTF8','-Xshare:off',
    ('-Dghidra.home=' + ($GhidraRoot -replace '\\','/')),
    '-Dapplication.name=GhidraMCP',
    ('-Duser.home=' + ($env:USERPROFILE -replace '\\','/')),
    ('-Djava.io.tmpdir=' + ($env:TEMP -replace '\\','/')),
    '-classpath',('"' + ($classpath -join ';') + '"'),
    'com.xebyte.headless.GhidraMCPHeadlessServer',
    '--port',"$Port",'--bind','127.0.0.1',
    '--project',('"' + ($project -replace '\\','/') + '"'),
    '--program','/original-symbols.elf'
) | Set-Content -LiteralPath $argumentFile -Encoding utf8
$process = Start-Process -FilePath (Join-Path $JavaRoot 'bin\java.exe') `
    -ArgumentList "@$argumentFile" -WorkingDirectory $AnalysisRoot -WindowStyle Hidden `
    -RedirectStandardOutput "$AnalysisRoot\logs\server.out.log" `
    -RedirectStandardError "$AnalysisRoot\logs\server.err.log" -PassThru
$process.PriorityClass = 'BelowNormal'
$process.Id | Set-Content -LiteralPath "$AnalysisRoot\server.pid"
Write-Output "LSD Ghidra MCP started: PID $($process.Id), http://127.0.0.1:$Port"
