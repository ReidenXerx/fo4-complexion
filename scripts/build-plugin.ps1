<#
.SYNOPSIS
  Builds Complexion.dll and runs the offline tests.

.DESCRIPTION
  Configures with the Visual Studio 2022 generator and vcpkg (manifest mode, x64-windows-static-md), builds,
  then runs build\<Config>\ComplexionTests.exe and the composer parity check: the C++ composer must give the
  very picks tools\compose.py gives (the reference), roll for roll.

  Run from PowerShell, not Git Bash: configuring through Git Bash's vcvars route silently does nothing here.

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
$toolchain = Join-Path $Vcpkg 'scripts\buildsystems\vcpkg.cmake'
if (-not (Test-Path $toolchain)) { throw "No vcpkg at $Vcpkg (set VCPKG_ROOT)." }

& $cmake -S $root -B $build -G 'Visual Studio 17 2022' -A x64 "-DCMAKE_TOOLCHAIN_FILE=$toolchain"
if ($LASTEXITCODE) { throw "configure failed ($LASTEXITCODE)" }
& $cmake --build $build --config $Config
if ($LASTEXITCODE) { throw "build failed ($LASTEXITCODE)" }

& python (Join-Path $root 'tools\overlay_tags.py')
if ($LASTEXITCODE) { throw "the tags do not check out (tools\overlay_tags.py)" }

$tests = Join-Path $build "$Config\ComplexionTests.exe"
& $tests
if ($LASTEXITCODE) { throw "$LASTEXITCODE offline test(s) failed" }

$parity = Join-Path $build 'parity.txt'
& python (Join-Path $root 'tools\compose.py') --dump 60 | Set-Content -Encoding ascii $parity
& $tests --parity $parity
if ($LASTEXITCODE) { throw "the C++ composer and tools\compose.py disagree" }

$dll = Get-Item (Join-Path $build "$Config\Complexion.dll")
Write-Host ("built {0}  {1} bytes  {2:yyyy-MM-dd HH:mm:ss}" -f $dll.FullName, $dll.Length, $dll.LastWriteTime)
