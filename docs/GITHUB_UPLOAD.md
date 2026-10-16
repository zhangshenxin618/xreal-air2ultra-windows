# 上传 GitHub 与交付

## 上传内容

解压发布包后，将 xreal-air2ultra-windows 目录中的源码、启动器、tests、docs、.github、.gitignore、.gitattributes、README 和许可证上传到新仓库根目录。

GitHub 网页可创建新仓库，再通过 Add file → Upload files 上传。也可用 GitHub Desktop 添加此文件夹为本地仓库后发布。仓库名可使用 xreal-air2ultra-windows，描述可填写：

> Windows camera capture, stereo preview and recording tools for XREAL Air 2 Ultra.

此整理包尚未替你创建远端仓库、推送代码或发布 Release。

## 分享给导师

- 仓库链接：便于阅读代码与文档。
- 源码 ZIP：便于离线下载与运行，需要自行安装 Python 及依赖。
- 项目总结：docs/PROJECT_SUMMARY.md。
- 实测与限制：docs/VALIDATION.md。

## 本地文件管理

Git 忽略 captures、录音录像、.venv、日志和本机设置。继续运行后这些文件仍会在本地生成，不应手动添加进公开仓库。公共发布包刻意不包含当前用户的校准结果，新使用者需自己运行左右镜头确认。

## 测试

本地安装 requirements-lock.txt 后运行 test.cmd，或执行：

```powershell
.venv\Scripts\python.exe -X utf8 tests\run_tests.py
```

上传后 GitHub Actions 会在 Windows/Python 3.13 环境运行相同测试。远端测试尚未执行，以仓库 Actions 页面实际结果为准。
