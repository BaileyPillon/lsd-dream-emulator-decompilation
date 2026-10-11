[CmdletBinding()]
param(
    [ValidateSet('check', 'doctor', 'progress', 'test')]
    [string]$Action = 'check',
    [Parameter(Mandatory)][string]$Distro,
    [ValidateRange(1, 64)]
    [int]$Jobs = 4
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$linuxRoot = & wsl.exe -d $Distro --exec wslpath -a -u $projectRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$linuxScript = @'
set -eu
lsdPython=python3
if [ -x .venv/bin/python ]; then
    export PATH="$PWD/.venv/bin:$PATH"
    lsdPython=python
elif [ -x /opt/lsd-decomp-venv/bin/python ]; then
    export PATH=/opt/lsd-decomp-venv/bin:$PATH
    lsdPython=python
fi
case "$1" in
    check) "$lsdPython" configure.py; ninja check -j "$2" ;;
    doctor) "$lsdPython" configure.py doctor ;;
    progress) "$lsdPython" tools/progress.py ;;
    test) "$lsdPython" -m unittest discover -s tests -v ;;
esac
'@

& wsl.exe -d $Distro --cd $linuxRoot.Trim() --exec bash -lc $linuxScript lsd-build $Action $Jobs
exit $LASTEXITCODE
