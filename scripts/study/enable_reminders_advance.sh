#!/usr/bin/env bash
set -euo pipefail

cd /Users/ming/projects/MOCA

echo "Building MOCARemindersAdvance.app..."
bash scripts/study/build_reminders_advance.sh || true

echo
echo "Opening System Settings > Privacy & Security > Reminders."
echo "Please enable Reminders access for: MOCA Reminders Advance"
echo
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Reminders"

echo "After enabling the permission, press Enter to test."
read -r _

if scripts/study/bin/MOCARemindersAdvance.app/Contents/MacOS/MOCARemindersAdvance --day auto; then
  echo "Permission test passed. Installing launchd watcher..."
  cp scripts/study/launchd/com.moca.study.reminders-advance.plist /Users/ming/Library/LaunchAgents/
  launchctl unload /Users/ming/Library/LaunchAgents/com.moca.study.reminders-advance.plist >/dev/null 2>&1 || true
  launchctl load /Users/ming/Library/LaunchAgents/com.moca.study.reminders-advance.plist
  echo "Installed: com.moca.study.reminders-advance"
else
  echo "Permission test failed. Confirm MOCA Reminders Advance is enabled in Reminders privacy settings."
  exit 1
fi

