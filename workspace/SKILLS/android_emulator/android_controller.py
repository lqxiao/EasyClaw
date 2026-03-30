#!/usr/bin/env python3
"""
Android Emulator Controller (安卓虚拟机控制器)

Control an Android emulator or real device via ADB.
Supports: tap, swipe, screenshot, type text, key events, 
          app management, screen recording, UI inspection, and more.

Usage:
    from android_controller import AndroidController
    
    ctrl = AndroidController()
    ctrl.connect()
    ctrl.screenshot("screen.png")
    ctrl.tap(500, 1000)
    ctrl.swipe(500, 1500, 500, 500)
"""

import subprocess
import os
import time
import re
import json
import base64
import tempfile
from typing import Optional, Tuple, List, Dict
from pathlib import Path


class ADBError(Exception):
    """ADB command execution error"""
    pass


class AndroidController:
    """
    Full-featured Android device controller via ADB.
    
    Supports both emulator and real devices.
    """
    
    def __init__(self, device_serial: Optional[str] = None, adb_path: Optional[str] = None):
        """
        Args:
            device_serial: Device serial (e.g., 'emulator-5554'). None = auto-detect.
            adb_path: Path to adb binary. None = find in PATH or ANDROID_HOME.
        """
        self.device_serial = device_serial
        self.adb_path = adb_path or self._find_adb()
        self._connected = False
        self._screen_size = None
    
    # =========================================================
    # Connection & Device Management
    # =========================================================
    
    def _find_adb(self) -> str:
        """Find adb binary"""
        # Check PATH
        result = subprocess.run(["which", "adb"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Check ANDROID_HOME
        android_home = os.environ.get("ANDROID_HOME", os.path.expanduser("~/android-sdk"))
        candidates = [
            os.path.join(android_home, "platform-tools", "adb"),
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            "/usr/local/bin/adb",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        
        raise FileNotFoundError(
            "adb not found! Run setup.sh first or install Android SDK.\n"
            "  brew install android-platform-tools  (macOS)\n"
            "  sudo apt install adb                 (Linux)"
        )
    
    def _run_adb(self, *args, timeout: int = 30, check: bool = True) -> str:
        """Run an ADB command and return stdout"""
        cmd = [self.adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if check and result.returncode != 0:
                raise ADBError(f"ADB command failed: {' '.join(cmd)}\n{result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise ADBError(f"ADB command timed out: {' '.join(cmd)}")
    
    def _shell(self, *args, timeout: int = 30) -> str:
        """Run a shell command on the device"""
        return self._run_adb("shell", *args, timeout=timeout)
    
    def connect(self, wait_timeout: int = 60) -> bool:
        """
        Connect to device/emulator. Waits for device to be ready.
        
        Args:
            wait_timeout: Max seconds to wait for device
        
        Returns:
            True if connected successfully
        """
        print("🔌 Connecting to device...")
        
        # Start ADB server
        self._run_adb("start-server", check=False)
        
        # Wait for device
        try:
            self._run_adb("wait-for-device", timeout=wait_timeout)
        except ADBError:
            raise ADBError(
                f"No device found within {wait_timeout}s.\n"
                "Start an emulator: emulator -avd test_device &\n"
                "Or connect a device via USB."
            )
        
        # Auto-detect serial if not set
        if not self.device_serial:
            devices = self.list_devices()
            if devices:
                self.device_serial = devices[0]["serial"]
                print(f"   Auto-selected device: {self.device_serial}")
        
        # Wait for boot complete
        print("   Waiting for boot...")
        start = time.time()
        while time.time() - start < wait_timeout:
            try:
                boot = self._shell("getprop", "sys.boot_completed")
                if boot.strip() == "1":
                    break
            except ADBError:
                pass
            time.sleep(2)
        
        self._connected = True
        self._screen_size = None  # Reset cache
        
        device_model = self._shell("getprop", "ro.product.model")
        android_ver = self._shell("getprop", "ro.build.version.release")
        print(f"✅ Connected: {device_model} (Android {android_ver})")
        return True
    
    def list_devices(self) -> List[Dict[str, str]]:
        """List all connected devices"""
        output = self._run_adb("devices", "-l")
        devices = []
        for line in output.split("\n")[1:]:
            line = line.strip()
            if line and "device" in line and "List" not in line:
                parts = line.split()
                serial = parts[0]
                info = " ".join(parts[1:])
                devices.append({"serial": serial, "info": info})
        return devices
    
    def disconnect(self):
        """Disconnect from device"""
        self._run_adb("disconnect", check=False)
        self._connected = False
        print("🔌 Disconnected")
    
    # =========================================================
    # Screen Interaction — Tap, Swipe, Long Press, Pinch
    # =========================================================
    
    def tap(self, x: int, y: int):
        """
        Tap at screen coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        self._shell("input", "tap", str(x), str(y))
    
    def double_tap(self, x: int, y: int, interval_ms: int = 100):
        """Double tap at coordinates"""
        self._shell("input", "tap", str(x), str(y))
        time.sleep(interval_ms / 1000)
        self._shell("input", "tap", str(x), str(y))
    
    def long_press(self, x: int, y: int, duration_ms: int = 1000):
        """
        Long press at coordinates.
        
        Args:
            x, y: Coordinates
            duration_ms: Press duration in milliseconds
        """
        self._shell("input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms))
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """
        Swipe from (x1,y1) to (x2,y2).
        
        Args:
            x1, y1: Start coordinates
            x2, y2: End coordinates
            duration_ms: Swipe duration in milliseconds
        """
        self._shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
    
    def swipe_up(self, distance: int = 500, duration_ms: int = 300):
        """Swipe up (scroll down)"""
        w, h = self.get_screen_size()
        cx = w // 2
        cy = h // 2
        self.swipe(cx, cy + distance // 2, cx, cy - distance // 2, duration_ms)
    
    def swipe_down(self, distance: int = 500, duration_ms: int = 300):
        """Swipe down (scroll up)"""
        w, h = self.get_screen_size()
        cx = w // 2
        cy = h // 2
        self.swipe(cx, cy - distance // 2, cx, cy + distance // 2, duration_ms)
    
    def swipe_left(self, distance: int = 500, duration_ms: int = 300):
        """Swipe left"""
        w, h = self.get_screen_size()
        cx = w // 2
        cy = h // 2
        self.swipe(cx + distance // 2, cy, cx - distance // 2, cy, duration_ms)
    
    def swipe_right(self, distance: int = 500, duration_ms: int = 300):
        """Swipe right"""
        w, h = self.get_screen_size()
        cx = w // 2
        cy = h // 2
        self.swipe(cx - distance // 2, cy, cx + distance // 2, cy, duration_ms)
    
    def pinch_in(self, cx: Optional[int] = None, cy: Optional[int] = None, 
                 distance: int = 300, duration_ms: int = 500):
        """Pinch in (zoom out) — requires two-finger gesture via sendevent (simplified)"""
        # Note: True multi-touch requires sendevent. This is a simplified version.
        if cx is None or cy is None:
            w, h = self.get_screen_size()
            cx, cy = w // 2, h // 2
        # Simulate with two sequential swipes (approximate)
        self.swipe(cx - distance, cy, cx - distance // 4, cy, duration_ms)
        self.swipe(cx + distance, cy, cx + distance // 4, cy, duration_ms)
    
    def pinch_out(self, cx: Optional[int] = None, cy: Optional[int] = None,
                  distance: int = 300, duration_ms: int = 500):
        """Pinch out (zoom in) — simplified"""
        if cx is None or cy is None:
            w, h = self.get_screen_size()
            cx, cy = w // 2, h // 2
        self.swipe(cx - distance // 4, cy, cx - distance, cy, duration_ms)
        self.swipe(cx + distance // 4, cy, cx + distance, cy, duration_ms)
    
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 1000):
        """Drag from one point to another (long press + move)"""
        self._shell("input", "draganddrop", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
    
    # =========================================================
    # Text Input
    # =========================================================
    
    def type_text(self, text: str):
        """
        Type text on the device. Handles spaces and special characters.
        
        Args:
            text: Text to type
        """
        # ADB input text doesn't handle spaces well, replace with %s
        escaped = text.replace(" ", "%s")
        escaped = escaped.replace("&", "\\&")
        escaped = escaped.replace("<", "\\<")
        escaped = escaped.replace(">", "\\>")
        escaped = escaped.replace("(", "\\(")
        escaped = escaped.replace(")", "\\)")
        escaped = escaped.replace("|", "\\|")
        escaped = escaped.replace(";", "\\;")
        escaped = escaped.replace("'", "\\'")
        escaped = escaped.replace('"', '\\"')
        self._shell("input", "text", escaped)
    
    def clear_text(self, char_count: int = 100):
        """Clear text field by sending delete keys"""
        # Move to end then delete
        self._shell("input", "keyevent", "KEYCODE_MOVE_END")
        for _ in range(char_count):
            self._shell("input", "keyevent", "KEYCODE_DEL")
    
    # =========================================================
    # Key Events
    # =========================================================
    
    def keyevent(self, keycode: str):
        """
        Send a key event.
        
        Args:
            keycode: Android keycode (e.g., 'KEYCODE_HOME', '3', 'HOME')
        """
        # Allow shorthand
        if not keycode.startswith("KEYCODE_") and not keycode.isdigit():
            keycode = f"KEYCODE_{keycode.upper()}"
        self._shell("input", "keyevent", keycode)
    
    def key_home(self):
        """Press Home button"""
        self.keyevent("3")
    
    def key_back(self):
        """Press Back button"""
        self.keyevent("4")
    
    def key_recent_apps(self):
        """Press Recent Apps button"""
        self.keyevent("187")
    
    def key_power(self):
        """Press Power button"""
        self.keyevent("26")
    
    def key_volume_up(self):
        """Press Volume Up"""
        self.keyevent("24")
    
    def key_volume_down(self):
        """Press Volume Down"""
        self.keyevent("25")
    
    def key_enter(self):
        """Press Enter"""
        self.keyevent("66")
    
    def key_tab(self):
        """Press Tab"""
        self.keyevent("61")
    
    def key_delete(self):
        """Press Delete/Backspace"""
        self.keyevent("67")
    
    def key_menu(self):
        """Press Menu"""
        self.keyevent("82")
    
    def key_search(self):
        """Press Search"""
        self.keyevent("84")
    
    def key_camera(self):
        """Press Camera button"""
        self.keyevent("27")
    
    # =========================================================
    # Screenshot & Screen Recording
    # =========================================================
    
    def screenshot(self, local_path: str = "screenshot.png") -> str:
        """
        Take a screenshot and save to local file.
        
        Args:
            local_path: Local file path to save the screenshot
            
        Returns:
            Path to the saved screenshot
        """
        device_path = "/sdcard/screenshot_tmp.png"
        self._shell("screencap", "-p", device_path)
        self._run_adb("pull", device_path, local_path)
        self._shell("rm", device_path)
        print(f"📸 Screenshot saved: {local_path}")
        return local_path
    
    def screenshot_bytes(self) -> bytes:
        """Take a screenshot and return as bytes (PNG)"""
        # Use exec-out for direct binary output
        cmd = [self.adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        cmd.extend(["exec-out", "screencap", "-p"])
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise ADBError(f"Screenshot failed: {result.stderr.decode()}")
        return result.stdout
    
    def screenshot_base64(self) -> str:
        """Take a screenshot and return as base64 string"""
        img_bytes = self.screenshot_bytes()
        return base64.b64encode(img_bytes).decode("utf-8")
    
    def screen_record(self, local_path: str = "recording.mp4", 
                      duration_sec: int = 10, bitrate: int = 4000000):
        """
        Record screen video.
        
        Args:
            local_path: Local file path for the video
            duration_sec: Recording duration in seconds (max 180)
            bitrate: Video bitrate
        """
        device_path = "/sdcard/recording_tmp.mp4"
        print(f"🎬 Recording for {duration_sec}s...")
        self._shell(
            "screenrecord", 
            "--time-limit", str(min(duration_sec, 180)),
            "--bit-rate", str(bitrate),
            device_path,
            timeout=duration_sec + 10
        )
        self._run_adb("pull", device_path, local_path)
        self._shell("rm", device_path)
        print(f"🎬 Recording saved: {local_path}")
        return local_path
    
    # =========================================================
    # Screen Info
    # =========================================================
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen resolution (width, height)"""
        if self._screen_size:
            return self._screen_size
        
        output = self._shell("wm", "size")
        match = re.search(r"(\d+)x(\d+)", output)
        if match:
            self._screen_size = (int(match.group(1)), int(match.group(2)))
            return self._screen_size
        raise ADBError(f"Could not parse screen size: {output}")
    
    def get_screen_density(self) -> int:
        """Get screen density (DPI)"""
        output = self._shell("wm", "density")
        match = re.search(r"(\d+)", output)
        if match:
            return int(match.group(1))
        raise ADBError(f"Could not parse density: {output}")
    
    def is_screen_on(self) -> bool:
        """Check if screen is on"""
        output = self._shell("dumpsys", "power")
        return "mWakefulness=Awake" in output
    
    def wake_up(self):
        """Wake up the screen"""
        if not self.is_screen_on():
            self.key_power()
            time.sleep(0.5)
    
    def unlock_screen(self):
        """Unlock screen (swipe up, works for no-password lock)"""
        self.wake_up()
        time.sleep(0.3)
        w, h = self.get_screen_size()
        self.swipe(w // 2, h * 3 // 4, w // 2, h // 4, 300)
    
    # =========================================================
    # UI Inspection (UI Automator)
    # =========================================================
    
    def dump_ui(self) -> str:
        """
        Dump current UI hierarchy (XML).
        Useful for finding element coordinates.
        
        Returns:
            XML string of the UI hierarchy
        """
        device_path = "/sdcard/ui_dump.xml"
        self._shell("uiautomator", "dump", device_path)
        output = self._shell("cat", device_path)
        self._shell("rm", device_path)
        return output
    
    def find_element(self, text: Optional[str] = None, 
                     resource_id: Optional[str] = None,
                     class_name: Optional[str] = None,
                     content_desc: Optional[str] = None) -> Optional[Dict]:
        """
        Find a UI element by attributes.
        
        Args:
            text: Element text
            resource_id: Resource ID (e.g., 'com.app:id/button')
            class_name: Class name (e.g., 'android.widget.Button')
            content_desc: Content description
            
        Returns:
            Dict with element info including bounds, or None
        """
        xml = self.dump_ui()
        
        # Build search pattern
        conditions = []
        if text:
            conditions.append(f'text="{text}"')
        if resource_id:
            conditions.append(f'resource-id="{resource_id}"')
        if class_name:
            conditions.append(f'class="{class_name}"')
        if content_desc:
            conditions.append(f'content-desc="{content_desc}"')
        
        if not conditions:
            return None
        
        # Search in XML
        for condition in conditions:
            pattern = f'{condition}.*?bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"'
            match = re.search(pattern, xml)
            if match:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), \
                                   int(match.group(3)), int(match.group(4))
                return {
                    "bounds": (x1, y1, x2, y2),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "width": x2 - x1,
                    "height": y2 - y1,
                }
        return None
    
    def tap_element(self, text: Optional[str] = None, 
                    resource_id: Optional[str] = None, **kwargs):
        """
        Find a UI element and tap its center.
        
        Args:
            text: Element text to find and tap
            resource_id: Resource ID to find and tap
        """
        element = self.find_element(text=text, resource_id=resource_id, **kwargs)
        if element:
            cx, cy = element["center"]
            self.tap(cx, cy)
            return True
        else:
            print(f"⚠️  Element not found: text={text}, resource_id={resource_id}")
            return False
    
    def wait_for_element(self, text: Optional[str] = None,
                         resource_id: Optional[str] = None,
                         timeout: int = 10, interval: float = 0.5, **kwargs) -> Optional[Dict]:
        """
        Wait for a UI element to appear.
        
        Returns:
            Element dict if found, None if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            element = self.find_element(text=text, resource_id=resource_id, **kwargs)
            if element:
                return element
            time.sleep(interval)
        return None
    
    # =========================================================
    # App Management
    # =========================================================
    
    def install_apk(self, apk_path: str):
        """Install an APK file"""
        print(f"📦 Installing {apk_path}...")
        self._run_adb("install", "-r", apk_path, timeout=120)
        print(f"✅ Installed")
    
    def uninstall_app(self, package: str):
        """Uninstall an app by package name"""
        self._run_adb("uninstall", package)
        print(f"🗑️  Uninstalled {package}")
    
    def launch_app(self, package: str, activity: Optional[str] = None):
        """
        Launch an app.
        
        Args:
            package: Package name (e.g., 'com.android.chrome')
            activity: Activity name. If None, launches default activity.
        """
        if activity:
            self._shell("am", "start", "-n", f"{package}/{activity}")
        else:
            self._shell("monkey", "-p", package, "-c", 
                        "android.intent.category.LAUNCHER", "1")
        print(f"🚀 Launched {package}")
    
    def stop_app(self, package: str):
        """Force stop an app"""
        self._shell("am", "force-stop", package)
    
    def clear_app_data(self, package: str):
        """Clear app data"""
        self._shell("pm", "clear", package)
    
    def list_packages(self, filter_str: Optional[str] = None) -> List[str]:
        """List installed packages"""
        output = self._shell("pm", "list", "packages")
        packages = [line.replace("package:", "") for line in output.split("\n") if line]
        if filter_str:
            packages = [p for p in packages if filter_str.lower() in p.lower()]
        return sorted(packages)
    
    def get_current_activity(self) -> str:
        """Get the currently focused activity"""
        output = self._shell("dumpsys", "activity", "activities")
        match = re.search(r"mResumedActivity.*?{.*?\s+([\w.]+/[\w.]+)", output)
        if match:
            return match.group(1)
        return "unknown"
    
    def get_current_package(self) -> str:
        """Get the currently focused package"""
        activity = self.get_current_activity()
        return activity.split("/")[0] if "/" in activity else activity
    
    # =========================================================
    # File Management
    # =========================================================
    
    def push_file(self, local_path: str, device_path: str):
        """Push a file to the device"""
        self._run_adb("push", local_path, device_path)
    
    def pull_file(self, device_path: str, local_path: str):
        """Pull a file from the device"""
        self._run_adb("pull", device_path, local_path)
    
    def list_files(self, device_path: str = "/sdcard/") -> List[str]:
        """List files on device"""
        output = self._shell("ls", "-la", device_path)
        return output.split("\n")
    
    # =========================================================
    # System Info
    # =========================================================
    
    def get_device_info(self) -> Dict[str, str]:
        """Get comprehensive device info"""
        return {
            "model": self._shell("getprop", "ro.product.model"),
            "brand": self._shell("getprop", "ro.product.brand"),
            "android_version": self._shell("getprop", "ro.build.version.release"),
            "sdk_version": self._shell("getprop", "ro.build.version.sdk"),
            "screen_size": f"{self.get_screen_size()[0]}x{self.get_screen_size()[1]}",
            "density": str(self.get_screen_density()),
            "serial": self.device_serial or "unknown",
            "battery": self._get_battery_level(),
        }
    
    def _get_battery_level(self) -> str:
        output = self._shell("dumpsys", "battery")
        match = re.search(r"level:\s*(\d+)", output)
        return f"{match.group(1)}%" if match else "unknown"
    
    def get_ip_address(self) -> str:
        """Get device IP address"""
        output = self._shell("ip", "addr", "show", "wlan0")
        match = re.search(r"inet\s+([\d.]+)", output)
        return match.group(1) if match else "unknown"
    
    # =========================================================
    # Advanced: Open URLs, Settings, etc.
    # =========================================================
    
    def open_url(self, url: str):
        """Open a URL in the default browser"""
        self._shell("am", "start", "-a", "android.intent.action.VIEW", "-d", url)
    
    def open_settings(self):
        """Open device settings"""
        self._shell("am", "start", "-a", "android.settings.SETTINGS")
    
    def set_brightness(self, level: int):
        """Set screen brightness (0-255)"""
        level = max(0, min(255, level))
        self._shell("settings", "put", "system", "screen_brightness", str(level))
    
    def toggle_wifi(self, enable: bool):
        """Enable/disable WiFi"""
        action = "enable" if enable else "disable"
        self._shell("svc", "wifi", action)
    
    def toggle_airplane_mode(self, enable: bool):
        """Toggle airplane mode"""
        value = "1" if enable else "0"
        self._shell("settings", "put", "global", "airplane_mode_on", value)
        self._shell("am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE",
                    "--ez", "state", str(enable).lower())
    
    def take_bug_report(self, local_path: str = "bugreport.zip"):
        """Generate a bug report"""
        self._run_adb("bugreport", local_path, timeout=300)
    
    # =========================================================
    # Convenience: Complex Gestures
    # =========================================================
    
    def scroll_to_text(self, text: str, max_scrolls: int = 10, direction: str = "down") -> bool:
        """
        Scroll until text is found on screen.
        
        Args:
            text: Text to find
            max_scrolls: Maximum number of scroll attempts
            direction: 'down' or 'up'
            
        Returns:
            True if text found
        """
        for i in range(max_scrolls):
            element = self.find_element(text=text)
            if element:
                print(f"✅ Found '{text}' after {i} scrolls")
                return True
            
            if direction == "down":
                self.swipe_up()
            else:
                self.swipe_down()
            time.sleep(0.5)
        
        print(f"⚠️  Text '{text}' not found after {max_scrolls} scrolls")
        return False
    
    def tap_and_type(self, x: int, y: int, text: str, clear_first: bool = True):
        """Tap a text field and type text"""
        self.tap(x, y)
        time.sleep(0.3)
        if clear_first:
            self.clear_text()
            time.sleep(0.1)
        self.type_text(text)
    
    # =========================================================
    # Emulator-Specific Controls
    # =========================================================
    
    def set_location(self, latitude: float, longitude: float):
        """Set GPS location (emulator only)"""
        self._shell("settings", "put", "secure", "location_providers_allowed", "+gps")
        # Use emulator console or adb emu command
        self._run_adb("emu", "geo", "fix", str(longitude), str(latitude), check=False)
    
    def rotate_screen(self, orientation: str = "landscape"):
        """
        Rotate screen.
        
        Args:
            orientation: 'portrait' (0), 'landscape' (1), 
                        'reverse_portrait' (2), 'reverse_landscape' (3)
        """
        orientations = {
            "portrait": "0", "landscape": "1",
            "reverse_portrait": "2", "reverse_landscape": "3"
        }
        value = orientations.get(orientation, orientation)
        self._shell("settings", "put", "system", "accelerometer_rotation", "0")
        self._shell("settings", "put", "system", "user_rotation", value)
    
    # =========================================================
    # Batch / Macro Operations
    # =========================================================
    
    def execute_macro(self, steps: List[Dict]):
        """
        Execute a sequence of actions (macro).
        
        Args:
            steps: List of action dicts, e.g.:
                [
                    {"action": "tap", "x": 500, "y": 1000},
                    {"action": "wait", "seconds": 1},
                    {"action": "type", "text": "hello"},
                    {"action": "swipe", "x1": 500, "y1": 1500, "x2": 500, "y2": 500},
                    {"action": "screenshot", "path": "step1.png"},
                    {"action": "key", "code": "BACK"},
                ]
        """
        for i, step in enumerate(steps):
            action = step.get("action", "")
            print(f"  Step {i+1}/{len(steps)}: {action} {step}")
            
            if action == "tap":
                self.tap(step["x"], step["y"])
            elif action == "double_tap":
                self.double_tap(step["x"], step["y"])
            elif action == "long_press":
                self.long_press(step["x"], step["y"], step.get("duration_ms", 1000))
            elif action == "swipe":
                self.swipe(step["x1"], step["y1"], step["x2"], step["y2"],
                          step.get("duration_ms", 300))
            elif action == "swipe_up":
                self.swipe_up(step.get("distance", 500))
            elif action == "swipe_down":
                self.swipe_down(step.get("distance", 500))
            elif action == "type":
                self.type_text(step["text"])
            elif action == "key":
                self.keyevent(step["code"])
            elif action == "screenshot":
                self.screenshot(step.get("path", f"macro_step_{i}.png"))
            elif action == "wait":
                time.sleep(step.get("seconds", 1))
            elif action == "launch":
                self.launch_app(step["package"])
            elif action == "home":
                self.key_home()
            elif action == "back":
                self.key_back()
            elif action == "tap_element":
                self.tap_element(text=step.get("text"), resource_id=step.get("resource_id"))
            else:
                print(f"  ⚠️  Unknown action: {action}")
            
            # Small delay between actions
            time.sleep(step.get("delay", 0.2))
        
        print(f"✅ Macro complete ({len(steps)} steps)")
    
    # =========================================================
    # String representation
    # =========================================================
    
    def __repr__(self):
        status = "connected" if self._connected else "disconnected"
        return f"AndroidController(serial={self.device_serial}, status={status})"


# =============================================================
# CLI Interface
# =============================================================

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("""
Android Controller CLI
Usage:
    python android_controller.py <command> [args]

Commands:
    setup       - Run setup.sh to install Android SDK & emulator
    start       - Start the emulator
    connect     - Test connection to device
    demo        - Run interactive demo
    info        - Show device info
    screenshot  - Take a screenshot
    tap X Y     - Tap at coordinates
    swipe X1 Y1 X2 Y2 - Swipe gesture
    type TEXT   - Type text
    key CODE    - Send key event
    shell CMD   - Run shell command on device
    ui          - Dump UI hierarchy
    packages    - List installed packages
    macro FILE  - Run a macro from JSON file
        """)
        return
    
    command = sys.argv[1]
    
    if command == "setup":
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.system(f"bash {script_dir}/setup.sh")
        return
    
    if command == "start":
        avd_name = sys.argv[2] if len(sys.argv) > 2 else "test_device"
        android_home = os.environ.get("ANDROID_HOME", os.path.expanduser("~/android-sdk"))
        emulator_path = os.path.join(android_home, "emulator", "emulator")
        print(f"Starting emulator: {avd_name}")
        os.system(f"{emulator_path} -avd {avd_name} -no-audio &")
        print("Emulator starting in background...")
        return
    
    ctrl = AndroidController()
    
    if command == "connect":
        ctrl.connect()
        print(ctrl)
    
    elif command == "info":
        ctrl.connect()
        info = ctrl.get_device_info()
        for k, v in info.items():
            print(f"  {k}: {v}")
    
    elif command == "demo":
        ctrl.connect()
        print("\n🎮 Interactive Demo")
        print("=" * 40)
        
        info = ctrl.get_device_info()
        print(f"\nDevice: {info['model']} (Android {info['android_version']})")
        print(f"Screen: {info['screen_size']} @ {info['density']}dpi")
        
        # Take screenshot
        ctrl.screenshot("demo_screenshot.png")
        
        # Show current activity
        print(f"\nCurrent activity: {ctrl.get_current_activity()}")
        
        # Demo macro
        print("\n📋 Running demo macro...")
        ctrl.execute_macro([
            {"action": "home"},
            {"action": "wait", "seconds": 1},
            {"action": "screenshot", "path": "demo_home.png"},
            {"action": "swipe_up", "distance": 800},
            {"action": "wait", "seconds": 0.5},
            {"action": "screenshot", "path": "demo_scrolled.png"},
            {"action": "home"},
        ])
        print("\n✅ Demo complete! Check demo_*.png files.")
    
    elif command == "screenshot":
        ctrl.connect()
        path = sys.argv[2] if len(sys.argv) > 2 else "screenshot.png"
        ctrl.screenshot(path)
    
    elif command == "tap":
        ctrl.connect()
        x, y = int(sys.argv[2]), int(sys.argv[3])
        ctrl.tap(x, y)
        print(f"Tapped ({x}, {y})")
    
    elif command == "swipe":
        ctrl.connect()
        x1, y1, x2, y2 = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        ctrl.swipe(x1, y1, x2, y2)
        print(f"Swiped ({x1},{y1}) -> ({x2},{y2})")
    
    elif command == "type":
        ctrl.connect()
        text = " ".join(sys.argv[2:])
        ctrl.type_text(text)
        print(f"Typed: {text}")
    
    elif command == "key":
        ctrl.connect()
        ctrl.keyevent(sys.argv[2])
        print(f"Key event: {sys.argv[2]}")
    
    elif command == "shell":
        ctrl.connect()
        result = ctrl._shell(*sys.argv[2:])
        print(result)
    
    elif command == "ui":
        ctrl.connect()
        xml = ctrl.dump_ui()
        print(xml[:3000])
        print("..." if len(xml) > 3000 else "")
    
    elif command == "packages":
        ctrl.connect()
        filter_str = sys.argv[2] if len(sys.argv) > 2 else None
        for pkg in ctrl.list_packages(filter_str):
            print(f"  {pkg}")
    
    elif command == "macro":
        ctrl.connect()
        macro_file = sys.argv[2]
        with open(macro_file) as f:
            steps = json.load(f)
        ctrl.execute_macro(steps)
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
