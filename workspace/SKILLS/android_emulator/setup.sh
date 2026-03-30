#!/bin/bash
set -e

#############################################
# Android Emulator Setup Script
# Supports: macOS (arm64/x86_64), Linux
#############################################

echo "========================================="
echo "  Android Emulator Setup"
echo "========================================="

# Detect OS and architecture
OS=$(uname -s)
ARCH=$(uname -m)
echo "OS: $OS, Arch: $ARCH"

# Set ANDROID_HOME
export ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

mkdir -p "$ANDROID_HOME"

#############################################
# Step 1: Install Java (if needed)
#############################################
if ! command -v java &> /dev/null; then
    echo ">>> Installing Java..."
    if [[ "$OS" == "Darwin" ]]; then
        brew install openjdk@17
        sudo ln -sfn $(brew --prefix openjdk@17)/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk
    else
        sudo apt-get update && sudo apt-get install -y openjdk-17-jdk
    fi
else
    echo ">>> Java already installed: $(java -version 2>&1 | head -1)"
fi

#############################################
# Step 2: Download Android Command Line Tools
#############################################
if [ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]; then
    echo ">>> Downloading Android Command Line Tools..."
    
    CMDLINE_TOOLS_DIR="$ANDROID_HOME/cmdline-tools"
    mkdir -p "$CMDLINE_TOOLS_DIR"
    
    if [[ "$OS" == "Darwin" ]]; then
        CMDLINE_URL="https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip"
    else
        CMDLINE_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
    fi
    
    TEMP_ZIP="/tmp/cmdline-tools.zip"
    curl -L -o "$TEMP_ZIP" "$CMDLINE_URL"
    unzip -q -o "$TEMP_ZIP" -d "$CMDLINE_TOOLS_DIR"
    mv "$CMDLINE_TOOLS_DIR/cmdline-tools" "$CMDLINE_TOOLS_DIR/latest"
    rm "$TEMP_ZIP"
    
    echo ">>> Command Line Tools installed at $CMDLINE_TOOLS_DIR/latest"
else
    echo ">>> Command Line Tools already installed"
fi

#############################################
# Step 3: Accept licenses & install SDK packages
#############################################
echo ">>> Installing SDK packages..."
yes | sdkmanager --licenses 2>/dev/null || true

# Install platform tools (adb), emulator, system image
sdkmanager "platform-tools" "emulator"

# Choose system image based on architecture
if [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
    SYSTEM_IMAGE="system-images;android-34;google_apis;arm64-v8a"
else
    SYSTEM_IMAGE="system-images;android-34;google_apis;x86_64"
fi

echo ">>> Installing system image: $SYSTEM_IMAGE"
sdkmanager "$SYSTEM_IMAGE" "platforms;android-34"

#############################################
# Step 4: Create AVD (Android Virtual Device)
#############################################
AVD_NAME="test_device"

if avdmanager list avd 2>/dev/null | grep -q "$AVD_NAME"; then
    echo ">>> AVD '$AVD_NAME' already exists"
else
    echo ">>> Creating AVD: $AVD_NAME"
    echo "no" | avdmanager create avd \
        --name "$AVD_NAME" \
        --package "$SYSTEM_IMAGE" \
        --device "pixel_6"
    echo ">>> AVD '$AVD_NAME' created"
fi

#############################################
# Step 5: Environment setup
#############################################
echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Add to your shell profile (~/.zshrc or ~/.bashrc):"
echo ""
echo "  export ANDROID_HOME=$ANDROID_HOME"
echo '  export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH'
echo ""
echo "To start the emulator:"
echo "  emulator -avd $AVD_NAME -no-audio -no-window &"
echo ""
echo "Or with GUI:"
echo "  emulator -avd $AVD_NAME &"
echo ""
echo "Then use the Python controller:"
echo "  python android_controller.py demo"
echo ""
