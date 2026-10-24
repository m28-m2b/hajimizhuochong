# 哈基米桌面宠物 · 介绍

一只常驻 Windows 桌面的小玩意。无窗口边框、背景全透明、始终置顶，安安静静趴在屏幕角落，点一下就能换表情、顺便"叮"一声。

它现在有 **174 张哈基米梗图**：早期从图库抓的猫猫表情，加上从拼图里自动切格出来的"三角洲鼠鼠"系列（戴头盔、拿枪、红眼猛攻、玻璃大炮）。每张都渲染成白边圆角贴纸，等比例缩放留白，不会把图上的字裁掉。

点一下就换，同时播一段音效。音效共 **27 个**：9 段来自哈基米私人音效板第一板块（私人笑声、哈基米、南北绿豆、曼波、wow、欧耶），点击时优先播这些短音效；6 段是从音乐站抓的哈基米原声；另外 12 个用 numpy 合成，是猫叫、呼噜、低吼、弹跳、星星音。四秒内连点会打断上一段，不叠音。

想安静时右键就能关音效，状态会被记住。菜单里还有随机换一张、每 12 秒自动切换、梗图与手绘互换、放大缩小、退出。

手绘模式是另一套玩法：9 个表情（日常、开心、疑惑、生气、哭哭、心动、震惊、困困、得意），全部由 Pillow 现场绘制，不依赖图片素材，会呼吸起伏、轻微浮动、随机眨眼。

操作很简单：单击换表情，按住拖动挪位置，滚轮缩放（0.6 到 1.6 倍），右键出菜单。位置、大小、静音状态都会自动保存。

技术上它是 Python 3.12 + Tk 8.6 + Pillow。透明窗口用无边框叠加颜色键（`#FF00FF`），合成时 alpha 二值化但保留原色，边缘不泛粉；动画做了 2 像素量化和帧签名，画面没变化就不重绘，静止约占单核 4% 到 5%，内存 60MB 左右。

十二项自测全部通过：连点切换、拖动不误触、滚轮缩放、点满一圈回到起点、每帧出图、点击触发音效、静音不响。素材来源记在 `memes/sources.json` 和 `sounds/hajimi_sources.json`，仅供个人桌面娱乐。

---

## English version

A tiny desktop companion for Windows. No window frame, fully transparent background, always on top — it just sits in the corner, and one click swaps its face with a little sound.

It ships with **174 Hajimi memes**: cat reaction images plus a "Delta Force mouse" set (helmet, rifle, red-eyed rage) split automatically out of collage sheets. Every image is rendered as a rounded sticker with a white border, letterboxed so captions never get cropped.

Clicking swaps the picture and plays one of **27 sounds**: nine short pads from the HajimiPad soundboard (private laughs, Hajimi, Nanbei Lüdou, Mambo, wow, oye), six longer Hajimi clips, and twelve synthesized meows, purrs, growls and sparkles. Rapid clicks cut off the previous sound instead of overlapping.

Right-click mutes it (remembered), picks a random one, enables 12-second auto switching, toggles between meme and hand-drawn mode, resizes, or quits. Drag to move, scroll to zoom 0.6–1.6×.

The hand-drawn mode is a separate set of nine expressions drawn entirely in Pillow — breathing, floating, blinking — with no image assets at all.

It is built with Python 3.12, Tk 8.6 and Pillow. Transparency uses a borderless layered window with a colour key, compositing alpha to binary while keeping original RGB so edges never pick up a pink fringe. Frames are quantized to 2 px and signature-checked so unchanged frames are skipped: about 4–5% of one core at rest, ~60 MB RAM.

All twelve self-checks pass: click to advance, drag without misfiring, wheel zoom, one full cycle returning to the start, frame rendering, sound on switch, and silence when muted. Asset sources are recorded in `memes/sources.json` and `sounds/hajimi_sources.json`; personal desktop use only.
