# Guitar Practice Monitor

[中文](README.md)

Guitar Practice Monitor is a lightweight desktop practice companion for guitar players, with Windows and macOS builds.

It makes daily practice less repetitive by combining a small desktop widget with a local practice log:

- live input visualization
- real-time chord display
- simple metronome
- automatic practice timing after selecting an input device
- local web dashboard for daily, weekly, and monthly records
- notes for riffs, rhythm parts, solo sections, technique work, tone settings, and speed practice

All data stays local.

## Screenshot

![Guitar Practice Monitor screenshot](docs/screenshot.png)

## Download

Download the latest build from GitHub Releases:

```text
Windows → guitar-practice-monitor-windows.zip
macOS   → guitar-practice-monitor-macos.zip
```

The Windows build output is a portable folder:

```text
GuitarPracticeMonitor/
  guitar-practice-monitor.exe
  data/
    practice_log.json
```

The macOS build contains the app bundle and local data folder:

```text
GuitarPracticeMonitor-macos/
  Guitar Practice Monitor.app
  data/
    practice_log.json
```

## Usage

- Click `MIC` to choose an input device. After a device is selected, the status changes from `WAITING` to `PRACTICING` and practice timing starts automatically.
- Click `LOG` to open the practice log page, where you can view daily, weekly, and monthly stats and edit practice notes for each day.
- Click the metronome button to turn the metronome on or off. Type a BPM value directly to change the tempo.
- When the floating window is closed, the current practice duration is saved to today's record.

## Data

Practice records are stored in the bundle folder:

```text
data/practice_log.json
```
