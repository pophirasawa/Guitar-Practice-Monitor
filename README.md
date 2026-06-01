# Guitar Practice Monitor

[English](README.en.md)

Guitar Practice Monitor 是一个轻量的桌面吉他练习记录器，支持 Windows 和 macOS。

它把桌面浮窗和本地练习记录结合起来，让日常练琴没那么枯燥：

- 实时输入可视化
- 实时和弦显示
- 简单节拍器
- 选择输入设备后自动记录练习时长
- 本地 Web 面板查看每日、每周、每月记录
- 记录 riff、节奏型、solo 段落、技巧练习、音色设置、速度训练等内容

所有数据都保存在本地。

## 截图

![Guitar Practice Monitor 截图](docs/screenshot.png)

## 下载

在 GitHub Releases 下载最新版构建：

```text
Windows → guitar-practice-monitor-windows.zip
macOS   → guitar-practice-monitor-macos.zip
```

Windows 构建产物是一个可直接运行的文件夹：

```text
GuitarPracticeMonitor/
  guitar-practice-monitor.exe
  data/
    practice_log.json
```

macOS 构建产物包含应用和本地数据目录：

```text
GuitarPracticeMonitor-macos/
  Guitar Practice Monitor.app
  data/
    practice_log.json
```

## 数据

练习记录保存在程序文件夹内：

```text
data/practice_log.json
```
