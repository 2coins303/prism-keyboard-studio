param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $env:PYTHONUTF8 = '1'
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment.' }
    $prismPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    & $prismPython -m pip install -r src/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $prismPython scripts/fetch_bridge.py
    if ($LASTEXITCODE -ne 0) { throw 'Bridge verification failed.' }
    & $prismPython -m unittest discover -s src -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $prismPython -m PyInstaller --noconfirm --distpath dist --workpath build 'src/Prism Keyboard Studio.spec'
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
    & $prismPython scripts/package_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Portable release assembly failed.' }
    Write-Host 'The Windows ZIP and SHA256 checksum are in release/.'
} finally { Pop-Location }
