#!/usr/bin/env bash
# Stage25: compile an installable, single-device, no-internet experimental APK.
# Ephemeral signing key: changes need uninstall (loss of nonexported app vault).
set -euo pipefail
cd "$(dirname "$0")/.."
test -n "${ANDROID_HOME:-}"
test -z "${RAILWAY_TOKEN:-}"
test -z "${RAILWAY_API_TOKEN:-}"
test -z "${NEXUS_API_TOKEN:-}"
test -z "${RENDER_API_KEY:-}"
test -z "${ANDROID_SIGNING_KEY:-}"
BT="$ANDROID_HOME/build-tools/35.0.1"
PLATFORM="$ANDROID_HOME/platforms/android-35/android.jar"
test -x "$BT/aapt2"
test -x "$BT/d8"
test -x "$BT/zipalign"
test -x "$BT/apksigner"
test -f "$PLATFORM"
command -v javac
command -v keytool
command -v openssl
command -v zip
command -v unzip
OUT=build/stage25-android
mkdir -p "$OUT"/{assets/nexus,res/mipmap-nodpi,resflat,classes,dex}
python3 scripts/build-stage25-android-assets.py --out "$OUT/generated"
python3 scripts/build-stage25-android-assets.py --out "$OUT/generated" --check
cp "$OUT/generated/nexus/index.html" "$OUT/assets/nexus/index.html"
cp "$OUT/generated/mipmap-nodpi/ic_launcher.png" "$OUT/res/mipmap-nodpi/ic_launcher.png"
"$BT/aapt2" compile -o "$OUT/resflat" "$OUT/res/mipmap-nodpi/ic_launcher.png"
RESOURCE="$OUT/resflat/mipmap-nodpi_ic_launcher.png.flat"
test -s "$RESOURCE"
"$BT/aapt2" link -o "$OUT/unsigned.apk" \
  -I "$PLATFORM" \
  --manifest android/stage25/AndroidManifest.xml \
  --min-sdk-version 26 --target-sdk-version 35 \
  --version-code 25 --version-name 0.25.0 \
  -A "$OUT/assets" -R "$RESOURCE"
javac -source 8 -target 8 -Xlint:-options \
  -classpath "$PLATFORM" \
  -d "$OUT/classes" \
  android/stage25/src/org/nexus/offline/stage25/MainActivity.java
mapfile -d '' CLASS_FILES < <(find "$OUT/classes" -name '*.class' -print0)
test "${#CLASS_FILES[@]}" -ge 2
"$BT/d8" --release --min-api 26 \
  --lib "$PLATFORM" --output "$OUT/dex" "${CLASS_FILES[@]}"
test -s "$OUT/dex/classes.dex"
zip -q -j "$OUT/unsigned.apk" "$OUT/dex/classes.dex"
"$BT/zipalign" -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
TMP_KEY="$(mktemp -d "$OUT/nexus-temporary-key.XXXXXX")"
export NEXUS_STAGE25_KEYPASS
NEXUS_STAGE25_KEYPASS="$(openssl rand -hex 24)"
cleanup(){ rm -rf "$TMP_KEY"; unset NEXUS_STAGE25_KEYPASS; }
trap cleanup EXIT
keytool -genkeypair -noprompt \
  -keystore "$TMP_KEY/test-release.jks" \
  -alias nexus-stage25-preview -keyalg RSA -keysize 3072 \
  -validity 365 -storetype PKCS12 \
  -storepass "$NEXUS_STAGE25_KEYPASS" \
  -keypass "$NEXUS_STAGE25_KEYPASS" \
  -dname "CN=NEXUS Offline Trial, O=Ephemeral Test Build, C=US" \
  >/dev/null 2>&1
"$BT/apksigner" sign --ks "$TMP_KEY/test-release.jks" \
  --ks-key-alias nexus-stage25-preview \
  --ks-pass env:NEXUS_STAGE25_KEYPASS \
  --key-pass env:NEXUS_STAGE25_KEYPASS \
  --out "$OUT/nexus-offline-stage25-test.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify --verbose "$OUT/nexus-offline-stage25-test.apk" \
  > "$OUT/apksigner-verify.txt"
"$BT/apksigner" verify --print-certs "$OUT/nexus-offline-stage25-test.apk" \
  > "$OUT/apksigner-public-cert.txt"
"$BT/aapt2" dump permissions "$OUT/nexus-offline-stage25-test.apk" \
  > "$OUT/manifest-permissions.txt"
"$BT/aapt2" dump badging "$OUT/nexus-offline-stage25-test.apk" \
  > "$OUT/badging.txt"
"$BT/aapt2" dump xmltree --file AndroidManifest.xml "$OUT/nexus-offline-stage25-test.apk" \
  > "$OUT/manifest-tree.txt"
echo "Android manifest public SDK fields:"
grep -E 'uses-sdk|minSdkVersion|targetSdkVersion' "$OUT/manifest-tree.txt" | head -n 8 || true
python3 scripts/test-stage25-apk.py \
  --apk "$OUT/nexus-offline-stage25-test.apk" \
  --badging "$OUT/badging.txt" \
  --permissions "$OUT/manifest-permissions.txt" \
  --public-cert "$OUT/apksigner-public-cert.txt" \
  --out "$OUT/nexus-stage25-apk-evidence.json"
rm -f "$OUT/unsigned.apk" "$OUT/aligned.apk"
cleanup
trap - EXIT
echo "PASS: Android SDK native APK, no Internet/privileged permissions, signed test artifact"
