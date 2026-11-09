# VOIDLOCK for Android

The phone app is the same web UI that you can open in any browser (`app/src/main/assets/www`), shown in a small native shell
(`MainActivity.kt`, `Bridge.kt`). It keeps its data in the phone, works offline and syncs with the computer app.

* Study timer, goal ring, subjects with any colour, tests / words counters, tasks, daily study chart, exams with results
  (total taraz, overall rank, **region rank**, per-subject percent / taraz) and their progress charts. Persian (Jalali dates, RTL) and English.
* **Sync with the computer** over Wi-Fi (any modem, even a SIM modem, or the phone's hotspot; no internet needed) or with a `.voidsync` file.
  The rules are described at the top of `voidlock/sync.py`; the computer side of the Wi-Fi sync is `voidlock/lansync.py`.
* **Reports** (More → Report): a period (7 / 14 / 30 / 90 days, everything, or custom) as PDF (Android print dialog → *Save as PDF*), a web page, or CSV.
* **Background sync**: `SyncWorker` opens the app page without a screen (`#bg`), does one encrypted sync and closes (every ~15 minutes on the same network, and ~20 s after the app is left). Android decides the exact time; it is not live.
* **Encrypted sync**: ECDH + a confirmation number shown on both devices, then AES-256-GCM (see the top of `voidlock/lansync.py`).
* **Updates** come from this repository's GitHub Releases: *More → About → Check for updates* downloads `VoidLock.apk`, checks its SHA-256
  against `VoidLock.apk.sha256` and opens the Android installer (Android only accepts it if it is signed with the same key).

## One release = both apps

Pushing a tag `vX.Y.Z` (equal to `__version__` in `voidlock/__init__.py`) runs `.github/workflows/release.yml`, which builds
`VoidLock.exe` (Windows), `VoidLock.apk` (Android) and publishes them in the same GitHub release. The Android version is the same number.
If the Android job fails, the Windows release is still published.

### One-time setup (signing key)

The APK must always be signed with the same key. Create 4 repository secrets (Settings → Secrets and variables → Actions):
`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`.
To make a new key yourself: 

```
keytool -genkeypair -keystore voidlock-release.jks -alias voidlock -keyalg RSA -keysize 2048 -validity 10000 -storetype PKCS12
base64 -w0 voidlock-release.jks        # the value of ANDROID_KEYSTORE_BASE64
```

Keep the `.jks` file and its password safe (never commit them: `.gitignore` already excludes `*.jks`). If the key is lost, installed phones cannot be updated.

## Tests (no Android needed)

```
node android/tests/js_unit_test.js           # logic of the phone app (colours, time, exams, sync, texts)
python android/tests/interop_test.py         # computer (Python) <-> phone (JavaScript): random work + syncs, both must end identical
python android/tests/lan_interop_test.py     # the phone's Wi-Fi client against the computer's real server
python android/tests/ui_flow_test.py         # taps through the UI in Chromium (Playwright), incl. pairing and live sync
python android/tests/shots.py db.json out    # screenshots
```

## Build locally

Android Studio (open the `android` folder) or `gradle -p android assembleDebug` (Gradle 8.7, JDK 17, Android SDK 34).
