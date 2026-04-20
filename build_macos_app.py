#!/usr/bin/env python3
"""
Package EasyClaw as a macOS application bundle (.app).

Usage:
    python build_macos_app.py            # Build the .app
    python build_macos_app.py --dmg      # Build .app + DMG disk image

Output:
    dist/EasyClaw.app
    dist/EasyClaw.dmg  (with --dmg)
"""

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
import sys

# ── Configuration ────────────────────────────────────────────────────────────

APP_NAME = "EasyClaw"
BUNDLE_ID = "com.easyclaw.app"
VERSION = "1.0.0"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
APP_BUNDLE = os.path.join(DIST_DIR, f"{APP_NAME}.app")

# Python source files to bundle
SOURCE_FILES = [
    "main.py",
    "agent.py",
    "apis.py",
    "memory.py",
    "skills_browser.py",
    "task.py",
    "tools.py",
    "utils.py",
    "requirements.txt",
]

# Directories to bundle
SOURCE_DIRS = [
    "config",
    "workspace",
]

# Patterns to exclude when copying directories
EXCLUDE_PATTERNS = ("__pycache__", "*.pyc", ".DS_Store", ".git")

# ── Native Wrapper ──────────────────────────────────────────────────────────
# A tiny C binary that execs the bash launcher. Without this, macOS shows
# "Script Editor" in the Dock because the process is /bin/bash.

