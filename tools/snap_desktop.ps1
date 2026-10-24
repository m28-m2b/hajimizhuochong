# Full-screen capture at physical resolution (DPI aware), so layered pet window is included
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class D { [DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int v); }
"@
[void][D]::SetProcessDpiAwareness(2)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
Write-Output ("virtual screen: {0}x{1} at {2},{3}" -f $b.Width, $b.Height, $b.X, $b.Y)
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
$out = Join-Path (Get-Location) "preview\desktop_full.png"
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $out"
