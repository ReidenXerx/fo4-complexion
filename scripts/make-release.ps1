<#
.SYNOPSIS
  Packs a release archive of Silhouette: the Data layout, ready for a mod manager.

.DESCRIPTION
  Assembles build\release\Silhouette-<version>\ from the same built and generated
  files deploy-dev.ps1 stages, checks they are one generator run, and zips it to
  build\release\Silhouette-<version>.zip. It does NOT publish anything: uploading
  is the owner's act, always.

  The generated files are the OWNER's build: they carry the presets on this
  machine. A public release needs a build generated from the presets it ships
  with -- say so, never ship a machine's own BodyGen files by accident.

  ASCII only. Windows PowerShell 5.1 reads a BOM-less UTF-8 script as ANSI.
#>
[CmdletBinding()]
param(
    [string] $Config = 'Release'
)

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$version = (Get-Content (Join-Path $root 'VERSION') -TotalCount 1).Trim()
$out     = Join-Path $root "build\release\Silhouette-$version"
$zip     = "$out.zip"

$dll  = Join-Path $root "build\$Config\Silhouette.dll"
$pex  = Join-Path $root 'build\papyrus\Silhouette'
$data = Join-Path $root 'data'
if (-not (Test-Path $dll)) { throw "Missing $dll - run scripts\build-plugin.ps1." }
if (-not (Test-Path (Join-Path $pex 'Bridge.pex'))) { throw "Missing scripts - run scripts\build-papyrus.ps1." }

$catalog = Get-Content (Join-Path $data 'F4SE\Plugins\Silhouette\catalog.json') -Raw | ConvertFrom-Json
$header  = Get-Content (Join-Path $data 'F4SE\Plugins\F4EE\BodyGen\Loose\Silhouette_templates.ini') -TotalCount 5
if (-not ($header -match "Build $($catalog.build), marker stamp $($catalog.stamp) ")) {
    throw "catalog.json and the BodyGen templates are different builds - regenerate."
}

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
if (Test-Path $zip) { Remove-Item -Force $zip }
New-Item -ItemType Directory -Force -Path $out | Out-Null
Copy-Item (Join-Path $data 'F4SE') $out -Recurse -Force
Copy-Item (Join-Path $data 'MCM') $out -Recurse -Force
Copy-Item (Join-Path $data 'Silhouette.esp') $out -Force
Copy-Item $dll (Join-Path $out 'F4SE\Plugins\Silhouette.dll') -Force
$scripts = Join-Path $out 'Scripts\Silhouette'
New-Item -ItemType Directory -Force -Path $scripts | Out-Null
foreach ($f in Get-ChildItem $pex -Filter *.pex) {
    $name = if ($f.Name -ieq 'player.pex') { 'Player.pex' } else { $f.Name }
    Copy-Item $f.FullName (Join-Path $scripts $name) -Force
}
foreach ($doc in @('README.md', 'LICENSE')) {
    $p = Join-Path $root $doc
    if (Test-Path $p) { Copy-Item $p $out -Force }
}

Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip -CompressionLevel Optimal
$item = Get-Item $zip
Write-Host ("packed {0}  {1} bytes: build {2}, stamp {3}" -f $item.FullName, $item.Length, $catalog.build, $catalog.stamp)
Write-Host "Nothing was uploaded."
