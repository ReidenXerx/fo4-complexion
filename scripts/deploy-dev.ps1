<#
.SYNOPSIS
  Copies a complete Silhouette build into its Vortex staging folder.

.DESCRIPTION
  Vortex owns Data/, so the dev build is an ordinary Vortex mod, Silhouette-dev.
  Vortex deploys by HARDLINK: copying over a staged file changes the file the game
  reads at once, with no Deploy. So this refuses while the game runs -- it would
  change a running game's Data under it, and the DLL is held open anyway -- and it
  is ONE session's act: whoever holds the game says it is free first.

  What goes in, all of it built or generated, none of it hand-edited:
    build\<Config>\Silhouette.dll          scripts\build-plugin.ps1
    build\papyrus\Silhouette\*.pex         scripts\build-papyrus.ps1
    data\...                               tools\silhouette_gen.py --write, tools\make_esp.py

  The whole staged tree is replaced (manifests excepted, which are only ever
  added): a file an older build shipped and this one does not would otherwise
  linger in the game.

  ASCII only. Windows PowerShell 5.1 reads a BOM-less UTF-8 script as ANSI.
#>
[CmdletBinding()]
param(
    [string] $Staging = 'D:\Vortex\fallout4\mods\Silhouette-dev',
    [string] $Config  = 'Release'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$game = Get-Process -Name 'Fallout4' -ErrorAction SilentlyContinue
if ($game) {
    throw "Fallout4 is running (PID $($game.Id -join ', ')). Close it before deploying: staged files are hardlinked into Data."
}

$dll  = Join-Path $root "build\$Config\Silhouette.dll"
$pex  = Join-Path $root 'build\papyrus\Silhouette'
$data = Join-Path $root 'data'
foreach ($need in @($dll, (Join-Path $pex 'Bridge.pex'), (Join-Path $pex 'Plugin.pex'), (Join-Path $pex 'API.pex'),
                    (Join-Path $pex 'Adopter.pex'), (Join-Path $data 'F4SE\Plugins\Silhouette\catalog.json'),
                    (Join-Path $data 'Silhouette.esp'))) {
    if (-not (Test-Path $need)) { throw "Missing $need - build and generate first." }
}
if (-not (Get-ChildItem $pex -Filter 'player.pex' -ErrorAction SilentlyContinue)) {
    throw "Missing $pex\Player.pex - run scripts\build-papyrus.ps1."
}

# The generated files must be one generator run, and the scripts from that run: the
# plugin refuses a catalog whose build differs from the BodyGen files, and Player.psc
# names its build too.
$catalog = Get-Content (Join-Path $data 'F4SE\Plugins\Silhouette\catalog.json') -Raw | ConvertFrom-Json
$header  = Get-Content (Join-Path $data 'F4SE\Plugins\F4EE\BodyGen\Loose\Silhouette_templates.ini') -TotalCount 5
if (-not ($header -match "Build $($catalog.build), marker stamp $($catalog.stamp) ")) {
    throw "catalog.json is build $($catalog.build) but the BodyGen templates say otherwise - regenerate."
}
$player = Get-Content (Join-Path $root 'papyrus\Silhouette\Player.psc') -Raw
if ($player -notmatch "Return `"$($catalog.build)`"") {
    throw "papyrus\Silhouette\Player.psc is not build $($catalog.build) - regenerate, then build-papyrus."
}

New-Item -ItemType Directory -Force -Path $Staging | Out-Null
foreach ($old in @('F4SE\Plugins\F4EE', 'MCM', 'Scripts')) {
    $p = Join-Path $Staging $old
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
foreach ($old in @('F4SE\Plugins\Silhouette\catalog.json', 'F4SE\Plugins\Silhouette\Silhouette_presetDistributionConfig.json')) {
    $p = Join-Path $Staging $old
    if (Test-Path $p) { Remove-Item -Force $p }
}

Copy-Item (Join-Path $data 'F4SE') $Staging -Recurse -Force
Copy-Item (Join-Path $data 'MCM') $Staging -Recurse -Force
Copy-Item (Join-Path $data 'Silhouette.esp') $Staging -Force
Copy-Item $dll (Join-Path $Staging 'F4SE\Plugins\Silhouette.dll') -Force
$scripts = Join-Path $Staging 'Scripts\Silhouette'
New-Item -ItemType Directory -Force -Path $scripts | Out-Null
foreach ($f in Get-ChildItem $pex -Filter *.pex) {
    # The compiler writes some names in lower case; the game does not care, a person reading the folder does.
    $name = if ($f.Name -ieq 'player.pex') { 'Player.pex' } else { $f.Name }
    Copy-Item $f.FullName (Join-Path $scripts $name) -Force
}

# What landed, from the disk: a deploy that silently did nothing looks exactly like one that worked.
foreach ($rel in @('F4SE\Plugins\Silhouette.dll', 'F4SE\Plugins\Silhouette\catalog.json',
                   'F4SE\Plugins\F4EE\BodyGen\Loose\Silhouette_templates.ini', 'MCM\Config\Silhouette\keybinds.json',
                   'Scripts\Silhouette\Bridge.pex', 'Scripts\Silhouette\Player.pex', 'Silhouette.esp')) {
    $path = Join-Path $Staging $rel
    if (Test-Path $path) {
        $item = Get-Item $path
        Write-Host ("  {0,-60} {1,9} bytes  {2:HH:mm:ss}" -f $rel, $item.Length, $item.LastWriteTime)
    } else {
        Write-Host "  MISSING: $rel"
    }
}
Write-Host "Staged build $($catalog.build) (stamp $($catalog.stamp)) in $Staging."
Write-Host "New files (the DLL, catalog, keybinds, new scripts) need Vortex's Deploy; Silhouette.esp must be ENABLED for the bridge."
