#!/usr/bin/env bash
set -euo pipefail

cd /Users/ming/projects/MOCA
mkdir -p /tmp/moca-swift-module-cache scripts/study/bin
app_dir="scripts/study/bin/MOCARemindersAdvance.app"
mkdir -p "$app_dir/Contents/MacOS"
cp scripts/study/reminders_advance_info.plist "$app_dir/Contents/Info.plist"
CLANG_MODULE_CACHE_PATH=/tmp/moca-swift-module-cache \
  swiftc scripts/study/reminders_advance.swift \
    -o "$app_dir/Contents/MacOS/MOCARemindersAdvance"

if command -v codesign >/dev/null 2>&1; then
  codesign --force --sign - "$app_dir" >/dev/null 2>&1 || true
fi

"$app_dir/Contents/MacOS/MOCARemindersAdvance" --day auto
