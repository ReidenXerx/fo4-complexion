<#
.SYNOPSIS
  Compiles the overlay window (C-19, ported from Silhouette S-79): interface\src\*.as into build\interface\ComplexionMenu.swf.

.DESCRIPTION
  Apache Flex 4.16.1's mxmlc on the machine's Java, against playerglobal 11.2 -- Flash Player 11.2 and SWF
  version 15, what Adobe Animate publishes for Fallout 4's Scaleform. No Animate and no .fla: the window
  is code, so every change is a diff.

  One-time setup, in -Flex (default D:\Tools\flex\sdk): unzip apache-flex-sdk-4.16.1-bin.zip
  (archive.apache.org/dist/flex/4.16.1/binaries), put playerglobal.swc for 11.2 at
  frameworks\libs\player\11.2\playerglobal.swc, and replace {playerglobalHome} in
  frameworks\flex-config.xml with the absolute frameworks\libs\player path.

  ASCII only. Windows PowerShell 5.1 reads a BOM-less UTF-8 script as ANSI.
#>
[CmdletBinding()]
param(
    [string] $Flex = 'D:\Tools\flex\sdk'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src  = Join-Path $root 'interface\src'
$out  = Join-Path $root 'build\interface'
$swf  = Join-Path $out 'ComplexionMenu.swf'
$jar  = Join-Path $Flex 'lib\mxmlc.jar'

if (-not (Test-Path $jar)) { throw "No mxmlc at $jar - see this script's setup notes." }
if (-not (Test-Path (Join-Path $Flex 'frameworks\libs\player\11.2\playerglobal.swc'))) {
    throw "No playerglobal.swc for Flash Player 11.2 under $Flex\frameworks\libs\player\11.2."
}
New-Item -ItemType Directory -Force $out | Out-Null

$java = (Get-Command java -ErrorAction SilentlyContinue).Source
if (-not $java) { throw "java is not on PATH (mxmlc runs on it)." }

Push-Location $Flex
try {
    # Every argument quoted: PowerShell splits a bare -name=1.2 before Java sees it, and mxmlc then refuses
    # "default arguments interspersed with other options".
    $arguments = @('-Xmx1024m', '-jar', $jar, '+flexlib=frameworks', '-target-player=11.2', '-swf-version=15',
        '-static-link-runtime-shared-libraries=true', "-source-path=$src", "-output=$swf", (Join-Path $src 'ComplexionMenu.as'))
    $output = & $java $arguments 2>&1
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
$output | ForEach-Object { "  $_" }
if ($code -ne 0 -or -not (Test-Path $swf)) { throw "mxmlc failed ($code)." }
$f = Get-Item $swf
"built {0}  {1} bytes  {2:yyyy-MM-dd HH:mm:ss}" -f $f.FullName, $f.Length, $f.LastWriteTime
