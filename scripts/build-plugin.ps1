<#
.SYNOPSIS
  Builds Silhouette.dll and runs the offline tests.

.DESCRIPTION
  Configures with the Visual Studio 2022 generator and vcpkg (manifest mode,
  x64-windows-static-md, pinned in CMakeLists.txt), builds, then runs
  build\<Config>\SilhouetteTests.exe. Fails when a single test fails: the tests
  drive the whole director through a fake bridge, so a failure there is a body
  that would come out wrong in the game.

  Then the tools' own tests (tools\tests, Python's unittest): catalog.check()
  against this build's parser, the verifier against damaged copies of data\, the
  markers, the rules and the esp. A tool that lets through what it must refuse
  lets a broken package through every script after it. The verifier cases build
  every body from the game's Data and take a minute or two; without the Data they
  are skipped, and say so.

  Run from PowerShell, not Git Bash: configuring through Git Bash's vcvars route
  silently does nothing on this machine.

  ASCII only. Windows PowerShell 5.1 reads a BOM-less UTF-8 script as ANSI.
#>
[CmdletBinding()]
param(
    [string] $Config = 'Release',
    [string] $Vcpkg  = $(if ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { Join-Path $env:USERPROFILE 'vcpkg' })
)

$ErrorActionPreference = 'Stop'
$root  = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root 'build'

$cmake = (Get-Command cmake -ErrorAction SilentlyContinue).Source
if (-not $cmake) {
    $cmake = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
}
if (-not (Test-Path $cmake)) { throw "No cmake: install the VS 2022 Build Tools (C++ workload)." }
if (-not (Test-Path (Join-Path $root 'extern\CommonLibF4\CommonLibF4\CMakeLists.txt'))) {
    throw "CommonLibF4 is missing: git submodule update --init --recursive"
}
$toolchain = Join-Path $Vcpkg 'scripts\buildsystems\vcpkg.cmake'
if (-not (Test-Path $toolchain)) { throw "No vcpkg at $Vcpkg (set VCPKG_ROOT)." }

& $cmake -S $root -B $build -G 'Visual Studio 17 2022' -A x64 "-DCMAKE_TOOLCHAIN_FILE=$toolchain"
if ($LASTEXITCODE) { throw "configure failed ($LASTEXITCODE)" }
& $cmake --build $build --config $Config
if ($LASTEXITCODE) { throw "build failed ($LASTEXITCODE)" }

$tests = Join-Path $build "$Config\SilhouetteTests.exe"
& $tests
if ($LASTEXITCODE) { throw "$LASTEXITCODE offline test(s) failed" }
# The generated files in data\, read by the plugin's own parser.
& $tests --check (Join-Path $root 'data')
if ($LASTEXITCODE) { throw "the plugin would refuse the generated files in data\ - regenerate." }

# The tools' tests, against the parser just built.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "No python: the tools' tests (tools\tests) must pass with the build." }
$encoding = $env:PYTHONIOENCODING
$testsExe = $env:SILHOUETTE_TESTS_EXE    # whatever the caller set is put back afterwards, not deleted
$env:SILHOUETTE_TESTS_EXE = $tests
$env:PYTHONIOENCODING = 'utf-8'
$ErrorActionPreference = 'Continue'    # unittest reports on stderr: that must not turn into a PowerShell error
& $python -m unittest discover -s (Join-Path $root 'tools\tests') -v 2>&1 | Tee-Object -Variable unitLog | ForEach-Object { "$_" }
$unitExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = $encoding
if ($null -eq $testsExe) { Remove-Item Env:\SILHOUETTE_TESTS_EXE -ErrorAction SilentlyContinue } else { $env:SILHOUETTE_TESTS_EXE = $testsExe }
if ($unitExit) { throw "the tools' tests failed (tools\tests) - every FAIL and ERROR above." }
# The words tools\tests\support.py skips a test that needs the game's Data with.
$noData = @($unitLog | Where-Object { "$_" -match 'no game Data with the bodies here' }).Count -gt 0

$dll = Get-Item (Join-Path $build "$Config\Silhouette.dll")
Write-Host ("built {0}  {1} bytes  {2:yyyy-MM-dd HH:mm:ss}" -f $dll.FullName, $dll.Length, $dll.LastWriteTime)
if ($noData) {
    # Green, and yet the verifier's refusals were never tried: said last, where it cannot scroll away.
    Write-Host "the verifier's damage tests were SKIPPED: no game Data here -- CLAUDE.md rule 5 is untested on this machine" -ForegroundColor Yellow
}
