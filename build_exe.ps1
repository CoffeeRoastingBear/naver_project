$ErrorActionPreference = "Stop"

$distDir = Join-Path $PSScriptRoot "dist"
$buildDir = Join-Path $PSScriptRoot "build"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageDir = Join-Path $distDir "dashboard_tool_v2_$timestamp"
$zipPath = Join-Path $distDir "dashboard_tool_v2_$timestamp.zip"

if (Test-Path $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
py -m PyInstaller `
    --noconfirm `
    --onefile `
    --name dashboard `
    --add-data "dashboard.html;." `
    --add-data "dashboard.css;." `
    --add-data "dashboard.js;." `
    dashboard_app.py

New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "data") | Out-Null

Copy-Item -LiteralPath (Join-Path $distDir "dashboard.exe") -Destination (Join-Path $packageDir "dashboard.exe") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.txt") -Destination (Join-Path $packageDir "README.txt") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "config_sample.json") -Destination (Join-Path $packageDir "config_sample.json") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "keyword_master.t1") -Destination (Join-Path $packageDir "keyword_master.t1") -Force

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($packageDir, $zipPath)
Write-Host "Created: $zipPath"
