# 来源与授权

本项目是在 Windows 上实现的 XREAL Air 2 Ultra 摄像头实验工具，不是 XREAL 官方驱动，也未获得 XREAL 背书。

- 上游项目：[sean9061/xreal-air2ultra-camera](https://github.com/sean9061/xreal-air2ultra-camera)，MIT License，Copyright (c) 2026 sean9061。
- 分块重排表最初由 [mazeasdamien/myXreal](https://github.com/mazeasdamien/myXreal) 发现，上游已有明确致谢。
- 本地新增内容包括 Windows 定向采集、当前设备遥测适配、录制/导出、麦克风录制合成、交互入口与测试。

保留上游 LICENSE 和 LICENSE-upstream.txt，继续使用 MIT 许可。未擅自添加用户姓名或机构作为版权所有者。发布者可在确认归属后为自己的新增贡献补充版权信息，不应删除上游版权声明。

第三方 Python 依赖及 FFmpeg 各自适用其自身许可证。当前仓库只记录依赖，不随包分发它们的二进制文件；imageio-ffmpeg 安装包会提供其 FFmpeg 可执行文件。本项目的 MIT 许可不替代依赖各自的许可。
