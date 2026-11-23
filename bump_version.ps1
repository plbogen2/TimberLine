param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [ValidateSet("feature", "fix", "minor", "patch")]
    [string]$Bump
)

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$versionPath = Join-Path $rootDir "VERSION"

if (-not $Version -and -not $Bump) {
    throw "Specify either -Version X.Y.Z or -Bump feature|fix"
}

if ($Bump) {
    $current = (Get-Content $versionPath -Raw).Trim()
    $parts = $current.Split('.')
    $maj = [int]$parts[0]
    $min = [int]$parts[1]
    $pat = [int]$parts[2]
    if ($Bump -in @("feature", "minor")) {
        $min += 1
        $pat = 0
    } else {
        $pat += 1
    }
    $Version = "$maj.$min.$pat"
}

# 1. Update VERSION
[System.IO.File]::WriteAllText($versionPath, "$Version`n", [System.Text.UTF8Encoding]::new($false))

# 2. Update TimberLine.manifest (regex preserves empty-key description object in PS 5.1)
$manifestPath = Join-Path $rootDir "TimberLine.manifest"
$manifestContent = Get-Content $manifestPath -Raw
$manifestContent = $manifestContent -replace '("version"\s*:\s*)"[^"]+"', "`$1`"$Version`""
[System.IO.File]::WriteAllText($manifestPath, $manifestContent, [System.Text.UTF8Encoding]::new($false))

# 3. Update PackageContents.xml (case-sensitive -creplace avoids <?xml version="1.0"?>)
$pkgPath = Join-Path $rootDir "PackageContents.xml"
$pkgContent = Get-Content $pkgPath -Raw
$pkgContent = $pkgContent -creplace 'AppVersion="[^"]+"', "AppVersion=`"$Version`""
$pkgContent = $pkgContent -creplace 'Version="[^"]+"', "Version=`"$Version`""
[System.IO.File]::WriteAllText($pkgPath, $pkgContent, [System.Text.UTF8Encoding]::new($false))

Write-Host "Updated TimberLine version to $Version across VERSION, TimberLine.manifest, and PackageContents.xml" -ForegroundColor Green
