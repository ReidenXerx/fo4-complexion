<#
.SYNOPSIS
  Packs a release archive of Complexion: the Data layout with a FOMOD installer, ready for a mod manager.

.DESCRIPTION
  Assembles build\dist\Complexion-<version>\ from the built and generated files, checks each is there and fresh,
  writes the installer (tools\fomod_pack.py, the house FOMOD standard) and zips it to
  build\dist\Complexion-<version>.zip. It does NOT publish anything: uploading is the owner's act, always.

  Run first: scripts\build-plugin.ps1, scripts\build-papyrus.ps1, python tools\paint\make_marks.py,
  python tools\make_data.py, python tools\make_esp.py data\Complexion.esp.

  ASCII only. Windows PowerShell 5.1 reads a BOM-less UTF-8 script as ANSI.
#>
[CmdletBinding()]
param([string] $Config = 'Release')

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$version = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
$dist    = Join-Path $root 'build\dist'
$out     = Join-Path $dist "Complexion-$version"
$zip     = Join-Path $dist "Complexion-$version.zip"

$files = [ordered]@{
    'F4SE\Plugins\Complexion.dll'            = "build\$Config\Complexion.dll"
    'F4SE\Plugins\Complexion\profiles.json'  = 'data\F4SE\Plugins\Complexion\profiles.json'
    'F4SE\Plugins\Complexion\tags.json'      = 'data\F4SE\Plugins\Complexion\tags.json'
    'F4SE\Plugins\Complexion\README.md'      = 'README.md'
    'F4SE\Plugins\Complexion\LICENSE'        = 'LICENSE'
    'Scripts\Complexion\Bridge.pex'          = 'build\papyrus\Complexion\Bridge.pex'
    'Scripts\Complexion\DLL.pex'             = 'build\papyrus\Complexion\DLL.pex'
    'Scripts\Complexion\Persona.pex'              = 'build\papyrus\Complexion\Persona.pex'
    'Scripts\Complexion\API.pex'              = 'build\papyrus\Complexion\API.pex'
    'Complexion.esp'                         = 'data\Complexion.esp'
    'MCM\Config\Complexion\config.json'      = 'data\MCM\Config\Complexion\config.json'
    'MCM\Config\Complexion\settings.ini'     = 'data\MCM\Config\Complexion\settings.ini'
    'MCM\Config\Complexion\keybinds.json'    = 'data\MCM\Config\Complexion\keybinds.json'
    'Interface\ComplexionMenu.swf'            = 'build\interface\ComplexionMenu.swf'
    'F4SE\Plugins\Complexion\thumbs.json'    = 'data\F4SE\Plugins\Complexion\thumbs.json'
}
foreach ($tree in 'Textures\Overlays\Complexion', 'Textures\Complexion', 'Materials\Overlays\Complexion', 'F4SE\Plugins\F4EE\Overlays\Complexion.esp', 'F4SE\Plugins\RobCo_Patcher\race') {
    Get-ChildItem (Join-Path $root "data\$tree") -File -Recurse | ForEach-Object {
        $files[$_.FullName.Substring((Join-Path $root 'data').Length + 1)] = $_.FullName.Substring($root.Length + 1)
    }
}

& python (Join-Path $root 'tools\make_esp.py') --check (Join-Path $root 'data\Complexion.esp')
if ($LASTEXITCODE) { throw 'Complexion.esp is refused' }
$dll = Get-Item (Join-Path $root "build\$Config\Complexion.dll")
$newest = Get-ChildItem (Join-Path $root 'src') -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($newest.LastWriteTime -gt $dll.LastWriteTime) { throw "Complexion.dll is older than src\$($newest.Name): run scripts\build-plugin.ps1" }
# The window (C-19): its movie newer than every .as, and its pictures of the build the index names.
$swf = Get-Item (Join-Path $root 'build\interface\ComplexionMenu.swf') -ErrorAction SilentlyContinue
$as = Get-ChildItem (Join-Path $root 'interface\src') -Filter *.as | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $swf -or $as.LastWriteTime -gt $swf.LastWriteTime) { throw "ComplexionMenu.swf is missing or older than $($as.Name): run scripts\build-interface.ps1" }
$thumbs = Get-Content (Join-Path $root 'data\F4SE\Plugins\Complexion\thumbs.json') -Raw | ConvertFrom-Json
foreach ($sex in 'Female', 'Male') {
    if (-not (Test-Path (Join-Path $root "data\Textures\Complexion\Thumbs$($sex)_$($thumbs.build)_0.dds"))) {
        throw "no $sex picture atlas of build $($thumbs.build): run python tools\paint\thumbs.py"
    }
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
if (Test-Path $zip) { Remove-Item $zip -Force }
foreach ($dest in $files.Keys) {
    $src = Join-Path $root $files[$dest]
    if (-not (Test-Path $src)) { throw "missing $($files[$dest])" }
    $to = Join-Path $out $dest
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    Copy-Item $src $to
}
# The compiled scripts without this machine's paths in them.
& python (Join-Path $root 'scripts\strip-pex.py') (Join-Path $out 'Scripts') 'Complexion'
if ($LASTEXITCODE) { throw 'strip-pex failed' }

& python (Join-Path $root 'tools\fomod_pack.py') $out $version
if ($LASTEXITCODE) { throw 'the installer does not validate (tools\fomod_pack.py)' }

Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip
$hash = (Get-FileHash $zip).Hash.ToLower()
Write-Host ("packed {0}  {1} bytes  sha256 {2}" -f $zip, (Get-Item $zip).Length, $hash)
Write-Host 'Nothing was uploaded.'
