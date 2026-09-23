<#
.SYNOPSIS
  Builds Silhouette.dll and runs the offline tests.

.DESCRIPTION
  Configures with the Visual Studio 2022 generator and vcpkg (manifest mode,
  x64-windows-static-md, pinned in CMakeLists.txt), builds, then runs
  build\<Config>\SilhouetteTests.exe. Fails when a single test fails: the tests
  drive the whole director through a fake bridge, so a failure there is a body
  that would come out wrong in the game.

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

$dll = Get-Item (Join-Path $build "$Config\Silhouette.dll")
Write-Host ("built {0}  {1} bytes  {2:yyyy-MM-dd HH:mm:ss}" -f $dll.FullName, $dll.Length, $dll.LastWriteTime)
