# 安装与用法 · 哈基米桌宠

## 一、环境要求

| 项目 | 要求 |
| --- | --- |
| 系统 | Windows 10 / 11（用到 `winsound` 和分层窗口颜色键，macOS / Linux 跑不了透明窗口） |
| Python | 3.10 以上（本机实测 3.12.14） |
| 依赖库 | `Pillow`、`numpy`；`tkinter` 是 Python 自带（Windows 官方安装包默认勾选） |
| 其他 | 想重新抓音频才需要 ffmpeg（脚本会自动下载，见第五节） |

检查一下有没有装好：

```bat
python --version
python -c "import tkinter, PIL, numpy; print('ok')"
```

## 二、安装依赖

```bat
cd hajimi-pet
python -m pip install -r requirements.txt
```

如果 `import tkinter` 报错，说明装 Python 时没勾 "tcl/tk and IDLE"，重新运行安装包选 Modify，把 **tcl/tk and IDLE** 勾上。

## 三、启动方式

### 方式 1：双击（推荐）

**双击 `start_hajimi.bat`**。它用 `pythonw.exe` 启动，所以没有黑色控制台窗口，关掉 bat 窗口也不会退出。

`start_hajimi.bat` 里默认写的是一台机器上的 Python 路径，换电脑请把这行改成你自己的 `pythonw.exe`：

```bat
set "PYW=C:\你的Python路径\pythonw.exe"
```

如果这行路径不存在，脚本会自动退回系统 PATH 里的 `pythonw`。

### 方式 2：命令行

```bat
python hajimi_pet.py                  :: 有控制台窗口，方便看报错
pythonw hajimi_pet.py                 :: 无控制台
```

### 方式 3：开机自启

按 `Win + R` 输入 `shell:startup`，把 `start_hajimi.bat` 的**快捷方式**丢进去即可。

## 四、用法

| 操作 | 效果 |
| --- | --- |
| **单击** | 切到下一张梗图 / 下一个表情，同时播放音效 |
| **按住拖动** | 挪动位置 |
| **滚轮** | 放大 / 缩小（0.6× ~ 1.6×） |
| **右键** | 菜单：下一个、随机、梗图/手绘切换、音效开关、自动切换、缩放、关于、退出 |
| **中键** | 随机换一张 |

窗口位置、大小、静音状态会自动保存到 `%APPDATA%\hajimi-pet.json`，下次启动原样恢复。想让它回到右下角，删掉这个文件即可。

### 命令行参数

```bat
python hajimi_pet.py --mode meme --scale 1.2 --pos 1200,700 --auto
python hajimi_pet.py --mute
python hajimi_pet.py --preview preview
python hajimi_pet.py --selftest verify
```

| 参数 | 说明 |
| --- | --- |
| `--mode meme` / `draw` | 梗图模式 / 手绘猫模式（默认有梗图就用梗图） |
| `--memes 目录` | 指定梗图目录，默认 `./memes` |
| `--mute` | 静音启动 |
| `--scale 1.2` | 初始缩放 0.6~1.6 |
| `--expr 5` | 初始序号 |
| `--pos 1200,700` | 初始位置 |
| `--auto` | 启动即开启自动切换（每 12 秒） |
| `--log run.log` | 把启动/切换/音效事件写成 JSONL，便于排查 |
| `--preview 目录` | 只生成表情九宫格、窗口效果图、演示 GIF 后退出 |
| `--selftest 目录` | 进程内跑一遍交互（含音效）并输出 `report.json` |
| `--exit-after 10` | 10 秒后自动退出（调试用） |

## 五、换素材

- **加图**：把 jpg/png/webp 丢进 `memes/`，文件名排序就是切换顺序。
- **加音效**：把 wav 放成 `sounds/pad_10.wav`（短音效，点击优先播）或 `sounds/hajimi_07.wav`（长片段）。
- **从拼图切表情**：
  ```bat
  python tools\split_sheet.py incoming\sheet.jpg
  python tools\add_sheet_memes.py incoming\sheet
  python tools\renumber_memes.py
  ```
- **重新抓音频**（需要 ffmpeg）：
  ```bat
  python tools\get_ffmpeg.py            :: 自动下载 ffmpeg 到 .build/
  python tools\import_pad_sounds.py     :: HajimiPad 音效板第一板块
  python tools\make_hajimi_sounds.py    :: 酷我哈基米原声片段
  ```

## 六、常见问题

| 现象 | 处理 |
| --- | --- |
| 双击 bat 没反应 | 用 `python hajimi_pet.py` 跑一次，看控制台报错；多半是 Python 路径不对或缺 Pillow |
| 看不到猫 | 可能被拖到屏幕边缘，删 `%APPDATA%\hajimi-pet.json` 重启 |
| 没有声音 | 右键菜单确认"音效"勾选；再看音量合成器里 `Python` 是不是被调成 0 |
| 被别的窗口盖住 | 程序每 2 秒会自动置顶一次；仍然被盖就把那个窗口取消置顶 |
| 想彻底退出 | 右键 → 退出，或在任务管理器里结束 `python.exe` / `pythonw.exe` |

## 七、卸载

关掉程序，删除整个 `hajimi-pet` 文件夹，再删掉 `%APPDATA%\hajimi-pet.json` 即可，不写注册表、不装服务。
