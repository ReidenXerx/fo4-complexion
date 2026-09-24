<#
.SYNOPSIS
  Packs a release archive of Silhouette: the Data layout, ready for a mod manager.

.DESCRIPTION
  Assembles build\dist\Silhouette-<version>\ from the same built and generated
  files deploy-dev.ps1 stages, checks they are one generator run, and zips it to
  build\dist\Silhouette-<version>.zip. It does NOT publish anything: uploading
  is the owner's act, always. (Not build\release: on NTFS that IS build\Release,
  where the DLL is built and which a clean build empties.)

  README.md and LICENSE go inside the archive at F4SE\Plugins\Silhouette\, beside
  the plugin's own files (owner, 2026-09-24): nothing lands loose in Data's root,
  where every other mod's README would collide with it.

  Before packing, the tools' own tests run with SILHOUETTE_REQUIRE_DATA=1: a test
  that needs the game's Data fails without it instead of being skipped, so a
  release never passes with the verifier's refusals untested.

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
$out     = Join-Path $root "build\dist\Silhouette-$version"
$zip     = "$out.zip"

$dll  = Join-Path $root "build\$Config\Silhouette.dll"
$pex  = Join-Path $root 'build\papyrus\Silhouette'
$data = Join-Path $root 'data'
if (-not (Test-Path $dll)) { throw "Missing $dll - run scripts\build-plugin.ps1." }
if (-not (Test-Path (Join-Path $pex 'Bridge.pex'))) { throw "Missing scripts - run scripts\build-papyrus.ps1." }

# The generated files, read by the plugin's own parser (SilhouetteTests.exe --check): the catalog,
# every manifest, and both BodyGen headers against the catalog's build, stamp and rules hash. What
# the game would refuse at load is refused here.
$tests = Join-Path $root "build\$Config\SilhouetteTests.exe"
if (-not (Test-Path $tests)) { throw "Missing $tests - run scripts\build-plugin.ps1." }
& $tests --check $data
if ($LASTEXITCODE) { throw "the plugin would refuse these generated files - regenerate." }
$catalog = Get-Content (Join-Path $data 'F4SE\Plugins\Silhouette\catalog.json') -Raw | ConvertFrom-Json
# The compiled picker script must be of that run: the .pex is what ships.
$pexFile = (Get-ChildItem $pex -Filter 'player.pex' -ErrorAction SilentlyContinue).FullName
if (-not $pexFile) { throw "Missing $pex\Player.pex - run scripts\build-papyrus.ps1." }
$pexText = [System.Text.Encoding]::GetEncoding(28591).GetString([System.IO.File]::ReadAllBytes($pexFile))
if (-not $pexText.Contains($catalog.build)) {
    throw "$pexFile was not compiled from build $($catalog.build) - run scripts\build-papyrus.ps1."
}
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No python: the verifier (tools\verify_bodygen.py) must pass before a release." }
# Never pack a Silhouette.esp without the refit keyword (0x803): LooksMenu resolves a keyed morph by the
# plugin's NAME only, so such an esp turns every refit value into her own body for good (wave 3 L5-H1).
# First, so its plain reason is the one shown -- the verifier refuses the same esp among everything else.
& $python (Join-Path $root 'tools\make_esp.py') --check (Join-Path $data 'Silhouette.esp')
if ($LASTEXITCODE) { throw "data\Silhouette.esp must not be packed - see the line above." }
# ...and the files do what they claim. On a failure every line is shown, not a tail.
$verify = @(& $python (Join-Path $root 'tools\verify_bodygen.py') --dir $data --psc (Join-Path $root 'papyrus\Silhouette\Player.psc'))
if ($LASTEXITCODE) {
    $verify | ForEach-Object { Write-Host $_ }
    throw "tools\verify_bodygen.py fails these files - every line above."
}
$verify | Select-Object -Last 3 | ForEach-Object { Write-Host $_ }
# ...nor a committed manifest edited or deleted: it is what the bodies of its build are, in every save.
$git = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $git) { throw "No git: the committed manifests cannot be checked before a release." }
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
# ...and the tools that made and proved all of the above pass their own tests, against this parser, with the
# game's Data REQUIRED: a skip here would be a release whose verifier was never shown to refuse anything.
$docs = @('README.md', 'LICENSE') | ForEach-Object { Join-Path $root $_ }
foreach ($d in $docs) { if (-not (Test-Path $d)) { throw "Missing $d - the archive carries it (the GPL wants the licence shipped)." } }
$saved = @{ exe = $env:SILHOUETTE_TESTS_EXE; req = $env:SILHOUETTE_REQUIRE_DATA; enc = $env:PYTHONIOENCODING }
$env:SILHOUETTE_TESTS_EXE = $tests
$env:SILHOUETTE_REQUIRE_DATA = '1'
$env:PYTHONIOENCODING = 'utf-8'
$ErrorActionPreference = 'Continue'    # unittest reports on stderr: that must not turn into a PowerShell error
& $python -m unittest discover -s (Join-Path $root 'tools\tests')
$unitExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
foreach ($pair in @(@('SILHOUETTE_TESTS_EXE', $saved.exe), @('SILHOUETTE_REQUIRE_DATA', $saved.req), @('PYTHONIOENCODING', $saved.enc))) {
    if ($null -eq $pair[1]) { Remove-Item "Env:\$($pair[0])" -ErrorAction SilentlyContinue } else { Set-Item "Env:\$($pair[0])" $pair[1] }
}
if ($unitExit) { throw "the tools' tests failed (tools\tests) - every FAIL and ERROR above; nothing was packed." }

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
foreach ($d in $docs) {
    Copy-Item $d (Join-Path $out 'F4SE\Plugins\Silhouette') -Force
}

Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip -CompressionLevel Optimal
$item = Get-Item $zip
Write-Host ("packed {0}  {1} bytes: build {2}, stamp {3}" -f $item.FullName, $item.Length, $catalog.build, $catalog.stamp)
# The PDB stays out of the archive (twenty times the DLL) but beside it: a user's crash log is read
# against the exact build that crashed.
$pdb = [System.IO.Path]::ChangeExtension($dll, '.pdb')
if (Test-Path $pdb) {
    Copy-Item $pdb "$out.pdb" -Force
    Write-Host "kept $out.pdb for reading crash logs of this build (not in the archive)"
}
Write-Host "Nothing was uploaded."
