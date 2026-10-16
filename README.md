# XREAL Air 2 Ultra Camera for Windows

基于 [sean9061/xreal-air2ultra-camera](https://github.com/sean9061/xreal-air2ultra-camera) 的 Windows 实验性适配。读取 Air 2 Ultra 双目追踪摄像头，还原原始画面，支持预览、普通模式透视显示、录制及离线处理。

**已在一副 Air 2 Ultra 上跑通 Windows 摄像头采集。眼镜内的 SBS 立体显示尚未验证；本项目不是完整的深度、定位或 SLAM 系统。**

## 功能

- 按设备名定向读取眼镜，通过 FFmpeg DirectShow 保留未经颜色转换的原始字节。
- 分块图像还原、方向与镜像调整、条纹清理；单路和双目实时预览。
- 根据遥测中的共享编号配对双目帧，处理顺序变化和缺帧。
- 通过遮挡左右镜头交叉确认物理左右对应，并保存设置。
- 普通 2D 模式下单路全屏显示；另提供完整 SBS 输出入口及分眼测试图。
- PNG 截图、MP4 录制；支持麦克风 WAV 采集及 AAC 音轨合成。
- 原始数据录制、离线单路/双目 MP4 导出；不需要眼镜在线。

## 环境与安装

本地验证环境：Windows x64、Python 3.13、Air 2 Ultra、支持数据传输的 USB-C 连接。眼镜全屏显示还需要视频输出与扩展屏连接。安装 Python 时启用 PATH。

双击 `start.cmd` 即可创建 `.venv` 并安装锁定依赖。首次需要联网，后续使用本地环境。命令行安装方式：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe xreal_windows.py --view stereo
```

Windows 设置中需允许桌面应用访问相机；需要录音时也需允许麦克风访问。一次只运行一个摄像头预览。

## 启动入口

| 脚本 | 用途 |
|---|---|
| `start.cmd` | 单路预览 |
| `start-stereo.cmd` | 双目并排预览 |
| `start-passthrough-2d.cmd` | 普通模式眼镜全屏；选择眼镜对应屏幕 |
| `start-passthrough.cmd` | 完整 SBS 模式的双目全屏实验 |
| `confirm-cameras.cmd` | 按提示遮挡左右镜头，确认对应关系 |
| `test-eyes.cmd` | 完整 SBS 屏幕上的 LEFT/RIGHT 分眼测试图 |
| `list-displays.cmd` | 列出活动显示器 |
| `list-audio.cmd` | 列出麦克风输入 |
| `diagnose.cmd` | 短时检查眼镜数据 |
| `export-video.cmd` | 离线导出原始录制 |
| `test.cmd` | 运行不使用硬件的回归测试 |

普通 2D 模式不需要切换 3D，两眼看到同一路画面。立体入口要求完整 SBS 屏幕（例如 3840×1080），不会自动切换眼镜或修改 Windows 显示设置。屏幕编号可能变化，请按当前列表选择。

## 按键

先点击预览窗口或启动终端，再直接按键，无需回车。

| 按键 | 功能 |
|---|---|
| `q` / Esc | 退出并结束录制 |
| `v` | 开始/停止 MP4 录像；默认尝试同时录音 |
| `b` | 开始/停止原始数据录制 |
| `s` | 截图 |
| `r` | 两路各自旋转 180° |
| `1` / `2` | 分别旋转原始组 0 / 1 |
| `m` | 两路水平镜像切换 |
| `3` / `4` | 分别切换原始组 0 / 1 镜像 |
| `x` | 交换双目位置 |
| `c` | 开关条纹清理 |
| `f` | 开关全屏 |

旋转、镜像、左右交换保存在 `view-settings.json`。首次默认对两路进行水平镜像校正；不同使用方式请按实际画面调整。新电脑应运行左右确认向导，不要沿用其他人的映射。

## 录像、声音与导出

输出默认在 `captures/`。`v` 保存处理后的画面，单路 480×640，双目 960×640；不把全屏黑边和操作提示录入。30 fps 时间轴通过保持前帧补偿丢帧间隙，CSV 记录收到帧的相对时间。

录音默认优先选择眼镜麦克风，未发现时使用系统默认输入。开始时显示设备名；`REC + MIC` 表示已打开麦克风，`REC VIDEO ONLY` 表示无录音。停止后等待合成，最终带声音文件为 `*_with_audio.mp4`；无声原视频和 WAV 也保留。可指定输入编号或禁用声音：

```powershell
.\start-stereo.cmd --audio-device 24
.\start-stereo.cmd --no-audio
```

编号只是示例，请先运行 `list-audio.cmd`。目前音轨合成已测试，真实麦克风采集仍需用户本机验证；若报告 `AUDIO UNAVAILABLE`，请检查麦克风权限、设备状态及占用情况。系统扬声器回放不在采集范围内。

`b` 保存交给预览程序的完整原始帧、时间表和录制开始时的方向设置；即使单路预览，也保存两组收到的数据。约 60 fps 时每分钟约 1.1 GB。退出后双击 `export-video.cmd`，输入 `raw_…` 文件夹路径，默认导出双目视频到其 `exported/` 子目录。单路示例：

```powershell
.\export-video.cmd "D:\captures\raw_123" --view mono --camera 0
```

原始数据和离线导出目前不含音频。录制中途对预览的设置调整不会更新原始录制开始时的设置快照。

## 测试与验证边界

```powershell
.venv\Scripts\python.exe -X utf8 tests\run_tests.py
```

测试使用合成数据、临时文件及模拟设备，不打开摄像头、麦克风或显示窗口，不包含个人实拍图像。覆盖异常帧恢复、双目乱序/缺帧、镜像旋转、原始数据读写、MP4/AAC 编解码、音频时间补偿、左右遮挡判定等。GitHub Actions 配置为 Windows/Python 3.13，远端结果以实际运行日志为准。

开发期间实际摄像头采集曾连续解码 300 帧、配成 150 对；物理遮挡确认了当前设备的左右映射。音频实录、SBS 分眼显示及几何标定尚未完成硬件验证。详见 [验证记录](docs/VALIDATION.md)。

## 限制

- 当前原生遥测布局只在一副 Air 2 Ultra 上验证，不保证适用所有固件。
- 没有相机标定、立体校正、视野匹配、深度估计、SLAM 或 IMU 融合。
- 原始录制不是无丢帧保证：处理过慢时采集队列可能丢帧，时间戳是软件收到数据的时间。
- 音视频起点为软件时间补偿，不是曝光与采样的硬件同步；实际延迟及长时间漂移需测量。
- 双目预览不等于已经验证的立体透视。普通模式两眼显示同一路图像。

## 代码结构与许可

模块说明见 [架构文档](docs/ARCHITECTURE.md)，导师交流可参考 [项目总结](docs/PROJECT_SUMMARY.md)。

MIT License，保留上游版权。来源、修改范围和第三方依赖说明见 [NOTICE.md](NOTICE.md) 与 [LICENSE](LICENSE)。本项目不随包携带依赖二进制、录制数据、日志、个人设置或本机环境。
