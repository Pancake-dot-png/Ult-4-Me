$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$portableRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) 'dist\win-unpacked'))
# Fail before packaging can empty a directory still used by the running app.
$runningPortable = Get-Process -Name 'ULT-4-ME V2', 'vision-worker' -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($portableRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)
}
if ($runningPortable) { throw 'Close the portable V2 app and its detector before rebuilding. No package files were changed.' }
$pythonExe = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install requirements.txt first.' }
# Rebuilding must preserve settings already edited in the portable app.
$portableConfig = Join-Path (Get-Location) 'dist\win-unpacked\config.json'
$configBytes = $null
if (Test-Path -LiteralPath $portableConfig) {
    $configBytes = [System.IO.File]::ReadAllBytes($portableConfig)
} elseif (Test-Path -LiteralPath 'config.json') {
    $configBytes = [System.IO.File]::ReadAllBytes((Join-Path (Get-Location) 'config.json'))
} elseif (Test-Path -LiteralPath 'release-settings.json') {
    $configBytes = [System.IO.File]::ReadAllBytes((Join-Path (Get-Location) 'release-settings.json'))
}
# Portable template edits are user data too. Keep a recovery copy and restore it
# after packaging, including if a build fails partway through.
$portableTemplates = Join-Path (Get-Location) 'dist\win-unpacked\templates'
$templateSnapshot = $null
if (Test-Path -LiteralPath $portableTemplates) {
    $stateSnapshot = Join-Path (Get-Location) ('build\portable-state-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stateSnapshot -Force | Out-Null
    $templateSnapshot = Join-Path $stateSnapshot 'templates'
    Copy-Item -LiteralPath $portableTemplates -Destination $templateSnapshot -Recurse -ErrorAction Stop
    if ($null -ne $configBytes) { [System.IO.File]::WriteAllBytes((Join-Path $stateSnapshot 'config.json'), $configBytes) }
    Get-ChildItem -LiteralPath $portableRoot -Filter 'config.json*.bak' -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $stateSnapshot
    }
}
try {
& $pythonExe -m PyInstaller --noconfirm --onedir --name vision-worker --paths engine --distpath build --workpath build\pyinstaller app\src\vision-worker.py
if ($LASTEXITCODE -ne 0) { throw 'Vision worker build failed' }
& $pythonExe -m PyInstaller --noconfirm --onefile --name capture-screen --distpath build\capture-screen --workpath build\pyinstaller app\src\capture-screen.py
if ($LASTEXITCODE -ne 0) { throw 'Capture helper build failed' }
& .\node_modules\.bin\electron-builder.cmd --win --dir
if ($LASTEXITCODE -ne 0) { throw 'Electron build failed' }
} finally {
    New-Item -ItemType Directory -Path (Split-Path $portableConfig -Parent) -Force | Out-Null
    if ($null -ne $configBytes) { [System.IO.File]::WriteAllBytes($portableConfig, $configBytes) }
    if ($null -ne $templateSnapshot) {
        New-Item -ItemType Directory -Path $portableTemplates -Force | Out-Null
        Get-ChildItem -LiteralPath $templateSnapshot | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $portableTemplates -Recurse -Force -ErrorAction Stop
        }
        Get-ChildItem -LiteralPath $stateSnapshot -Filter 'config.json*.bak' -File | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $portableRoot -Force
        }
    }
}
Write-Host 'V2 is built in dist\win-unpacked. Run ULT-4-ME V2.exe.'