NATIVE_WRAPPER_C = r'''
/*
 * Cocoa + WebKit wrapper for EasyClaw.
 *   - Opens a native window with WKWebView showing the Gradio UI
 *   - Forks the bash launcher to start the Gradio server
 *   - Polls until the server is ready, then loads the page
 *   - Cmd-Q / window close cleanly shuts down the server
 */
#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#include <signal.h>
#include <sys/wait.h>
#include <libgen.h>
#include <mach-o/dyld.h>

static pid_t child_pid = 0;

static void forward_signal(int sig) {
    if (child_pid > 0) kill(child_pid, sig);
}

/* ── Menu bar ─────────────────────────────────────────────────────────── */

static void setupMenuBar(void) {
    NSMenu *menuBar = [[NSMenu alloc] init];

    /* App menu (EasyClaw) */
    NSMenuItem *appMenuItem = [[NSMenuItem alloc] init];
    NSMenu *appMenu = [[NSMenu alloc] initWithTitle:@"EasyClaw"];
    [appMenu addItemWithTitle:@"About EasyClaw"
                       action:@selector(orderFrontStandardAboutPanel:)
                keyEquivalent:@""];
    [appMenu addItem:[NSMenuItem separatorItem]];
    [appMenu addItemWithTitle:@"Quit EasyClaw"
                       action:@selector(terminate:)
                keyEquivalent:@"q"];
    [appMenuItem setSubmenu:appMenu];
    [menuBar addItem:appMenuItem];

    /* Edit menu (enables Cmd-C / Cmd-V / Cmd-A in the webview) */
    NSMenuItem *editMenuItem = [[NSMenuItem alloc] init];
    NSMenu *editMenu = [[NSMenu alloc] initWithTitle:@"Edit"];
    [editMenu addItemWithTitle:@"Undo"   action:@selector(undo:)       keyEquivalent:@"z"];
    [editMenu addItemWithTitle:@"Redo"   action:@selector(redo:)       keyEquivalent:@"Z"];
    [editMenu addItem:[NSMenuItem separatorItem]];
    [editMenu addItemWithTitle:@"Cut"    action:@selector(cut:)        keyEquivalent:@"x"];
    [editMenu addItemWithTitle:@"Copy"   action:@selector(copy:)       keyEquivalent:@"c"];
    [editMenu addItemWithTitle:@"Paste"  action:@selector(paste:)      keyEquivalent:@"v"];
    [editMenu addItemWithTitle:@"Select All" action:@selector(selectAll:) keyEquivalent:@"a"];
    [editMenuItem setSubmenu:editMenu];
    [menuBar addItem:editMenuItem];

    /* View menu */
    NSMenuItem *viewMenuItem = [[NSMenuItem alloc] init];
    NSMenu *viewMenu = [[NSMenu alloc] initWithTitle:@"View"];

    NSMenuItem *sidebarItem = [[NSMenuItem alloc]
        initWithTitle:@"Toggle Sidebar"
        action:@selector(toggleSidebar:) keyEquivalent:@"s"];
    [sidebarItem setKeyEquivalentModifierMask:
        NSEventModifierFlagControl | NSEventModifierFlagCommand];
    [viewMenu addItem:sidebarItem];

    NSMenuItem *fullScreenItem = [[NSMenuItem alloc]
        initWithTitle:@"Enter Full Screen"
        action:@selector(toggleFullScreen:) keyEquivalent:@"f"];
    [fullScreenItem setKeyEquivalentModifierMask:
        NSEventModifierFlagControl | NSEventModifierFlagCommand];
    [viewMenu addItem:fullScreenItem];

    [viewMenu addItemWithTitle:@"Reload"
                        action:@selector(doReload:)
                 keyEquivalent:@"r"];
    [viewMenu addItem:[NSMenuItem separatorItem]];
    [viewMenu addItemWithTitle:@"Make Text Bigger"
                        action:@selector(zoomIn:)
                 keyEquivalent:@"+"];
    [viewMenu addItemWithTitle:@"Make Text Normal Size"
                        action:@selector(zoomReset:)
                 keyEquivalent:@"0"];
    [viewMenu addItemWithTitle:@"Make Text Smaller"
                        action:@selector(zoomOut:)
                 keyEquivalent:@"-"];
    [viewMenuItem setSubmenu:viewMenu];
    [menuBar addItem:viewMenuItem];

    /* Window menu (standard macOS minimize / zoom / bring all to front) */
    NSMenuItem *windowMenuItem = [[NSMenuItem alloc] init];
    NSMenu *windowMenu = [[NSMenu alloc] initWithTitle:@"Window"];
    [windowMenu addItemWithTitle:@"Minimize"
                          action:@selector(performMiniaturize:)
                   keyEquivalent:@"m"];
    [windowMenu addItemWithTitle:@"Zoom"
                          action:@selector(performZoom:)
                   keyEquivalent:@""];
    [windowMenu addItem:[NSMenuItem separatorItem]];
    [windowMenu addItemWithTitle:@"Bring All to Front"
                          action:@selector(arrangeInFront:)
                   keyEquivalent:@""];
    [windowMenuItem setSubmenu:windowMenu];
    [menuBar addItem:windowMenuItem];
    [NSApp setWindowsMenu:windowMenu];

    [NSApp setMainMenu:menuBar];
}

/* ── App Delegate ─────────────────────────────────────────────────────── */

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property (strong) NSWindow  *window;
@property (strong) WKWebView *webView;
@property (strong) NSTimer   *pollTimer;
@property (assign) CGFloat    zoomLevel;
- (void)doReload:(id)sender;
- (void)zoomIn:(id)sender;
- (void)zoomOut:(id)sender;
- (void)zoomReset:(id)sender;
- (void)toggleSidebar:(id)sender;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)note {
    setupMenuBar();

    /* ── Create window ────────────────────────────────────────────── */
    NSRect screen = [[NSScreen mainScreen] visibleFrame];
    CGFloat w = MIN(1280, screen.size.width  * 0.85);
    CGFloat h = MIN(900,  screen.size.height * 0.85);
    NSRect frame = NSMakeRect(0, 0, w, h);

    self.window = [[NSWindow alloc]
        initWithContentRect:frame
        styleMask:(NSWindowStyleMaskTitled      |
                   NSWindowStyleMaskClosable     |
                   NSWindowStyleMaskMiniaturizable |
                   NSWindowStyleMaskResizable)
        backing:NSBackingStoreBuffered
        defer:NO];
    [self.window setTitle:@"EasyClaw"];
    [self.window center];
    [self.window setMinSize:NSMakeSize(640, 480)];
    [self.window setReleasedWhenClosed:NO];

    /* ── WebView ──────────────────────────────────────────────────── */
    WKWebViewConfiguration *cfg = [[WKWebViewConfiguration alloc] init];
    self.webView = [[WKWebView alloc] initWithFrame:self.window.contentView.bounds
                                      configuration:cfg];
    [self.webView setAutoresizingMask:(NSViewWidthSizable | NSViewHeightSizable)];
    self.zoomLevel = 1.0;
    [self.window.contentView addSubview:self.webView];

    /* Show a loading page while the server starts */
    NSString *loadingHTML = @"<html><body style='display:flex;align-items:center;"
        "justify-content:center;height:100vh;margin:0;font-family:-apple-system,"
        "system-ui;background:#f7f7f8;color:#555;'>"
        "<div style='text-align:center'>"
        "<h2 style='font-weight:500'>Starting EasyClaw...</h2>"
        "<p style='color:#999'>Launching Gradio server</p>"
        "</div></body></html>";
    [self.webView loadHTMLString:loadingHTML baseURL:nil];

    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];

    /* ── Fork the bash launcher ───────────────────────────────────── */
    char exe[4096];
    uint32_t size = sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0) {
        NSLog(@"EasyClaw: cannot resolve executable path");
        [NSApp terminate:nil];
        return;
    }
    char *dir = dirname(exe);
    char script[4096];
    snprintf(script, sizeof(script), "%s/launcher.sh", dir);

    child_pid = fork();
    if (child_pid == 0) {
        execl("/bin/bash", "bash", script, (char *)NULL);
        _exit(1);
    }
    if (child_pid < 0) {
        NSLog(@"EasyClaw: fork failed");
        [NSApp terminate:nil];
        return;
    }

    signal(SIGTERM, forward_signal);
    signal(SIGINT,  forward_signal);

    /* Watch child — quit the app if the server dies */
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        int status;
        waitpid(child_pid, &status, 0);
        dispatch_async(dispatch_get_main_queue(), ^{
            [NSApp terminate:nil];
        });
    });

    /* ── Poll until Gradio is ready, then load the page ───────────── */
    self.pollTimer = [NSTimer scheduledTimerWithTimeInterval:1.0
        repeats:YES
        block:^(NSTimer *timer) {
            NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:7860"];
            NSMutableURLRequest *req = [NSMutableURLRequest requestWithURL:url];
            [req setTimeoutInterval:1.0];
            [[[NSURLSession sharedSession] dataTaskWithRequest:req
                completionHandler:^(NSData *data, NSURLResponse *resp, NSError *err) {
                    if (!err) {
                        dispatch_async(dispatch_get_main_queue(), ^{
                            [timer invalidate];
                            [self.webView loadRequest:[NSURLRequest requestWithURL:url]];
                        });
                    }
                }] resume];
        }];
}

/* ── View menu actions ────────────────────────────────────────────── */

- (void)doReload:(id)sender {
    [self.webView reload];
}

- (void)zoomIn:(id)sender {
    self.zoomLevel = MIN(self.zoomLevel + 0.1, 3.0);
    [self.webView setPageZoom:self.zoomLevel];
}

- (void)zoomOut:(id)sender {
    self.zoomLevel = MAX(self.zoomLevel - 0.1, 0.5);
    [self.webView setPageZoom:self.zoomLevel];
}

- (void)zoomReset:(id)sender {
    self.zoomLevel = 1.0;
    [self.webView setPageZoom:1.0];
}

- (void)toggleSidebar:(id)sender {
    /* Click the Gradio sidebar toggle button via JavaScript */
    [self.webView evaluateJavaScript:
        @"(function(){ var b = document.querySelector('button[aria-label*=\"sidebar\" i], "
         ".sidebar-toggle, button.svelte-1ciwbxo'); if(b) b.click(); })()"
        completionHandler:nil];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return NO;
}

/* Re-show window when Dock icon is clicked */
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    if (!flag) {
        [self.window makeKeyAndOrderFront:nil];
    }
    return YES;
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (child_pid > 0) {
        kill(child_pid, SIGTERM);
        int status;
        int tries = 0;
        while (tries++ < 10) {
            pid_t r = waitpid(child_pid, &status, WNOHANG);
            if (r != 0) break;
            usleep(200000);
        }
        if (tries >= 10) kill(child_pid, SIGKILL);
    }
    return NSTerminateNow;
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        [app setDelegate:delegate];
        [app run];
    }
    return 0;
}
'''

