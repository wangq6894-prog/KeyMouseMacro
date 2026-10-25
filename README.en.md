# KeyMouseMacro

[中文](README.md)

A keyboard/mouse simulation tool for Windows: auto-click, key repeat, hold-down and sequence loops. Single file, zero dependencies (Python standard library only). Windows only.

## Run

Install [Python 3](https://www.python.org/downloads/), then double-click `启动工具.bat` or run `python main.py`.

Append `--lang=zh` / `--lang=en` to force the UI language (follows the system language by default).

## Features

- Any keyboard key (click the capture button, then press the key) or left/middle/right mouse button
- Modes: press once, hold down, press N times, repeat forever, sequence loop
- Sequence mode supports per-step intervals (ms), a loop count limit (0 = endless) and ±20% timing jitter
- Global hotkeys (default F9 start / F10 stop, remappable) that work inside other programs
- Raises the system timer resolution while running, so millisecond intervals are honored
- Stop takes effect immediately; held keys are always released on stop or exit
- Settings persist in config.json; keyboard and mouse sequences are remembered separately

## Sequence syntax

Actions are space-separated: `1 2 3 4`, `q e r f1`, `left right left right`.

- Keyboard: letters, digits, F1–F24, arrows (`up/down/left/right`), `space/tab/enter/esc/shift/ctrl/alt`, symbol keys (`-` `=` `[`)
- Mouse: `left` / `right` / `middle` (Chinese `左 右 中` also works)
- The space key itself is written as `space`, since spaces separate actions
- Per-step intervals are colon-separated: `2000:300:300` is the wait in ms after each step; the n-th entry replaces the loop pause; entries cannot outnumber steps

## Notes

- If the target program runs as administrator, this tool must too
- Some games ignore a simulated "hold down"; use "repeat forever" instead
- Automated input may violate the terms of service of some games/apps — use your own judgment

Full manual (Chinese): [使用说明.md](使用说明.md)

## License

MIT
