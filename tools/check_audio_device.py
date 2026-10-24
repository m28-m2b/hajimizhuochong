# -*- coding: utf-8 -*-
"""看看这台机器有没有音频输出设备。"""
import ctypes
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
winmm = ctypes.windll.winmm
n = winmm.waveOutGetNumDevs()
print("waveOut 设备数:", n)
for i in range(n):
    class WAVEOUTCAPS(ctypes.Structure):
        _fields_ = [("wMid", ctypes.c_ushort), ("wPid", ctypes.c_ushort),
                    ("vDriverVersion", ctypes.c_uint),
                    ("szPname", ctypes.c_wchar * 32),
                    ("dwFormats", ctypes.c_uint), ("wChannels", ctypes.c_ushort),
                    ("wReserved1", ctypes.c_ushort),
                    ("dwSupport", ctypes.c_uint)]
    caps = WAVEOUTCAPS()
    rc = winmm.waveOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
    print(f"  [{i}] rc={rc} {caps.szPname} channels={caps.wChannels}")

# 也尝试用 winsound 播一个音，看返回码
import winsound
try:
    winsound.PlaySound(r"sounds\meow_short.wav",
                       winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    print("winsound: 同步播放返回正常")
except Exception as exc:
    print("winsound 失败:", exc)
