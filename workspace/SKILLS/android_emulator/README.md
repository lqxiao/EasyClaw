# Android Emulator Skill (安卓虚拟机控制)

Control an Android emulator/device programmatically — tap, swipe, screenshot, type text, install apps, and more.

## Architecture

```
┌─────────────────────────────────────┐
│          Python Controller          │
│  (android_controller.py)            │
│                                     │
│  tap() swipe() screenshot()         │
│  type_text() keyevent() ...         │
└──────────────┬──────────────────────┘
               │  ADB commands
               ▼
┌─────────────────────────────────────┐
│          ADB Server                 │
│  (Android Debug Bridge)            │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────┐
│  Emulator   │  │ Real Device  │
│  (AVD)      │  │ (USB/WiFi)   │
└─────────────┘  └──────────────┘
```

## Setup

```bash
# 1. Install Android SDK command-line tools
./setup.sh

# 2. Create & start emulator
python android_controller.py setup

# 3. Use the controller
python android_controller.py demo
```

## Quick Start (Python)

```python
from android_controller import AndroidController

ctrl = AndroidController()
ctrl.connect()

# Screenshot
ctrl.screenshot("screen.png")

# Tap at coordinates
ctrl.tap(500, 1000)

# Swipe (scroll down)
ctrl.swipe(500, 1500, 500, 500, duration_ms=300)

# Type text
ctrl.type_text("Hello Android!")

# Press keys
ctrl.key_home()
ctrl.key_back()

# Get screen info
print(ctrl.get_screen_size())

# List installed packages
print(ctrl.list_packages())
```

## Files

- `setup.sh` — Install Android SDK, create emulator
- `android_controller.py` — Main Python controller class
- `demo.py` — Interactive demo
- `requirements.txt` — Python dependencies
