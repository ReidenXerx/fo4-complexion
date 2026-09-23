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
    build\<Config>\Silhouette.dll (+.pdb)  scripts\build-plugin.ps1
    build\papyrus\Silhouette\*.pex         scripts\build-papyrus.ps1
    data\...                               tools\silhouette_gen.py --write, tools\make_esp.py

  Refused before anything is copied: files the plugin's parser would refuse, a
  compiled player.pex of another generator run, files the verifier fails
  (tools\verify_bodygen.py -- it reads the built bodies in Data, so a body rebuilt
  since the generator ran fails here too), a Silhouette.esp without the refit
  keyword (tools\make_esp.py --check: LooksMenu would move every refit value into
  her own body for good), and a committed manifest edited or deleted (git).

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
foreach ($need in @($dll, (Join-Path $pex 'Bridge.pex'), (Join-Path $pex 'DLL.pex'), (Join-Path $pex 'API.pex'),
                    (Join-Path $pex 'Adopter.pex'), (Join-Path $data 'F4SE\Plugins\Silhouette\catalog.json'),
                    (Join-Path $data 'Silhouette.esp'))) {
    if (-not (Test-Path $need)) { throw "Missing $need - build and generate first." }
}
if (-not (Get-ChildItem $pex -Filter 'player.pex' -ErrorAction SilentlyContinue)) {
    throw "Missing $pex\Player.pex - run scripts\build-papyrus.ps1."
}

# The generated files, read by the plugin's own parser (SilhouetteTests.exe --check): the catalog,
# every manifest, and both BodyGen headers against the catalog's build, stamp and rules hash. What
# the game would refuse at load is refused here.
$tests = Join-Path $root "build\$Config\SilhouetteTests.exe"
if (-not (Test-Path $tests)) { throw "Missing $tests - run scripts\build-plugin.ps1." }
& $tests --check $data
if ($LASTEXITCODE) { throw "the plugin would refuse these generated files - regenerate." }
$catalog = Get-Content (Join-Path $data 'F4SE\Plugins\Silhouette\catalog.json') -Raw | ConvertFrom-Json
# ...and the scripts must be from that run: Player.psc names its build, and so does what was COMPILED
# from it -- the .pex is what ships, and a stale one outlives a regenerated source.
$player = Get-Content (Join-Path $root 'papyrus\Silhouette\Player.psc') -Raw
if ($player -notmatch "Return `"$($catalog.build)`"") {
    throw "papyrus\Silhouette\Player.psc is not build $($catalog.build) - regenerate, then build-papyrus."
}
$pexFile = (Get-ChildItem $pex -Filter 'player.pex').FullName
$pexText = [System.Text.Encoding]::GetEncoding(28591).GetString([System.IO.File]::ReadAllBytes($pexFile))
if (-not $pexText.Contains($catalog.build)) {
    throw "$pexFile was not compiled from build $($catalog.build) - run scripts\build-papyrus.ps1."
}
# The files do what they claim, against the bodies built in Data now.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No python: the verifier (tools\verify_bodygen.py) must pass before a deploy." }
& $python (Join-Path $root 'tools\verify_bodygen.py') --dir $data --psc (Join-Path $root 'papyrus\Silhouette\Player.psc') | Select-Object -Last 3
if ($LASTEXITCODE) { throw "tools\verify_bodygen.py fails these files - see its output; regenerate if a body was rebuilt." }
# The refit keyword (0x803) must be in the esp that lands. LooksMenu resolves a keyed morph by the
# plugin's NAME only: a Silhouette.esp without that form turns every refit value into her own body at
# the next load, for good (wave 3 L5-H1) -- an older build's esp restaged is exactly that.
& $python (Join-Path $root 'tools\make_esp.py') --check (Join-Path $data 'Silhouette.esp')
if ($LASTEXITCODE) { throw "data\Silhouette.esp must not be staged - see the line above." }
# The manifests are history: each says what the bodies of one build are, and saves keep those bodies.
# A committed one edited or deleted misnames bodies no regeneration can repair; a new one is only added.
$git = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $git) { throw "No git: the committed manifests cannot be checked before a deploy." }
# Modified or deleted only: a new manifest, staged or not yet, is how a new build is meant to arrive.
& $git -C $root diff --quiet --diff-filter=MD HEAD -- 'data/F4SE/Plugins/Silhouette/manifests'
switch ($LASTEXITCODE) {
    0 { }
    1 { throw "A committed manifest was edited or deleted (git diff HEAD -- data/F4SE/Plugins/Silhouette/manifests). Restore it: manifests are only ever added." }
    default { throw "git could not compare the manifests with the last commit (exit $LASTEXITCODE)." }
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
# Beside the DLL, a crash logger names Silhouette's functions instead of offsets.
$pdb = [System.IO.Path]::ChangeExtension($dll, '.pdb')
if (Test-Path $pdb) { Copy-Item $pdb (Join-Path $Staging 'F4SE\Plugins\Silhouette.pdb') -Force }
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
                   'Scripts\Silhouette\Bridge.pex', 'Scripts\Silhouette\DLL.pex', 'Scripts\Silhouette\Player.pex',
                   'Silhouette.esp')) {
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
