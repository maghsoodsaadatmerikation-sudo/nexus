# Publish NEXUS Studio

The Android app launches the existing public Studio in a Trusted Web Activity. Its features and updates come from the same HTTPS origin as the website and installable PWA. Android delegates browser storage, file pickers, downloads, and web permissions to the selected browser. On the same profile, the app uses that origin’s browser data. For another device or browser, import an encrypted portable backup.

| Surface | Public access | Build or distribution |
| --- | --- | --- |
| Web | [NEXUS Studio](https://nexus-studio-merikation.onrender.com/) | Render publishes `public/studio` after `python3 scripts/build-studio-static.py --check`. |
| Android and iPhone home screen | Open the same HTTPS site and choose Install app or Add to Home Screen. | Studio can cache its code through Prepare offline use. Keep projects in a separate encrypted archive. |
| Android store | Package `com.merikation.nexus.studio`, target API 36 | Build, sign and submit the release AAB. The test APK has its own package suffix. |

Projects and branching chat, writing, local source search, data analysis, charts, the reviewed JavaScript lab, astrology, music, score export, vocal mixing and encrypted backups use the same web implementation. Live research requires connectivity. Device-model inference requires compatible browser hardware and the initial download. Online model replies require a separately configured HTTPS gateway and provider. Browser and OS support affects voice features and downloads. There are no Studio accounts or automatic cross-device synchronization.

## Build and verify Android

Use JDK 17 or 21, Gradle 8.13, Android SDK Platform 36 and Build Tools 35.0.0. Set `ANDROID_HOME` to the SDK directory. From the repository root run:

```sh
gradle --no-daemon --project-dir android :app:lintRelease :app:assembleDebug :app:bundleRelease
```

The debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`. The unsigned release bundle is `android/app/build/outputs/bundle/release/app-release.aab`. The Android CI workflow publishes both with SHA-256 checksums. The test APK opens the public website in a browser surface. On a physical phone test first launch, Persian text, audio previews and file import/export, first offline setup and airplane-mode restart, encrypted save/reopen, and an external link returning to Studio.

## Publish on Google Play

1. In the owner’s Play Console, reserve `com.merikation.nexus.studio` and create the application. Keep this package ID stable once published. Increment `versionCode` for future Android uploads.
2. Sign the release bundle with the owner's upload key in Android Studio or with `jarsigner`. Keep the private key and passwords out of Git and chat. Upload the signed bundle to an internal testing track and enable Play App Signing.
3. Copy the **Play app signing** certificate SHA-256 fingerprint from App integrity. Generate the website statement with `python3 android/assetlinks.py FINGERPRINT` and have the deployment publish that JSON at `https://nexus-studio-merikation.onrender.com/.well-known/assetlinks.json` over HTTPS, with HTTP 200, JSON content type and no redirects. Keep the exact public directory allowlist and deployment witness in sync when adding the file. Use the Play app-signing fingerprint for store installs. A separate distribution key can be added only if it is also used for authorized public builds.
4. Install the owner-approved signed build from the test track. Verify domain association with `adb shell pm get-app-links com.merikation.nexus.studio` and confirm the public studio opens without browser chrome in a supporting browser. Before verification Android falls back to a browser surface. First launch needs connectivity, and offline relaunch depends on the same browser profile having already prepared Studio.
5. Complete the store listing, screenshots, content rating and Data safety disclosures against the actual release. Link the [public privacy policy](https://nexus-studio-merikation.onrender.com/#studio-privacy) after deploying the corresponding website change. Apply any Play Console testing requirements shown for the owner account before requesting production review.

For an Apple App Store package, this Android AAB cannot be reused. The iPhone release route covered here is the installable Safari web app.
