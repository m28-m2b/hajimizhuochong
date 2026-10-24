# Capture the live pet window several times (PrintWindow) to prove the content changes
param(
    [Parameter(Mandatory = $true)][int]$Pid_,
    [int]$Count = 6,
    [int]$IntervalMs = 1400,
    [string]$OutDir = "preview\shots"
)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class C {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int v);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[void][C]::SetProcessDpiAwareness(2)
Add-Type -AssemblyName System.Drawing

$target = [IntPtr]::Zero
$proc = [C+EnumProc]{
    param($hwnd, $lp)
    $procId = 0
    [void][C]::GetWindowThreadProcessId($hwnd, [ref]$procId)
    if ($procId -eq $Pid_ -and [C]::IsWindowVisible($hwnd)) {
        $rr = New-Object C+RECT
        [void][C]::GetWindowRect($hwnd, [ref]$rr)
        if (($rr.Right - $rr.Left) -gt 100) { $script:target = $hwnd }
    }
    return $true
}
[void][C]::EnumWindows($proc, [IntPtr]::Zero)
if ($target -eq [IntPtr]::Zero) { throw "pet window not found" }

$r = New-Object C+RECT
[void][C]::GetWindowRect($target, [ref]$r)
$w = $r.Right - $r.Left
$h = $r.Bottom - $r.Top
$dir = Join-Path (Get-Location) $OutDir
New-Item -ItemType Directory -Force -Path $dir | Out-Null

for ($i = 1; $i -le $Count; $i++) {
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [C]::PrintWindow($target, $hdc, 2)
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    $path = Join-Path $dir ("shot{0:D2}.png" -f $i)
    $bmp.Save($path)
    $bmp.Dispose()
    Write-Output ("capture {0}: {1} ({2}x{3}) ok={4}" -f $i, $path, $w, $h, $ok)
    if ($i -lt $Count) { Start-Sleep -Milliseconds $IntervalMs }
}