# ── Launcher Script ─────────────────────────────────────────────────────────
# This bash script lives at Contents/MacOS/launcher.sh and is exec'd by the
# native wrapper above. It manages a Python venv, installs deps, and launches
# the Gradio server.

LAUNCHER_SCRIPT = r'''#!/bin/bash
set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_SRC="$APP_DIR/Resources/app"

SUPPORT_DIR="$HOME/Library/Application Support/EasyClaw"
VENV_DIR="$SUPPORT_DIR/venv"
LOG_DIR="$HOME/Library/Logs/EasyClaw"
WORK_DIR="$SUPPORT_DIR/data"
PID_FILE="$SUPPORT_DIR/.server.pid"
REQ_HASH_FILE="$SUPPORT_DIR/.requirements_hash"

MIN_PYTHON_MINOR=10   # Minimum Python 3.x version required

mkdir -p "$LOG_DIR" "$WORK_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_DIR/launcher.log"; }

log "────────────────────────────────────────"
log "EasyClaw starting..."

# ── Already running? Open browser and stay alive as Dock presence ────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log "Already running (PID $OLD_PID)."
        # Keep this process alive so the Dock icon doesn't flash-quit.
        # When the server stops, this also exits.
        while kill -0 "$OLD_PID" 2>/dev/null; do sleep 2; done
        rm -f "$PID_FILE"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

# ── Find Python 3.10+ ──────────────────────────────────────────────────────
# macOS .app bundles don't inherit the user's shell PATH, so we search common
# install locations explicitly: Homebrew, mise, pyenv, python.org framework,
# and the system PATH as a fallback.

find_python() {
    # Candidate directories (order = preference)
    local search_dirs=(
        "$HOME/.local/share/mise/installs/python"/*/bin
        "$HOME/.mise/installs/python"/*/bin
        "$HOME/.pyenv/versions"/*/bin
        /opt/homebrew/bin
        /usr/local/bin
        /Library/Frameworks/Python.framework/Versions/*/bin
    )

    # Also add directories from the user's default shell PATH
    local user_path
    user_path=$(/bin/zsh -lic 'echo $PATH' 2>/dev/null | tail -1 || true)
    IFS=':' read -ra extra_dirs <<< "$user_path"
    search_dirs+=("${extra_dirs[@]}")

    local best_python=""
    local best_minor=0

    for dir in "${search_dirs[@]}"; do
        for candidate in "$dir"/python3.* "$dir"/python3; do
            [ -x "$candidate" ] || continue
            local ver
            ver=$("$candidate" --version 2>&1 | grep -oE '3\.[0-9]+' | head -1) || continue
            local minor=${ver#3.}
            if [ "$minor" -ge "$MIN_PYTHON_MINOR" ] && [ "$minor" -gt "$best_minor" ]; then
                best_minor=$minor
                best_python="$candidate"
            fi
        done
    done

    echo "$best_python"
}

PYTHON_BIN=$(find_python)

if [ -z "$PYTHON_BIN" ]; then
    osascript -e 'display alert "Python 3.10+ Required" message "EasyClaw requires Python 3.10 or later.\n\nInstall from python.org or via Homebrew:\n  brew install python@3.12" as critical' 2>/dev/null
    log "ERROR: No Python 3.${MIN_PYTHON_MINOR}+ found."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1)
log "Using $PYTHON_VERSION at $PYTHON_BIN"

# ── First-run: copy config & workspace templates to user data dir ────────────
if [ ! -d "$WORK_DIR/config" ]; then
    log "First run — copying config template."
    cp -R "$APP_SRC/config" "$WORK_DIR/config"
fi

if [ ! -d "$WORK_DIR/workspace" ]; then
    log "First run — copying workspace template."
    cp -R "$APP_SRC/workspace" "$WORK_DIR/workspace"
fi

# ── Create env.sh for user environment overrides ────────────────────────────
ENV_FILE="$WORK_DIR/env.sh"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVEOF'
# EasyClaw Environment Configuration
# This file is sourced before launching the app.
# Uncomment and modify as needed:

# LLM provider: bedrock | anthropic | openai
# export LLM_PROVIDER=bedrock

# AWS credentials (for Bedrock)
# export AWS_PROFILE=default

# API keys (for Anthropic / OpenAI)
# export ANTHROPIC_API_KEY=sk-...
# export OPENAI_API_KEY=sk-...
ENVEOF
    log "Created env.sh template at $ENV_FILE"
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

# ── Setup / update Python virtual environment ───────────────────────────────
CURRENT_HASH=$(shasum -a 256 "$APP_SRC/requirements.txt" | cut -d' ' -f1)
STORED_HASH=""
[ -f "$REQ_HASH_FILE" ] && STORED_HASH=$(cat "$REQ_HASH_FILE")

if [ ! -d "$VENV_DIR" ] || [ "$CURRENT_HASH" != "$STORED_HASH" ]; then
    FIRST_SETUP=false

    if [ ! -d "$VENV_DIR" ]; then
        FIRST_SETUP=true
        log "Creating virtual environment with $PYTHON_BIN..."
        osascript -e 'display notification "Setting up Python environment… This may take a few minutes." with title "EasyClaw" subtitle "First-time setup"' 2>/dev/null || true
        "$PYTHON_BIN" -m venv "$VENV_DIR" >> "$LOG_DIR/setup.log" 2>&1
    fi

    log "Installing/updating dependencies..."
    "$VENV_DIR/bin/python" -m pip install --upgrade pip >> "$LOG_DIR/setup.log" 2>&1
    "$VENV_DIR/bin/python" -m pip install -r "$APP_SRC/requirements.txt" >> "$LOG_DIR/setup.log" 2>&1
    echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
    log "Python environment ready."

    if [ "$FIRST_SETUP" = true ]; then
        osascript -e 'display notification "Setup complete! Launching…" with title "EasyClaw"' 2>/dev/null || true
    fi
fi

# ── Inherit user's PATH (for tools like ada, aws, etc.) ─────────────────────
# macOS .app bundles start with a minimal PATH. Load the user's login shell
# PATH so external CLIs are available at runtime.
USER_SHELL=$(dscl . -read /Users/"$USER" UserShell 2>/dev/null | awk '{print $2}')
USER_SHELL="${USER_SHELL:-/bin/zsh}"
USER_PATH=$("$USER_SHELL" -lic 'echo $PATH' 2>/dev/null | tail -1 || true)
if [ -n "$USER_PATH" ]; then
    export PATH="$USER_PATH"
    log "Inherited PATH from $USER_SHELL"
fi

# ── Launch Gradio server ────────────────────────────────────────────────────
export PYTHONPATH="$APP_SRC"
cd "$WORK_DIR"

log "PATH=$(echo $PATH | tr ':' '\n' | grep -c /) entries, ada=$(which ada 2>/dev/null || echo NOT_FOUND)"

"$VENV_DIR/bin/python" -u "$APP_SRC/main.py" >> "$LOG_DIR/app.log" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"
log "Gradio server started (PID $SERVER_PID)."

# ── Wait for server; clean up on exit ───────────────────────────────────────
cleanup() {
    log "Shutting down (PID $SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    log "Stopped."
}
trap cleanup EXIT INT TERM HUP

wait "$SERVER_PID" 2>/dev/null || true
'''


