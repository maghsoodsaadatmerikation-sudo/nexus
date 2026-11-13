#!/usr/bin/env bash
# Stage26 builds an emulator-only copy of the reviewed Stage25 APK and a
# separately compiled Android-platform instrumentation APK. Both are signed
# by the SAME fresh, disposable cert, which NEVER leaves this job.
set -euo pipefail
cd "$(dirname "$0")/.."
test -n "${ANDROID_HOME:-}"
test -z "${RAILWAY_TOKEN:-}"
test -z "${RAILWAY_API_TOKEN:-}"
test -z "${NEXUS_API_TOKEN:-}"
test -z "${RENDER_API_KEY:-}"
test -z "${ANDROID_SIGNING_KEY:-}"
BT="$ANDROID_HOME/build-tools/35.0.1"
ANDROID_JAR="$ANDROID_HOME/platforms/android-35/android.jar"
for tool in aapt2 d8 zipalign apksigner; do test -x "$BT/$tool"; done
test -f "$ANDROID_JAR"

# A separately audited Stage25 user APK is still built and never modified.
bash scripts/build-stage25-apk.sh
OUT=build/stage26-emulator
mkdir -p "$OUT"/{classes,dex,keys}
chmod 700 "$OUT/keys"
KEY_DIR="$OUT/keys"
export NEXUS_STAGE26_KEY_PASS
NEXUS_STAGE26_KEY_PASS="$(openssl rand -hex 24)"
cleanup() {
  rm -rf "$KEY_DIR"
  unset NEXUS_STAGE26_KEY_PASS
}
trap cleanup EXIT
keytool -genkeypair -noprompt \
  -keystore "$KEY_DIR/disposable.p12" \
  -alias nexus-stage26-synthetic \
  -keyalg RSA -keysize 3072 -validity 1 \
  -storetype PKCS12 -storepass "$NEXUS_STAGE26_KEY_PASS" \
  -keypass "$NEXUS_STAGE26_KEY_PASS" \
  -dname "CN=Discarded Android Emulator Trial, O=NEXUS Synthetic Only, C=US" \
  >/dev/null 2>&1

# Re-sign (without code or manifest changes) with the instrumentation cert.
cp build/stage25-android/nexus-offline-stage25-test.apk \
  "$OUT/emulator-resign-source.apk"
zip -q -d "$OUT/emulator-resign-source.apk" 'META-INF/*'
"$BT/zipalign" -f 4 "$OUT/emulator-resign-source.apk" \
  "$OUT/emulator-aligned.apk"
"$BT/apksigner" sign \
  --ks "$KEY_DIR/disposable.p12" --ks-key-alias nexus-stage26-synthetic \
  --ks-pass env:NEXUS_STAGE26_KEY_PASS \
  --key-pass env:NEXUS_STAGE26_KEY_PASS \
  --out "$OUT/nexus-app-emulator-only.apk" "$OUT/emulator-aligned.apk"
"$BT/apksigner" verify --print-certs \
  "$OUT/nexus-app-emulator-only.apk" > "$OUT/app-cert.txt"

# No Gradle, Maven, external dependency, instrumentation account or token.
"$BT/aapt2" link -o "$OUT/test-unsigned.apk" \
  -I "$ANDROID_JAR" \
  --manifest android/stage26/AndroidManifest.xml \
  --min-sdk-version 26 --target-sdk-version 35
javac -source 8 -target 8 -Xlint:-options \
  -classpath "$ANDROID_JAR" \
  -d "$OUT/classes" \
  android/stage26/src/org/nexus/offline/stage26/test/Stage26Instrumentation.java
mapfile -d '' CLASSES < <(find "$OUT/classes" -name '*.class' -print0)
test "${#CLASSES[@]}" -ge 1
"$BT/d8" --release --min-api 26 --lib "$ANDROID_JAR" \
  --output "$OUT/dex" "${CLASSES[@]}"
test -s "$OUT/dex/classes.dex"
zip -q -j "$OUT/test-unsigned.apk" "$OUT/dex/classes.dex"
"$BT/zipalign" -f 4 "$OUT/test-unsigned.apk" "$OUT/test-aligned.apk"
"$BT/apksigner" sign \
  --ks "$KEY_DIR/disposable.p12" --ks-key-alias nexus-stage26-synthetic \
  --ks-pass env:NEXUS_STAGE26_KEY_PASS \
  --key-pass env:NEXUS_STAGE26_KEY_PASS \
  --out "$OUT/nexus-stage26-instrumentation-only.apk" "$OUT/test-aligned.apk"
"$BT/apksigner" verify --print-certs \
  "$OUT/nexus-stage26-instrumentation-only.apk" > "$OUT/test-cert.txt"

# Fail closed on changes in original app resources, manifest or dex.
python3 scripts/test-stage26-build-pair.py \
  --original build/stage25-android/nexus-offline-stage25-test.apk \
  --resigned "$OUT/nexus-app-emulator-only.apk" \
  --instrumentation "$OUT/nexus-stage26-instrumentation-only.apk" \
  --app-cert "$OUT/app-cert.txt" --test-cert "$OUT/test-cert.txt"
cleanup
trap - EXIT
rm -f "$OUT/emulator-resign-source.apk" "$OUT/emulator-aligned.apk" \
   "$OUT/test-unsigned.apk" "$OUT/test-aligned.apk"
test ! -d "$KEY_DIR"
echo 'PASS: two same-certificate Android emulator APKs; target exact bytes; disposable signing key destroyed'
