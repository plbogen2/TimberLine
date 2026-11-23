param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Update VERSION
Set-Content -Path (Join-Path $rootDir "VERSION") -Value $Version -Encoding UTF8

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
