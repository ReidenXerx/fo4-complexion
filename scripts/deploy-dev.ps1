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
  compiled player.pex of another generator run, a Silhouette.esp without the refit
  keyword (tools\make_esp.py --check: LooksMenu would move every refit value into
  her own body for good), files the verifier fails (tools\verify_bodygen.py -- it
  reads the built bodies in Data, so a body rebuilt since the generator ran fails
  here too), and a committed manifest edited or deleted (git; run from the
  fo4-silhouette checkout itself).

  Staged IN PLACE, file by file (Copy-Item -Force writes into the existing file and
  keeps its inode): every file Data already links goes live at once, all together,
  and only a genuinely NEW file waits for Vortex's Deploy -- listed by name at the
  end. Removing and re-copying a folder instead made every restage half-deployed
  until the Deploy: a new esp and DLL beside the old scripts (wave 4). A file an
  older build shipped and this one does not is removed from staging (manifests
  excepted: they are only ever added), and the Deploy takes it out of Data.

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
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No python: the verifier (tools\verify_bodygen.py) must pass before a deploy." }
# The refit keyword (0x803) must be in the esp that lands, and this is the plain answer why not: first,
# before the verifier (which refuses the same esp among everything else). LooksMenu resolves a keyed
# morph by the plugin's NAME only: a Silhouette.esp without that form turns every refit value into her
# own body at the next load, for good (wave 3 L5-H1) -- an older build's esp restaged is exactly that.
& $python (Join-Path $root 'tools\make_esp.py') --check (Join-Path $data 'Silhouette.esp')
if ($LASTEXITCODE) { throw "data\Silhouette.esp must not be staged - see the line above." }
# The files do what they claim, against the bodies built in Data now. On a failure every line is shown:
# a cut-off tail once hid the one reason that mattered.
$verify = @(& $python (Join-Path $root 'tools\verify_bodygen.py') --dir $data --psc (Join-Path $root 'papyrus\Silhouette\Player.psc'))
if ($LASTEXITCODE) {
    $verify | ForEach-Object { Write-Host $_ }
    throw "tools\verify_bodygen.py fails these files - every line above; regenerate if a body was rebuilt."
}
$verify | Select-Object -Last 3 | ForEach-Object { Write-Host $_ }
# The manifests are history: each says what the bodies of one build are, and saves keep those bodies.
# A committed one edited or deleted misnames bodies no regeneration can repair; a new one is only added.
$git = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $git) { throw "No git: the committed manifests cannot be checked before a deploy." }
# Only from this checkout itself: a copy without .git cannot be compared, and a copy inside another
# repository would be compared with THAT repository's commit and pass whatever it holds.
$ErrorActionPreference = 'Continue'    # git's stderr must not turn into a PowerShell error here
$top = & $git -C $root rev-parse --show-toplevel 2>$null
$topExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($topExit -or -not $top -or ([System.IO.Path]::GetFullPath(($top | Select-Object -First 1).Trim()).TrimEnd('\') -ine
                                  [System.IO.Path]::GetFullPath($root).TrimEnd('\'))) {
    throw "Run this from the fo4-silhouette git checkout: the manifest guard compares data\F4SE\Plugins\Silhouette\manifests with the last commit, and $root is not the top of a git work tree of its own."
}
# Modified or deleted only: a new manifest, staged or not yet, is how a new build is meant to arrive.
# --no-renames: a manifest renamed is one deleted, whatever git would call it.
& $git -C $root diff --quiet --no-renames --diff-filter=MD HEAD -- 'data/F4SE/Plugins/Silhouette/manifests'
switch ($LASTEXITCODE) {
    0 { }
    1 { throw "A committed manifest was edited or deleted (git diff HEAD -- data/F4SE/Plugins/Silhouette/manifests). Restore it: manifests are only ever added." }
    default { throw "git could not compare the manifests with the last commit (exit $LASTEXITCODE)." }
}

# Everything this build ships, staging path -> source. Keys compare in any case, as NTFS names do: a
# staged 'player.pex' IS Player.pex, and must never be taken for a file this build no longer ships.
$ship = New-Object 'System.Collections.Specialized.OrderedDictionary' ([System.StringComparer]::OrdinalIgnoreCase)
$dataFull = (Get-Item -LiteralPath $data).FullName.TrimEnd('\')
foreach ($f in Get-ChildItem -LiteralPath $data -Recurse -File) {
    $ship[$f.FullName.Substring($dataFull.Length).TrimStart('\')] = $f.FullName
}
$ship['F4SE\Plugins\Silhouette.dll'] = $dll
# Beside the DLL, a crash logger names Silhouette's functions instead of offsets.
$pdb = [System.IO.Path]::ChangeExtension($dll, '.pdb')
if (Test-Path $pdb) { $ship['F4SE\Plugins\Silhouette.pdb'] = $pdb }
foreach ($f in Get-ChildItem $pex -Filter *.pex) {
    # The compiler writes some names in lower case; the game does not care, a person reading the folder does.
    $name = if ($f.Name -ieq 'player.pex') { 'Player.pex' } else { $f.Name }
    $ship["Scripts\Silhouette\$name"] = $f.FullName
}

# In place, file by file: Copy-Item -Force writes INTO an existing file, so its hardlink in Data carries
# the new bytes at once. A file that did not exist has no link in Data until Vortex's Deploy.
New-Item -ItemType Directory -Force -Path $Staging | Out-Null
$new = @()
foreach ($rel in $ship.Keys) {
    $dest = Join-Path $Staging $rel
    if (-not (Test-Path -LiteralPath $dest)) { $new += $rel }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath $ship[$rel] -Destination $dest -Force
}

# What an older build shipped and this one does not: out of staging (Vortex's Deploy then takes it out of
# Data). Only Silhouette's own places are looked at, and never a manifest -- an NPC of that build keeps
# its stamp for the rest of the save.
$owned = @('F4SE\Plugins\Silhouette', 'F4SE\Plugins\F4EE\BodyGen\Loose', 'MCM\Config\Silhouette', 'Scripts\Silhouette')
$stageFull = (Get-Item -LiteralPath $Staging).FullName.TrimEnd('\')
$stale = @()
foreach ($dir in $owned) {
    $p = Join-Path $Staging $dir
    if (-not (Test-Path $p)) { continue }
    foreach ($f in Get-ChildItem -LiteralPath $p -Recurse -File) {
        $rel = $f.FullName.Substring($stageFull.Length).TrimStart('\')
        if ($rel -like 'F4SE\Plugins\Silhouette\manifests\*') { continue }
        if ($rel -like 'F4SE\Plugins\F4EE\BodyGen\Loose\*' -and $f.Name -notlike 'Silhouette_*') { continue }
        if (-not $ship.Contains($rel)) { $stale += $rel; Remove-Item -LiteralPath $f.FullName -Force }
    }
}
foreach ($rel in @('F4SE\Plugins\Silhouette.dll', 'F4SE\Plugins\Silhouette.pdb', 'Silhouette.esp')) {
    if (-not $ship.Contains($rel) -and (Test-Path (Join-Path $Staging $rel))) {
        $stale += $rel; Remove-Item -LiteralPath (Join-Path $Staging $rel) -Force
    }
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
Write-Host "Staged build $($catalog.build) (stamp $($catalog.stamp)) in $Staging, file by file in place."
if ($new.Count -eq 0 -and $stale.Count -eq 0) {
    Write-Host "Every file went live in place through its hardlink: no Deploy is needed."
} else {
    if ($new.Count) {
        Write-Host "NEW in staging -- no hardlink in Data until Vortex's Deploy:"
        $new | ForEach-Object { Write-Host "  $_" }
    }
    if ($stale.Count) {
        Write-Host "No longer shipped, removed from staging -- still in Data until Vortex's Deploy:"
        $stale | ForEach-Object { Write-Host "  $_" }
    }
    $until = @()
    if ($new.Count) { $until += 'lacks the new files' }
    if ($stale.Count) { $until += 'still holds the removed ones' }
    Write-Host ("Press Deploy in Vortex BEFORE starting the game: until then Data " + ($until -join ' and ') + " listed above.")
}
Write-Host "Silhouette.esp must be ENABLED for the bridge."
