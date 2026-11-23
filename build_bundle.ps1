# Build TimberLine.bundle and TimberLine.bundle.zip for the Autodesk App Store
$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $rootDir "dist"
$bundleDir = Join-Path $distDir "TimberLine.bundle"
$contentsDir = Join-Path $bundleDir "Contents"
$zipPath = Join-Path $distDir "TimberLine.bundle.zip"

if (Test-Path $distDir) {
    Remove-Item -Recurse -Force $distDir
}

New-Item -ItemType Directory -Force -Path $contentsDir | Out-Null

Copy-Item -Force (Join-Path $rootDir "PackageContents.xml") (Join-Path $bundleDir "PackageContents.xml")

$items = @(
    "TimberLine.manifest",
    "TimberLine.py",
    "fusion_ui.py",
    "lumber_catalog.py",
    "joinery_tools.py",
    "joinery_command.py",
    "attach_planner.py",
    "attach_command.py",
    "operation_log.py",
    "operations_command.py",
    "kerf_planner.py",
    "kerf_command.py",
    "resources"
)

foreach ($item in $items) {
    $src = Join-Path $rootDir $item
    if (Test-Path $src) {
        Copy-Item -Recurse -Force $src $contentsDir
    }
}

Compress-Archive -Path $bundleDir -DestinationPath $zipPath -Force

Write-Host "Built bundle: $bundleDir" -ForegroundColor Green
Write-Host "Built archive: $zipPath" -ForegroundColor Green
