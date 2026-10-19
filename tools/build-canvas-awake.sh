#!/bin/zsh
set -e
cd "$(dirname "$0")/.."
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk}"
mkdir -p data/canvas-power/classes data/canvas-power/dex
"$JAVA_HOME/bin/javac" -source 11 -target 11 -cp "$SDK/platforms/android-35/android.jar" -d data/canvas-power/classes tools/HoldCanvasAwake.java
"$JAVA_HOME/bin/jar" cf data/canvas-power/helper.jar -C data/canvas-power/classes .
"$SDK/build-tools/35.0.0/d8" --min-api 29 --lib "$SDK/platforms/android-35/android.jar" --output data/canvas-power/dex data/canvas-power/helper.jar
