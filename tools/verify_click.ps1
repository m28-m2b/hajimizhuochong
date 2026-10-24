# Verify the Hajimi desktop pet: locate window -> inspect style/size -> post real clicks -> read log
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_click.ps1 -Pid_ 1234 -Log run.log -Clicks 3
param(
    [Parameter(Mandatory = $true)][int]$Pid_,
    [string]$Log = "run.log",
    [int]$Clicks = 3,
    [switch]$Capture,
    [switch]$UseInput
)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class W {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int idx);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool GetLayeredWindowAttributes(IntPtr h, out uint color, out byte alpha, out uint flags);
    [DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int value);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, System.Text.StringBuilder sb, int n);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@ -ErrorAction Stop

try { [void][W]::SetProcessDpiAwareness(2); Write-Host "dpi awareness: per-monitor" }
catch { Write-Host "dpi awareness: unchanged" }

$target = [IntPtr]::Zero
$list = New-Object System.Collections.ArrayList

$proc = [W+EnumProc]{
    param($hwnd, $lp)
    $pid2 = 0
    [void][W]::GetWindowThreadProcessId($hwnd, [ref]$pid2)
    if ($pid2 -eq $Pid_) {
        $rr = New-Object W+RECT
        [void][W]::GetWindowRect($hwnd, [ref]$rr)
        $vis = [W]::IsWindowVisible($hwnd)
        [void]$list.Add([pscustomobject]@{
            HWnd = $hwnd; Visible = $vis
            Pos  = "$($rr.Left),$($rr.Top)"
            Size = "$($rr.Right - $rr.Left)x$($rr.Bottom - $rr.Top)"
            Style = ('0x{0:X8}' -f [W]::GetWindowLong($hwnd, -16))
            ExStyle = ('0x{0:X8}' -f [W]::GetWindowLong($hwnd, -20))
        })
        if ($vis -and ($rr.Right - $rr.Left) -gt 100) { $script:target = $hwnd }
    }
    return $true
}
[void][W]::EnumWindows($proc, [IntPtr]::Zero)

Write-Host "--- windows of pid $Pid_ ---"
$list | Format-Table -AutoSize | Out-String | Write-Host

if ($target -eq [IntPtr]::Zero) { throw "no visible window found for pid $Pid_" }

$r = New-Object W+RECT
[void][W]::GetWindowRect($target, [ref]$r)
$ex = [W]::GetWindowLong($target, -20)
$w = $r.Right - $r.Left
$h = $r.Bottom - $r.Top
Write-Host ("hwnd={0} rect=({1},{2}) size={3}x{4}" -f $target, $r.Left, $r.Top, $w, $h)
Write-Host ("topmost={0} layered={1} transparent={2} toolwindow={3}" -f `
    (($ex -band 0x8) -ne 0), (($ex -band 0x80000) -ne 0), (($ex -band 0x20) -ne 0), (($ex -band 0x80) -ne 0))

$ck = 0; $ca = 0; $cf = 0
if ([W]::GetLayeredWindowAttributes($target, [ref]$ck, [ref]$ca, [ref]$cf)) {
    Write-Host ("layered: colorkey=0x{0:X6} alpha={1} flags=0x{2:X} (colorkeyFlag={3})" -f $ck, $ca, $cf, (($cf -band 1) -ne 0))
}

# 找出 Tk 的 label 子窗口（真实鼠标事件会先投递到子窗口）
$child = [IntPtr]::Zero
$childInfo = ""
$cb2 = [W+EnumProc]{
    param($hwnd, $lp2)
    $rr = New-Object W+RECT
    [void][W]::GetWindowRect($hwnd, [ref]$rr)
    $sb = New-Object System.Text.StringBuilder 64
    [void][W]::GetClassName($hwnd, $sb, 64)
    $script:childInfo += ("child {0} class={1} size={2}x{3}`n" -f $hwnd, $sb.ToString(), ($rr.Right-$rr.Left), ($rr.Bottom-$rr.Top))
    if ($script:child -eq [IntPtr]::Zero -and ($rr.Right - $rr.Left) -ge ($w - 4) -and ($rr.Bottom - $rr.Top) -ge ($h - 4)) {
        $script:child = $hwnd
    }
    return $true
}
[void][W]::EnumChildWindows($target, $cb2, [IntPtr]::Zero)
Write-Host $childInfo.Trim()
if ($child -ne [IntPtr]::Zero) { Write-Host "using child window for clicks: $child" }
else { Write-Host "no matching child window; posting to toplevel" }
$clickTarget = if ($child -ne [IntPtr]::Zero) { $child } else { $target }

if ($Capture) {
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [W]::PrintWindow($target, $hdc, 2)
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    $out = Join-Path (Get-Location) "preview\shot_window.png"
    $bmp.Save($out)
    $bmp.Dispose()
    Write-Host "printwindow=$ok saved=$out"
}

# click point: belly area, away from transparent margins
$cx = [int]($w / 2)
$cy = [int]($h * 0.72)
Write-Host "click at client ($cx,$cy)"

$before = 0
if (Test-Path $Log) { $before = @(Get-Content $Log).Count }

$sx = $r.Left + $cx
$sy = $r.Top + $cy

for ($i = 0; $i -lt $Clicks; $i++) {
    $lp = [IntPtr](($cy -shl 16) -bor $cx)
    if ($UseInput) {
        [void][W]::SetCursorPos($sx, $sy)
        Start-Sleep -Milliseconds 120
        [W]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)   # LEFTDOWN
        Start-Sleep -Milliseconds 70
        [W]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)   # LEFTUP
    } else {
        [void][W]::PostMessage($clickTarget, 0x0200, [IntPtr]0, $lp)   # WM_MOUSEMOVE
        Start-Sleep -Milliseconds 40
        [void][W]::PostMessage($clickTarget, 0x0201, [IntPtr]1, $lp)   # WM_LBUTTONDOWN
        Start-Sleep -Milliseconds 70
        [void][W]::PostMessage($clickTarget, 0x0202, [IntPtr]0, $lp)   # WM_LBUTTONUP
    }
    Start-Sleep -Milliseconds 520
}
Start-Sleep -Milliseconds 300

if ($UseInput) {
    $pt = New-Object W+POINT
    $pt.X = $sx; $pt.Y = $sy
    $under = [W]::WindowFromPoint($pt)
    Write-Host ("input click at screen ({0},{1}); window under point = {2} (pet={3})" -f $sx, $sy, $under, ($under -eq $target))
}

Write-Host "--- new log lines ---"
if (Test-Path $Log) { Get-Content $Log | Select-Object -Skip $before }
else { Write-Host "no log file" }
