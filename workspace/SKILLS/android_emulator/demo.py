#!/usr/bin/env python3
"""
Interactive demo showing all capabilities of AndroidController.
"""

from android_controller import AndroidController
import time
import json


def demo_basic_controls(ctrl: AndroidController):
    """Demo: Basic screen interactions"""
    print("\n" + "=" * 50)
    print("📱 Demo 1: Basic Controls")
    print("=" * 50)
    
    # Go home
    ctrl.key_home()
    time.sleep(1)
    
    # Get screen info
    w, h = ctrl.get_screen_size()
    print(f"Screen size: {w}x{h}")
    
    # Take screenshot
    ctrl.screenshot("demo_01_home.png")
    
    # Swipe up to open app drawer
    ctrl.swipe_up(distance=800)
    time.sleep(1)
    ctrl.screenshot("demo_02_app_drawer.png")
    
    # Go back home
    ctrl.key_home()
    time.sleep(0.5)


def demo_text_input(ctrl: AndroidController):
    """Demo: Open browser and type a URL"""
    print("\n" + "=" * 50)
    print("⌨️  Demo 2: Text Input")
    print("=" * 50)
    
    # Open Chrome/Browser
    ctrl.launch_app("com.android.chrome")
    time.sleep(3)
    
    # Try to dismiss any welcome dialogs
    ctrl.tap_element(text="Accept & continue")
    time.sleep(1)
    ctrl.tap_element(text="No thanks")
    time.sleep(1)
    
    # Tap address bar and type
    w, h = ctrl.get_screen_size()
    ctrl.tap(w // 2, 150)  # Address bar is usually near top
    time.sleep(0.5)
    ctrl.type_text("https://example.com")
    ctrl.key_enter()
    time.sleep(3)
    
    ctrl.screenshot("demo_03_browser.png")
    ctrl.key_home()


def demo_ui_inspection(ctrl: AndroidController):
    """Demo: UI element finding"""
    print("\n" + "=" * 50)
    print("🔍 Demo 3: UI Inspection")
    print("=" * 50)
    
    ctrl.key_home()
    time.sleep(1)
    
    # Dump UI
    xml = ctrl.dump_ui()
    print(f"UI dump size: {len(xml)} chars")
    
    # Save UI dump
    with open("demo_ui_dump.xml", "w") as f:
        f.write(xml)
    print("UI dump saved to demo_ui_dump.xml")
    
    # Try to find elements
    for text in ["Settings", "Chrome", "Phone", "Messages", "Camera"]:
        element = ctrl.find_element(text=text)
        if element:
            print(f"  Found '{text}' at center={element['center']}, bounds={element['bounds']}")
        else:
            print(f"  '{text}' not found on current screen")


def demo_macro(ctrl: AndroidController):
    """Demo: Execute a macro (automated sequence)"""
    print("\n" + "=" * 50)
    print("🤖 Demo 4: Macro Execution")
    print("=" * 50)
    
    macro = [
        {"action": "home"},
        {"action": "wait", "seconds": 1},
        {"action": "screenshot", "path": "macro_01_start.png"},
        {"action": "swipe_up", "distance": 600},
        {"action": "wait", "seconds": 0.5},
        {"action": "screenshot", "path": "macro_02_scrolled.png"},
        {"action": "swipe_down", "distance": 600},
        {"action": "wait", "seconds": 0.5},
        {"action": "home"},
        {"action": "screenshot", "path": "macro_03_end.png"},
    ]
    
    # Save macro for reuse
    with open("demo_macro.json", "w") as f:
        json.dump(macro, f, indent=2)
    print("Macro saved to demo_macro.json")
    
    # Execute
    ctrl.execute_macro(macro)


def demo_device_info(ctrl: AndroidController):
    """Demo: Device information"""
    print("\n" + "=" * 50)
    print("ℹ️  Demo 5: Device Info")
    print("=" * 50)
    
    info = ctrl.get_device_info()
    for key, value in info.items():
        print(f"  {key:20s}: {value}")
    
    print(f"\n  Current activity: {ctrl.get_current_activity()}")
    print(f"  Screen on: {ctrl.is_screen_on()}")
    
    # List some packages
    print("\n  Installed Google apps:")
    for pkg in ctrl.list_packages("google")[:10]:
        print(f"    {pkg}")


def main():
    print("🤖 Android Controller - Full Demo")
    print("=" * 50)
    
    ctrl = AndroidController()
    ctrl.connect()
    
    # Run all demos
    demo_device_info(ctrl)
    demo_basic_controls(ctrl)
    demo_ui_inspection(ctrl)
    demo_macro(ctrl)
    
    # Optionally run browser demo (needs Chrome installed)
    # demo_text_input(ctrl)
    
    print("\n" + "=" * 50)
    print("✅ All demos complete!")
    print("Check the generated screenshots: demo_*.png, macro_*.png")
    print("=" * 50)


if __name__ == "__main__":
    main()
