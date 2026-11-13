#!/usr/bin/env bash
# Only an Android emulator may execute this integration acceptance.
# No production backend, physical device or Android account is required.
set -euo pipefail
cd "$(dirname "$0")/.."
test -z "${RAILWAY_TOKEN:-}"
test -z "${RAILWAY_API_TOKEN:-}"
test -z "${NEXUS_API_TOKEN:-}"
test -z "${RENDER_API_KEY:-}"
test -n "${ANDROID_HOME:-}"
command -v adb
command -v sdkmanager
command -v avdmanager
test -x "$ANDROID_HOME/emulator/emulator"

mkdir -p build/stage26-emulator
OUT=build/stage26-emulator
IMAGE='system-images;android-35;google_apis;x86_64'
printf 'no\n' | avdmanager create avd --force --name nexus_stage26 \
    --package "$IMAGE" --device 'pixel_3a' \
    > "$OUT/avd-create.log" 2>&1

if [ -c /dev/kvm ] && [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
  ACCEL='on'
else
  # Do not claim real Android emulator acceptance from a timeout-prone
  # software-only guest on hosted CI. Keep source build PASS separately.
  echo 'BLOCKED: no accessible /dev/kvm for independent Android emulator witness'
  exit 2
fi
"$ANDROID_HOME/emulator/emulator" \
  -avd nexus_stage26 -no-window -no-audio -no-boot-anim \
  -no-snapshot -no-metrics -gpu swiftshader_indirect \
  -accel "$ACCEL" -camera-back none -camera-front none \
  > "$OUT/emulator-start.log" 2>&1 &
EMULATOR_PID=$!
cleanup(){
  adb emu kill >/dev/null 2>&1 || true
  kill "$EMULATOR_PID" 2>/dev/null || true
  wait "$EMULATOR_PID" 2>/dev/null || true
}
trap cleanup EXIT
adb wait-for-device
for i in $(seq 1 240); do
  value="$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')"
  if [ "$value" = 1 ]; then break; fi
  if ! kill -0 "$EMULATOR_PID" 2>/dev/null; then
    echo 'BLOCKED: Android emulator exited before boot'
    exit 3
  fi
  sleep 2
done
test "$(adb shell getprop sys.boot_completed | tr -d '\r')" = 1 || {
  echo 'BLOCKED: Android emulator did not finish boot'
  exit 3
}
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
adb shell svc wifi disable || true
adb shell svc data disable || true
test "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" -ge 35
adb install -r "$OUT/nexus-app-emulator-only.apk"
adb install -r "$OUT/nexus-stage26-instrumentation-only.apk"
adb shell pm clear org.nexus.offline.stage25 >/dev/null

# The platform instrumentation result is our only actual runtime witness.
# The app and test APKs have no Android INTERNET permission.
adb shell am instrument -w -r \
  org.nexus.offline.stage26.test/.Stage26Instrumentation \
  > "$OUT/stage26-emulator-acceptance.txt"
python3 scripts/test-stage26-emulator-witness.py \
  --evidence "$OUT/stage26-emulator-acceptance.txt" \
  --pair "$OUT/stage26-emulator-apk-pair.json" \
  --out "$OUT/stage26-emulator-witness.json"
echo 'PASS: real Android API35 emulator WebView encrypted vault, reopen, tamper and picker intent'
