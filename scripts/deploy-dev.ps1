<#
.SYNOPSIS
  Stages the dev build of Complexion into Vortex: D:\Vortex\fallout4\mods\Complexion-dev.

.DESCRIPTION
  Copies what the game loads -- Complexion.dll (+ .pdb), its data (profiles.json, tags.json), the compiled
  scripts, Complexion.esp and the MCM page -- into the staging folder, file by file in place: a file Vortex
  already hardlinked into Data changes there at once; a NEW file waits for Vortex's Deploy (shared memory:
  vortex-staging-halfdeploy). Refuses while Fallout 4 runs.

  Build first: scripts\build-plugin.ps1, scripts\build-papyrus.ps1, python tools\make_data.py,
  python tools\make_esp.py data\Complexion.esp.

  ASCII only. Windows PowerShell 5.1 reads a BOM-less UTF-8 script as ANSI.
#>
[CmdletBinding()]
param(
    [string] $Config  = 'Release',
    [string] $Staging = 'D:\Vortex\fallout4\mods\Complexion-dev',
    [string] $Data    = 'D:\SteamFreeGames\Fallout 4 AE\Data'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

if (Get-Process -Name 'Fallout4*' -ErrorAction SilentlyContinue) {
    throw 'Fallout 4 is running: close it before staging (the DLL is locked while the game runs).'
}

$files = [ordered]@{
    'F4SE\Plugins\Complexion.dll'                 = "build\$Config\Complexion.dll"
    'F4SE\Plugins\Complexion.pdb'                 = "build\$Config\Complexion.pdb"
    'F4SE\Plugins\Complexion\profiles.json'       = 'data\F4SE\Plugins\Complexion\profiles.json'
    'F4SE\Plugins\Complexion\tags.json'           = 'data\F4SE\Plugins\Complexion\tags.json'
    'Scripts\Complexion\Bridge.pex'               = 'build\papyrus\Complexion\Bridge.pex'
    'Scripts\Complexion\DLL.pex'                  = 'build\papyrus\Complexion\DLL.pex'
    'Scripts\Complexion\Persona.pex'              = 'build\papyrus\Complexion\Persona.pex'
    'Complexion.esp'                              = 'data\Complexion.esp'
    'MCM\Config\Complexion\config.json'           = 'data\MCM\Config\Complexion\config.json'
    'MCM\Config\Complexion\settings.ini'          = 'data\MCM\Config\Complexion\settings.ini'
}

# Complexion's own overlays (tools\paint\make_marks.py): every file under these folders, as it is.
foreach ($tree in 'Textures\Overlays\Complexion', 'Materials\Overlays\Complexion', 'F4SE\Plugins\F4EE\Overlays\Complexion.esp', 'F4SE\Plugins\RobCo_Patcher\race') {
    $dir = Join-Path $root "data\$tree"
    if (-not (Test-Path $dir)) { throw "missing data\$tree - run python tools\paint\make_marks.py" }
    Get-ChildItem $dir -File -Recurse | ForEach-Object {
        $files[$_.FullName.Substring((Join-Path $root 'data').Length + 1)] = $_.FullName.Substring($root.Length + 1)
    }
}

& python (Join-Path $root 'tools\make_esp.py') --check (Join-Path $root 'data\Complexion.esp')
if ($LASTEXITCODE) { throw 'Complexion.esp is refused: rebuild it with tools\make_esp.py' }

$waits = @()
foreach ($dest in $files.Keys) {
    $src = Join-Path $root $files[$dest]
    if (-not (Test-Path $src)) { throw "missing $($files[$dest]) - build it first" }
    $to = Join-Path $Staging $dest
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    if (Test-Path $to) {
        # In place: Vortex's hardlink in Data sees the new bytes at once.
        [System.IO.File]::WriteAllBytes($to, [System.IO.File]::ReadAllBytes($src))
    } else {
        Copy-Item $src $to
    }
    $item = Get-Item $to
    Write-Host ("  {0,-48} {1,9} bytes  {2:HH:mm:ss}" -f $dest, $item.Length, $item.LastWriteTime)
    $live = Join-Path $Data $dest
    if (-not (Test-Path $live) -or (Get-Item $live).Length -ne $item.Length) { $waits += $dest }
}
Write-Host "Staged in $Staging."
if ($waits.Count) {
    Write-Host "Not in Data yet (waits for Vortex's Deploy):" -ForegroundColor Yellow
    $waits | ForEach-Object { Write-Host "  $_" }
    Write-Host 'Enable Complexion-dev in Vortex and press Deploy BEFORE starting the game. Complexion.esp must be enabled.' -ForegroundColor Yellow
}
