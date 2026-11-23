# Install TimberLine into Autodesk Fusion's AddIns directory
$targetDir = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\AddIns\TimberLine"
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path $targetDir) {
    Remove-Item -Recurse -Force $targetDir
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$itemsToCopy = @(
    "TimberLine.manifest",
    "TimberLine.py",
    "fusion_ui.py",
    "lumber_catalog.py",
    "joinery_tools.py",
    "joinery_command.py",
    "kerf_planner.py",
    "kerf_command.py",
    "resources"
)

foreach ($item in $itemsToCopy) {
    $src = Join-Path $sourceDir $item
    if (Test-Path $src) {
        Copy-Item -Recurse -Force $src $targetDir
    }
}

Write-Host "Installed TimberLine add-in to: $targetDir" -ForegroundColor Green
Write-Host "Open Autodesk Fusion -> Utilities -> Add-Ins (Shift+S) -> Add-Ins tab -> Run 'TimberLine'."