# ── Build Functions ──────────────────────────────────────────────────────────

def build_info_plist(icon_name=None):
    """Generate the Info.plist dictionary."""
    plist = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "CFBundleExecutable": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleSignature": "????",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
    }
    if icon_name:
        plist["CFBundleIconFile"] = icon_name
    return plist


def build_app(icon_path=None):
    """Build the macOS .app bundle."""
    # Clean previous build
    if os.path.exists(APP_BUNDLE):
        shutil.rmtree(APP_BUNDLE)

    macos_dir = os.path.join(APP_BUNDLE, "Contents", "MacOS")
    resources_dir = os.path.join(APP_BUNDLE, "Contents", "Resources")
    app_src_dir = os.path.join(resources_dir, "app")

    os.makedirs(macos_dir)
    os.makedirs(app_src_dir)

    # Info.plist
    icon_name = None
    if icon_path and os.path.exists(icon_path):
        icon_name = os.path.basename(icon_path)
        shutil.copy2(icon_path, os.path.join(resources_dir, icon_name))
        print(f"  Icon:    {icon_name}")

    plist_path = os.path.join(APP_BUNDLE, "Contents", "Info.plist")
    with open(plist_path, "wb") as f:
        plistlib.dump(build_info_plist(icon_name), f)

    # Compile native Cocoa wrapper (the actual CFBundleExecutable)
    wrapper_m_path = os.path.join(macos_dir, "wrapper.m")
    wrapper_bin_path = os.path.join(macos_dir, APP_NAME)
    with open(wrapper_m_path, "w") as f:
        f.write(NATIVE_WRAPPER_C)
    result = subprocess.run(
        ["cc", "-O2", "-arch", "arm64", "-arch", "x86_64", "-framework", "Cocoa", "-framework", "WebKit", "-o", wrapper_bin_path, wrapper_m_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Error compiling native wrapper: {result.stderr}")
        sys.exit(1)
    os.remove(wrapper_m_path)

    # Bash launcher script (exec'd by the native wrapper)
    launcher_path = os.path.join(macos_dir, "launcher.sh")
    with open(launcher_path, "w") as f:
        f.write(LAUNCHER_SCRIPT)
    st = os.stat(launcher_path)
    os.chmod(launcher_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Copy Python source files
    copied = 0
    for filename in SOURCE_FILES:
        src = os.path.join(PROJECT_ROOT, filename)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(app_src_dir, filename))
            copied += 1
        else:
            print(f"  Warning: {filename} not found, skipping.")

    # Copy directories
    for dirname in SOURCE_DIRS:
        src = os.path.join(PROJECT_ROOT, dirname)
        if os.path.exists(src):
            shutil.copytree(
                src,
                os.path.join(app_src_dir, dirname),
                ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS),
            )
        else:
            print(f"  Warning: {dirname}/ not found, skipping.")

    # Calculate bundle size
    total_size = 0
    for dirpath, _, filenames in os.walk(APP_BUNDLE):
        for fn in filenames:
            total_size += os.path.getsize(os.path.join(dirpath, fn))
    size_mb = total_size / (1024 * 1024)

    print(f"\n  Built:   {APP_BUNDLE}")
    print(f"  Files:   {copied} source files + {len(SOURCE_DIRS)} directories")
    print(f"  Size:    {size_mb:.1f} MB")


def build_dmg():
    """Create a DMG disk image for distribution."""
    dmg_path = os.path.join(DIST_DIR, f"{APP_NAME}.dmg")
    if os.path.exists(dmg_path):
        os.remove(dmg_path)

    print(f"\n  Creating DMG...")
    result = subprocess.run(
        [
            "hdiutil", "create",
            "-volname", APP_NAME,
            "-srcfolder", APP_BUNDLE,
            "-ov",
            "-format", "UDZO",
            dmg_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Error creating DMG: {result.stderr}")
        sys.exit(1)

    dmg_size = os.path.getsize(dmg_path) / (1024 * 1024)
    print(f"  DMG:     {dmg_path} ({dmg_size:.1f} MB)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"Build {APP_NAME} as a macOS application bundle."
    )
    parser.add_argument(
        "--dmg", action="store_true",
        help="Also create a DMG disk image for distribution.",
    )
    parser.add_argument(
        "--icon", type=str, default=None,
        help="Path to an .icns icon file for the app.",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Building {APP_NAME}.app (v{VERSION})")
    print(f"{'='*60}")

    build_app(icon_path=args.icon)

    if args.dmg:
        build_dmg()

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}")
    print(f"""
  To run:
    open dist/{APP_NAME}.app

  User data location:
    ~/Library/Application Support/{APP_NAME}/data/
      config/     — LLM & agent configuration
      workspace/  — workspace files, skills, tasks
      env.sh      — environment variables (API keys, etc.)

  Logs:
    ~/Library/Logs/{APP_NAME}/

  Note: On first launch, macOS Gatekeeper may block the app.
    Right-click the app → Open, or go to:
    System Settings → Privacy & Security → Open Anyway
""")


if __name__ == "__main__":
    main()
